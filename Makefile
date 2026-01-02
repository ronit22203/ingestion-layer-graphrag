.PHONY: help install clean test test-processors test-embedder test-qdrant run logs docker-up docker-down docker-logs inspect neo4j-build neo4j-delete neo4j-stats

# Default target
help:
	@echo "Medical Data Ingestion Pipeline - Makefile Commands"
	@echo "======================================================"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install          Install dependencies from requirements.txt"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-processors  Test cleaner & chunker on markdown files"
	@echo "  make test-embedder    Test embedder (clean -> chunk -> embed -> qdrant)"
	@echo "  make test-qdrant      Test Qdrant connection & collection management"
	@echo ""
	@echo "Pipeline Execution (5 Stages):"
	@echo "  make run              Run full 5-stage pipeline"
	@echo "    Stage 1: PDF → OCR JSON (Surya)"
	@echo "    Stage 2: OCR JSON → Markdown (Converter)"
	@echo "    Stage 3: Markdown → Cleaned (Cleaner)"
	@echo "    Stage 4: Cleaned → Chunks (Chunker)"
	@echo "    Stage 5: Chunks → Vectors (Vectorizer → Qdrant)"
	@echo ""
	@echo "Pipeline Options:"
	@echo "  make run SKIP=ocr     Skip OCR stage"
	@echo "  make run SKIP=convert Skip conversion stage"
	@echo "  make run SKIP=clean   Skip cleaning stage"
	@echo "  make run SKIP=chunk   Skip chunking stage"
	@echo "  make run SKIP=vectorize Skip vectorization stage"
	@echo ""
	@echo "Pipeline Inspection:"
	@echo "  make inspect          Inspect pipeline outputs (all stages)"
	@echo ""
	@echo "Qdrant Management:"
	@echo "  make docker-up        Start Qdrant in Docker"
	@echo "  make docker-down      Stop Qdrant"
	@echo "  make docker-logs      View Qdrant logs"
	@echo "  make qdrant-clear     Clear embeddings"
	@echo "  make qdrant-delete    Delete collection"
	@echo ""
	@echo "Neo4j Knowledge Graph:"
	@echo "  make neo4j-build      Build knowledge graph from chunks"
	@echo "  make neo4j-delete     Delete all graph data"
	@echo "  make neo4j-stats      Show graph statistics"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove cache & logs"
	@echo "  make clean-all        Reset all data folders & pipeline outputs"
	@echo ""

# Installation
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "✓ Installation complete"

# Testing
test: test-processors test-qdrant
	@echo "✓ All tests completed"

test-processors:
	@echo "Running Processors Test (Cleaner & Chunker)..."
	python tests/test_processors.py

test-embedder:
	@echo "Running Embedder Test (Vectorizer)..."
	python tests/test_embedder.py

test-qdrant:
	@echo "Running Qdrant Client Test..."
	python tests/test_qdrant.py

# Pipeline Execution (5 Stages with traceability)
run:
	@echo "Running Medical Data Ingestion Pipeline..."
	@echo "  Input:  data/raw/"
	@echo "  Output: data/ocr/, data/markdown/, data/cleaned/, data/chunks/"
	@echo ""
ifdef SKIP
	python scripts/run_pipeline.py --skip-$(SKIP)
else
	python scripts/run_pipeline.py
endif
	@echo "✓ Pipeline complete - Check logs/ingestion.log"

inspect:
	@echo "Inspecting pipeline outputs..."
	python scripts/inspect_pipeline.py

# Docker / Qdrant Management
docker-up:
	@echo "Starting Qdrant container..."
	docker-compose -f infra/docker-compose.yaml up -d
	@echo "✓ Qdrant started (http://localhost:6333)"
	@sleep 2
	python tests/test_qdrant.py

docker-down:
	@echo "Stopping Qdrant container..."
	docker-compose -f infra/docker-compose.yaml down
	@echo "✓ Qdrant stopped"

docker-logs:
	@echo "Qdrant logs:"
	docker-compose -f infra/docker-compose.yaml logs -f qdrant

qdrant-clear:
	@echo "Clearing Qdrant collection..."
	python src/storage/qdrant_manager.py clear

qdrant-delete:
	@echo "Deleting Qdrant collection..."
	python src/storage/qdrant_manager.py delete

# Neo4j Management
neo4j-build:
	@echo "Building knowledge graph from chunks..."
	python scripts/build_knowledge_graph.py

neo4j-delete:
	@echo "Deleting knowledge graph data..."
	python scripts/delete_knowledge_graph.py

neo4j-stats:
	@echo "Getting knowledge graph statistics..."
	python -c "from scripts.delete_knowledge_graph import KnowledgeGraphDeleter; deleter = KnowledgeGraphDeleter(); import atexit; atexit.register(deleter.close); deleter.get_graph_stats()"

# Cleanup
clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -f logs/*.log
	@echo "✓ Cleanup complete"

clean-all: clean
	@echo "Resetting all pipeline data..."
	rm -rf data/raw/* data/ocr/* data/markdown/* data/cleaned/* data/chunks/* 2>/dev/null || true
	@echo "✓ All data reset complete"

.SILENT: help
