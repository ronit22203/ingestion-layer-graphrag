import os
import uuid
from typing import List, Dict, Any
from pathlib import Path
import yaml
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Use our custom cleaner and chunker
from src.processors.cleaner import TextCleaner
from src.processors.chunker import MarkdownChunker

# Import embedding model
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError("Please install sentence-transformers: pip install sentence-transformers")


class ConfigLoader:
    """Load configuration from YAML file"""
    @staticmethod
    def load(config_path: str = None) -> Dict[str, Any]:
        if config_path is None:
            # Find settings.yaml in project root config/ directory
            script_file = Path(__file__).resolve()
            project_root = script_file.parent.parent.parent  # src/storage/embedder.py -> root
            config_path = project_root / "config" / "settings.yaml"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)


class MedicalVectorizer:
    def __init__(self, config: Dict[str, Any] = None, collection_name: str = None):
        if config is None:
            config = ConfigLoader.load()
        
        self.config = config
        self.project_root = Path(__file__).parent.parent.parent
        
        # Get vectorization config
        vec_config = config.get('vectorization', {})
        
        # Set collection name (from param > config > default)
        self.collection_name = collection_name or vec_config.get('collection_name', 'medical_papers')
        
        # 1. Connect to Qdrant
        qdrant_url = vec_config.get('qdrant_url', 'http://localhost:6333')
        print(f"Connecting to Qdrant at {qdrant_url}...")
        self.client = QdrantClient(url=qdrant_url)
        
        # 2. Load Embedding Model
        model_name = vec_config.get('model_name', 'BAAI/bge-small-en-v1.5')
        print(f"Loading embedding model: {model_name}")
        self.embedding_model = SentenceTransformer(model_name)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        
        # 3. Initialize cleaner and chunker
        self.cleaner = TextCleaner()
        self.chunker = MarkdownChunker(max_tokens=vec_config.get('chunk_size', 512))

        # 4. Create Collection (Idempotent)
        if not self.client.collection_exists(self.collection_name):
            print(f"Creating collection '{self.collection_name}' with {self.embedding_dim} dimensions...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE)
            )
        else:
            print(f"Collection '{self.collection_name}' already exists")

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve paths relative to project root"""
        return self.project_root / relative_path

    def process_file(self, file_path: str):
        """
        Reads a single Markdown file -> Clean -> Chunk -> Embed -> Qdrant
        Uses custom TextCleaner and MarkdownChunker for optimal processing
        """
        file_path = Path(file_path)
        print(f"Vectorizing: {file_path.name}")

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Step 1: Clean the markdown
        cleaned_text = self.cleaner.clean(text)
        
        # Step 2: Context-aware chunking
        chunks = self.chunker.chunk(cleaned_text)
        
        if not chunks:
            print("No chunks generated from file.")
            return
        
        # Step 3: Generate embeddings and prepare points for Qdrant
        points = []
        vec_config = self.config.get('vectorization', {})
        batch_size = vec_config.get('batch_size', 64)
        
        for i, chunk in enumerate(chunks):
            # Embed the chunk content
            embedding = self.embedding_model.encode(chunk['content']).tolist()
            
            # Prepare metadata
            metadata = {
                'source': file_path.name,
                'context': chunk['context'],
                'level': chunk['level'],
                'chunk_index': i,
                'page_number': chunk.get('page_number', 1)
            }
            
            # Create Qdrant point
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=metadata
            )
            points.append(point)
        
        # Step 4: Upsert to Qdrant (Batched)
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
        
        print(f"✓ Indexed {len(points)} chunks from {file_path.name}")

    def run(self, input_dir_path: str = None):
        """
        Recursively finds all .md files in the directory and processes them.
        If input_dir_path is None, uses the path from config.
        """
        if input_dir_path is None:
            vec_config = self.config.get('vectorization', {})
            # Use interim directory (where markdown files are after extraction)
            input_dir_path = self._resolve_path(vec_config.get('input_dir', 'data/interim'))
        
        input_dir_path = Path(input_dir_path)
        if not input_dir_path.exists():
            print(f"Directory not found: {input_dir_path}")
            return

        print(f"Scanning: {input_dir_path}")
        found_files = False
        
        # Walk through the directory to handle nested folders
        for md_file in input_dir_path.rglob("*.md"):
            found_files = True
            self.process_file(str(md_file))
        
        if not found_files:
            print("No .md files found in the input directory.")

# --- Execution ---
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vectorize markdown documents using Qdrant")
    parser.add_argument('-c', '--config', help='Path to settings.yaml file')
    parser.add_argument('-i', '--input-dir', help='Input directory with markdown files')
    
    args = parser.parse_args()
    
    try:
        config = ConfigLoader.load(args.config) if args.config else ConfigLoader.load()
        vectorizer = MedicalVectorizer(config=config)
        vectorizer.run(args.input_dir)
        print("✓ Vectorization complete")
    except Exception as e:
        print(f"✗ Error during vectorization: {e}")
        raise
