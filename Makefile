.PHONY: help install clean test test-cleaner test-chunker test-embedder test-qdrant run logs docker-up docker-down

# Default target
help:
	@echo "Medical Data Ingestion Pipeline - Makefile Commands"
	@echo "===================================================="
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
	@echo "Pipeline Execution:"
	@echo "  make run              Run full ingestion pipeline"
	@echo "  make extract          Extract PDFs to markdown (Step 1)"
	@echo "  make vectorize        Vectorize markdown files (Step 3)"
	@echo ""
	@echo "Qdrant Management:"
	@echo "  make docker-up        Start Qdrant in Docker (docker-compose up -d)"
	@echo "  make docker-down      Stop Qdrant (docker-compose down)"
	@echo "  make docker-logs      View Qdrant logs"
	@echo "  make qdrant-clear     Clear all embeddings in collection"
	@echo "  make qdrant-delete    Delete entire collection"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove processed files & __pycache__"
	@echo "  make clean-all        Clean + reset data folders"
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

# Pipeline Execution
run:
	@echo "Running full ingestion pipeline..."
	@echo "  Step 1: Extract PDFs to Markdown"
	python scripts/run_pipeline.py
	@echo "✓ Pipeline complete"

extract:
	@echo "Running PDF extraction (pdf_marker)..."
	python -c "from src.extractors.pdf_marker import PDFMarkerExtractor; from pathlib import Path; e = PDFMarkerExtractor('data/interim'); [e.extract(f) for f in Path('data/raw').glob('*.pdf')]"

vectorize:
	@echo "Vectorizing markdown files..."
	python src/storage/embedder.py

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
	python src/storage/qdrant_client.py clear

qdrant-delete:
	@echo "Deleting Qdrant collection..."
	python src/storage/qdrant_client.py delete

# Cleanup
clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -f logs/*.log
	@echo "✓ Cleanup complete"

clean-all: clean
	@echo "Resetting data folders..."
	rm -rf data/interim/* data/processed/* 
	@echo "✓ Full reset complete"

.SILENT: help
