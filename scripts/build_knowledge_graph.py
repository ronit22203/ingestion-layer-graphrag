import json
import requests
import logging
import time
import re
from pathlib import Path
from neo4j import GraphDatabase



# --- Configuration ---
# Path to existing chunks

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
CHUNKS_DIR = REPO_ROOT / "data" / "chunks"

# Ollama Settings

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "cniongolo/biomistral:latest"
OLLAMA_TIMEOUT = 120  # seconds
OLLAMA_MAX_RETRIES = 2


# Neo4j Settings (Your Docker Container)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j","testpassword")


# Logging Setup

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s | %(levelname)s | %(message)s',
	datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
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

    def extract_relations(self, text: str):
        """
        Extract relations with retry logic and timeout handling.
        """
        if len(text) < 50:
            return []

        # We force a JSON schema in the prompt
        prompt = f"""<s>[INST] You are a medical knowledge graph extractor. 
        Analyze the text and extract triplets: (Head, Relation, Tail).
        
        Rules:
        1. Return ONLY a valid JSON object.
        2. "head" and "tail" must be specific medical entities (Drugs, Diseases, Symptoms).
        3. "relation" must be a single verb in UPPERCASE (e.g., TREATS, CAUSES, PREVENTS).
        4. Do not output conversational text.

        Text: "{text[:2000]}"

        Expected JSON Structure:
        {{
            "triplets": [
                {{"head": "Aspirin", "relation": "TREATS", "tail": "Headache"}},
                {{"head": "Insulin", "relation": "REGULATES", "tail": "Blood Glucose"}}
            ]
        }}
        [/INST]"""

        for attempt in range(OLLAMA_MAX_RETRIES):
            try:
                response = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": MODEL_NAME,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {
                            "temperature": 0.0,
                            "num_ctx": 4096
                        }
                    },
                    timeout=OLLAMA_TIMEOUT
                )
                
                if response.status_code != 200:
                    logger.error(f"Ollama Error (attempt {attempt+1}/{OLLAMA_MAX_RETRIES}): {response.text}")
                    if attempt < OLLAMA_MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)  # exponential backoff
                        continue
                    return []

                # Parse JSON directly, no Regex guessing
                data = response.json()
                response_text = data.get('response', '{}')
                
                try:
                    parsed = json.loads(response_text)
                    # Handle cases where model wraps it in different keys
                    triplets = parsed.get('triplets', []) or parsed.get('relations', [])
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON: {response_text[:100]}...")
                    return []
                
                # Simple validation
                valid_triplets = []
                for t in triplets:
                    if 'head' in t and 'relation' in t and 'tail' in t:
                        valid_triplets.append(t)
                
                logger.debug(f"Extracted {len(valid_triplets)} triplets")
                return valid_triplets
                
            except requests.exceptions.Timeout:
                logger.warning(f"Ollama timeout (attempt {attempt+1}/{OLLAMA_MAX_RETRIES}), retrying...")
                if attempt < OLLAMA_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    logger.error("Ollama: Max retries exceeded due to timeout")
                    return []
            except requests.exceptions.ConnectionError:
                logger.warning(f"Ollama connection error (attempt {attempt+1}/{OLLAMA_MAX_RETRIES}), retrying...")
                if attempt < OLLAMA_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    logger.error("Ollama: Max retries exceeded due to connection error")
                    return []
            except Exception as e:
                logger.error(f"Extraction failed (attempt {attempt+1}/{OLLAMA_MAX_RETRIES}): {e}")
                if attempt < OLLAMA_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return []

    def ingest_triplets(self, triplets, source_file, chunk_id):
        """
        FIX 3: Dynamic Cypher Relationships
        Instead of (:Entity)-[:RELATION {type:'TREATS'}]->(:Entity),
        we create (:Entity)-[:TREATS]->(:Entity)
        """
        if not triplets:
            return

        with self.driver.session() as session:
            for t in triplets:
                head = t['head'].strip().upper()
                tail = t['tail'].strip().upper()
                
                # Sanitize relation to ensure it's a valid Cypher identifier
                # Replace spaces/dashes with underscores, keep only alphanumeric
                raw_rel = t['relation'].strip().upper().replace(" ", "_").replace("-", "_")
                relation_type = "".join(c for c in raw_rel if c.isalnum() or c == '_')
                
                if not relation_type: 
                    relation_type = "RELATED_TO"

                # We use string formatting for the Relationship TYPE because 
                # Cypher cannot parameterize relationship types (e.g., -[:$rel]-> is illegal).
                # Since we sanitized 'relation_type' above, this is safe from injection.
                query = f"""
                MERGE (h:Entity {{name: $head}})
                MERGE (t:Entity {{name: $tail}})
                MERGE (h)-[r:{relation_type}]->(t)
                SET r.source = $source, r.chunk_id = $chunk_id
                """
                
                try:
                    session.run(query, head=head, tail=tail, 
                                source=source_file, chunk_id=chunk_id)
                except Exception as e:
                    logger.warning(f"Neo4j Write Error: {e}")
        
        logger.info(f"-> Graph: Added {len(triplets)} relations from {source_file}")

    def run(self):
        """Main Loop: Iterate over all chunks with resume capability."""
        chunk_files = list(CHUNKS_DIR.glob("*_chunks.json"))
        logger.info(f"Found {len(chunk_files)} chunk files to process.")

        for file_path in chunk_files:
            logger.info(f"Processing file: {file_path.name}")
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Extract chunks from the wrapper dict
            chunks = data.get('chunks', []) if isinstance(data, dict) else data

            for i, chunk in enumerate(chunks):
                try:
                    # Only process chunks that have "content"
                    content = chunk.get('content', '')
                    
                    logger.info(f"Using BioMistral on Chunk {i+1}/{len(chunks)}...")
                    triplets = self.extract_relations(content)
                    
                    if triplets:
                        self.ingest_triplets(triplets, file_path.stem, i)
                    else:
                        logger.info("-> No relations found (or empty).")
                except KeyboardInterrupt:
                    logger.info(f"Processing interrupted at chunk {i+1}. You can resume by running the script again.")
                    raise
                except Exception as e:
                    logger.error(f"Error processing chunk {i+1}: {e}, continuing to next chunk...")
                    continue

if __name__ == "__main__":
    # 1. Install dependencies if you haven't: pip install neo4j requests
    builder = KnowledgeGraphBuilder()
    try:
        builder.run()
    finally:
        builder.close()
        logger.info("Done. Check http://localhost:7474")