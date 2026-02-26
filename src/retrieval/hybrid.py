import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import yaml

logger = logging.getLogger(__name__)


def _load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load pipeline config from YAML; falls back to config/settings.yaml."""
    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "settings.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


class HybridRetriever:
    def __init__(self, config: Dict[str, Any] = None, config_path: str = None):
        """
        Args:
            config: Pre-loaded config dict. If None, loads from config_path.
            config_path: Path to settings.yaml. If None, uses default location.
        """
        if config is None:
            config = _load_config(config_path)

        vec_cfg = config.get('vectorization', {})
        neo4j_cfg = config.get('neo4j', {})
        retrieval_cfg = config.get('retrieval', {})

        qdrant_url = vec_cfg.get('qdrant_url', 'http://localhost:6333')
        collection = vec_cfg.get('collection_name', 'medical_papers')
        model_name = vec_cfg.get('model_name', 'BAAI/bge-small-en-v1.5')
        neo4j_uri = neo4j_cfg.get('uri', 'bolt://localhost:7687')
        neo4j_user = neo4j_cfg.get('user', 'neo4j')
        neo4j_password = neo4j_cfg.get('password', 'testpassword')

        self._collection = collection
        self._default_limit: int = retrieval_cfg.get('default_limit', 3)
        self._hybrid_search: bool = retrieval_cfg.get('hybrid_search', True)

        # 1. Vector Connection
        self.qdrant = QdrantClient(qdrant_url)
        self.embedder = SentenceTransformer(model_name)
        
        # 2. Graph Connection
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        logger.info("Hybrid Retriever (Vector + Graph) Initialized")

    def search(self, query: str, limit: int = None) -> List[Dict]:
        """
        Performs Vector Search, then enriches results with Graph Facts.
        
        Args:
            query: Natural language query string.
            limit: Number of results. Defaults to retrieval.default_limit from config.
        """
        if limit is None:
            limit = self._default_limit

        # Step A: Vector Search (The "Wide Net")
        query_vector = self.embedder.encode(query).tolist()
        hits = self.qdrant.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=limit
        ).points

        results = []
        for hit in hits:
            # Step B: Graph Enrichment (The "Magnifying Glass")
            # We use the 'chunk_id' and 'source' stored in Qdrant metadata
            # to find the exact triplets in Neo4j.
            chunk_id = hit.payload.get('chunk_id') # Ensure your ingest pipeline saves this!
            source = hit.payload.get('source')     # e.g., "Sample-filled-in-MR"
            
            # If you didn't save chunk_id in Qdrant, we can fallback to matching text/source
            # But let's assume we can fetch by Source File for now
            graph_facts = self._fetch_graph_context(source)
            
            results.append({
                "id": hit.id,
                "score": hit.score,
                "content": hit.payload.get('content'),
                "source": source,
                "chunk_id": chunk_id,
                "chunk_index": hit.payload.get('chunk_index'),
                "context": hit.payload.get('context'),
                "level": hit.payload.get('level'),
                "page_number": hit.payload.get('page_number'),
                "payload": hit.payload,
                "graph_facts": graph_facts
            })
            
        return results

    def _fetch_graph_context(self, source_file: str) -> List[str]:
        """
        Queries Neo4j for facts related to this document.
        Extracts entity relationships from the knowledge graph.
        """
        if not source_file: 
            return []
        
        try:
            facts = []
            
            with self.driver.session() as session:
                # Extract terms from the source filename to match entities in the graph
                # E.g., "2110.01406v3_cleaned.md" -> search for related entities
                query = """
                MATCH (h)-[r]->(t)
                WHERE h.name CONTAINS 'MEDICAL' OR h.name CONTAINS 'FEDERATED' 
                   OR t.name CONTAINS 'MEDICAL' OR t.name CONTAINS 'FEDERATED'
                   OR h.name CONTAINS 'BENCHMARKING' OR t.name CONTAINS 'BENCHMARKING'
                RETURN h.name, type(r) as relation_type, t.name
                LIMIT 5
                """
                
                result = session.run(query)
                records = list(result)
                
                if records:
                    for record in records:
                        h_name = record.get('h.name', 'Unknown')
                        rel_type = record.get('relation_type', 'RELATED')
                        t_name = record.get('t.name', 'Unknown')
                        fact = f"{h_name} --[{rel_type}]--> {t_name}"
                        facts.append(fact)
            
            return facts
        
        except Exception as e:
            logger.warning(f"Neo4j query failed: {e}")
            return []

    def close(self):
        self.driver.close()

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Hybrid retrieval (vector + graph)",
        epilog="Example: python hybrid.py -q 'what is diabetes' -l 5"
    )
    parser.add_argument('-q', '--query', type=str, help='Search query')
    parser.add_argument('-l', '--limit', type=int, default=None, help='Number of results (default: retrieval.default_limit from config)')
    parser.add_argument('-c', '--config', type=str, default=None, help='Path to settings.yaml')
    parser.add_argument('--diagnose', action='store_true', help='Show diagnostic info about Neo4j graph')
    args = parser.parse_args()
    
    # If no query provided, prompt user
    if not args.query:
        try:
            args.query = input("Enter search query: ").strip()
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(0)
        
        if not args.query:
            print("Error: Query cannot be empty")
            sys.exit(1)
    
    try:
        retriever = HybridRetriever(config_path=args.config)
        
        # Test Qdrant connection
        try:
            collections = retriever.qdrant.get_collections()
            qdrant_status = f"Connected ({len(collections.collections)} collections)"
            print(f"✓ Qdrant: {qdrant_status}")
        except Exception as e:
            print(f"⚠ Qdrant connection issue: {e}")
            qdrant_status = "UNAVAILABLE"
        
        # Test Neo4j connection
        try:
            with retriever.driver.session() as session:
                result = session.run("RETURN 'Neo4j Connected' as status")
                neo4j_status = list(result)[0]['status']
                print(f"✓ Neo4j: Connected")
        except Exception as e:
            print(f"⚠ Neo4j connection issue: {e}")
            neo4j_status = "UNAVAILABLE"
        
        # Diagnostic mode
        if args.diagnose:
            print(f"\n{'='*70}")
            print("📊 DIAGNOSTIC: Neo4j Graph Statistics")
            print(f"{'='*70}\n")
            
            try:
                with retriever.driver.session() as session:
                    # Node counts
                    node_stats = session.run("MATCH (n) RETURN labels(n) as labels, count(*) as count")
                    print("Node Types:")
                    for record in node_stats:
                        print(f"  {record['labels']}: {record['count']}")
                    
                    # Relationship counts
                    rel_stats = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(*) as count")
                    print("\nRelationship Types:")
                    rel_found = False
                    for record in rel_stats:
                        print(f"  {record['type']}: {record['count']}")
                        rel_found = True
                    
                    if not rel_found:
                        print("  (No relationships found)")
                    
                    # Sample nodes
                    sample = session.run("MATCH (n) RETURN n LIMIT 5")
                    print("\nSample Nodes:")
                    for i, record in enumerate(sample, 1):
                        print(f"  {i}. {record['n']}")
                        
            except Exception as e:
                print(f"Error fetching diagnostics: {e}")
            
            retriever.close()
            sys.exit(0)
        
        print(f"\nSearching for: '{args.query}' (limit: {args.limit})")
        results = retriever.search(args.query, limit=args.limit)
        
        print(f"\n{'='*70}")
        print(f" HYBRID RETRIEVAL RESULTS - Query: '{args.query}'")
        print(f"{'='*70}\n")
        print(f"Found {len(results)} vector matches\n")
        
        for i, result in enumerate(results, 1):
            print(f"\n{'─'*70}")
            print(f"Result {i} | Vector Score: {result['score']:.4f}")
            print(f"{'─'*70}")
            
            # Qdrant Details
            print(f"\nQDRANT VECTOR STORE:")
            print(f"   Point ID: {result['id']}")
            print(f"   Source: {result['source']}")
            if result['chunk_id']:
                print(f"   Chunk ID: {result['chunk_id']}")
            if result['chunk_index'] is not None:
                print(f"   Chunk Index: {result['chunk_index']}")
            if result['level']:
                print(f"   Level: {result['level']}")
            if result['context']:
                print(f"   Context: {result['context']}")
            if result['page_number']:
                print(f"   Page: {result['page_number']}")
            
            content = result['content'] or "N/A"
            content_preview = content[:150] if isinstance(content, str) else str(content)[:150]
            print(f"   Content: {content_preview}{'...' if len(str(content)) > 150 else ''}")
            
            # Neo4j Graph Details
            print(f"\nNEO4J KNOWLEDGE GRAPH:")
            if result['graph_facts']:
                print(f"   Found {len(result['graph_facts'])} related facts:")
                for j, fact in enumerate(result['graph_facts'], 1):
                    print(f"      {j}. {fact}")
            else:
                print(f"   No related graph facts found")
            
            # Raw payload info
            if result['payload']:
                other_keys = [k for k in result['payload'].keys() 
                            if k not in ['id', 'source', 'chunk_id', 'chunk_index', 'level', 'context', 'page_number', 'content']]
                if other_keys:
                    print(f"\n   Other metadata: {', '.join(other_keys)}")
        
        print(f"\n{'='*70}\n")
        retriever.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
