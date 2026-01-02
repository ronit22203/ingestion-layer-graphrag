import logging
from pathlib import Path
from neo4j import GraphDatabase

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent

# Neo4j Settings (Your Docker Container)
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "testpassword")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


class KnowledgeGraphDeleter:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
            self.driver.verify_connectivity()
            logger.info("Connected to Neo4j Graph Database")
        except Exception as e:
            logger.critical(f"Failed to connect to Neo4j: {e}")
            raise e

    def close(self):
        self.driver.close()

    def delete_all_nodes(self):
        """Delete all nodes and relationships from the graph."""
        with self.driver.session() as session:
            try:
                # First, delete all relationships
                session.run("MATCH ()-[r]-() DELETE r")
                logger.info("Deleted all relationships")
                
                # Then, delete all nodes
                session.run("MATCH (n) DELETE n")
                logger.info("Deleted all nodes")
                
                # Verify the graph is empty
                result = session.run("MATCH (n) RETURN COUNT(n) as count")
                count = result.single()['count']
                
                if count == 0:
                    logger.info("✓ Graph successfully cleared - 0 nodes remaining")
                else:
                    logger.warning(f"Graph still contains {count} nodes")
                    
            except Exception as e:
                logger.error(f"Failed to delete graph: {e}")
                raise e

    def delete_entities_by_source(self, source_pattern: str):
        """Delete entities/relationships by source file pattern."""
        with self.driver.session() as session:
            try:
                # Delete relationships with matching source
                result = session.run(
                    "MATCH ()-[r {source: $pattern}]-() DELETE r RETURN count(r) as count",
                    pattern=source_pattern
                )
                deleted_rels = result.single()['count']
                logger.info(f"Deleted {deleted_rels} relationships from source: {source_pattern}")
                
                # Clean up orphaned nodes (nodes with no relationships)
                result = session.run("MATCH (n) WHERE NOT (n)--() DELETE n RETURN count(n) as count")
                deleted_nodes = result.single()['count']
                logger.info(f"Cleaned up {deleted_nodes} orphaned nodes")
                
            except Exception as e:
                logger.error(f"Failed to delete by source: {e}")
                raise e

    def get_graph_stats(self):
        """Get statistics about the current graph."""
        with self.driver.session() as session:
            try:
                node_count = session.run("MATCH (n) RETURN COUNT(n) as count").single()['count']
                rel_count = session.run("MATCH ()-[r]-() RETURN COUNT(r) as count").single()['count']
                
                logger.info(f"Graph Stats: {node_count} nodes, {rel_count} relationships")
                return {"nodes": node_count, "relationships": rel_count}
                
            except Exception as e:
                logger.error(f"Failed to get graph stats: {e}")
                return None

    def run(self):
        """Main execution."""
        logger.info("Starting Knowledge Graph Deletion...")
        
        # Show current stats
        stats = self.get_graph_stats()
        
        if stats and stats['nodes'] == 0:
            logger.info("Graph is already empty")
            return
        
        # Delete all nodes and relationships
        self.delete_all_nodes()


if __name__ == "__main__":
    deleter = KnowledgeGraphDeleter()
    try:
        deleter.run()
    finally:
        deleter.close()
        logger.info("Done")
