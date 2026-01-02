#!/usr/bin/env python3
"""
Medical Data Ingestion Pipeline - Main Entry Point
Orchestrates the complete pipeline: 
  PDF -> Surya OCR (_ocr.json) -> Converter (_converted.md) -> Cleaner (_cleaned.md) -> Chunker (_chunks.json) -> Vectorizer
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
import yaml

# Get project root (1 level up from this script: scripts/run_pipeline.py)
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extractors.pdf_marker_v2 import initialize_models, load_pdf_images, serialize_surya_results
from src.extractors.surya_converter import SuryaToMarkdown
from src.processors.cleaner import TextCleaner
from src.processors.chunker import MarkdownChunker
from src.storage.embedder import MedicalVectorizer, ConfigLoader


class PipelineLogger:
    """Setup and manage logging for the pipeline with comprehensive traceability"""
    
    @staticmethod
    def setup(log_file: str) -> logging.Logger:
        """Setup dual logging: console (INFO) and file (DEBUG)"""
        logger = logging.getLogger("pipeline")
        logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Console handler (INFO level - user friendly)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # File handler (DEBUG level - comprehensive)
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Rich formatter with timestamps and colors for console
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Detailed formatter for file (includes function info)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler.setFormatter(console_formatter)
        file_handler.setFormatter(file_formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        # Configure child loggers (for imported modules)
        logging.getLogger('src').setLevel(logging.DEBUG)
        logging.getLogger('presidio_analyzer').setLevel(logging.WARNING)  # Reduce noise
        logging.getLogger('presidio_anonymizer').setLevel(logging.WARNING)
        
        # Add file header
        logger.info("="*80)
        logger.info("MEDICAL DATA INGESTION PIPELINE - LOG START")
        logger.info("="*80)
        
        return logger


class MedicalDataPipeline:
    """Main pipeline orchestrator with full traceability"""
    
    def __init__(self, config_path: str = None):
        """Initialize pipeline with configuration"""
        if config_path is None:
            config_path = PROJECT_ROOT / "config" / "settings.yaml"
        
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.project_root = PROJECT_ROOT
        self.log_file = self.project_root / self.config.get('log_file', 'logs/ingestion.log')
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.logger = PipelineLogger.setup(str(self.log_file))
        
        # Resolve paths from config - organized logically
        self.input_dir = self._resolve_path(self.config.get('input_dir', 'data/raw'))
        
        # Processing stages from config.output
        output_config = self.config.get('output', {})
        self.ocr_dir = self._resolve_path(output_config.get('ocr_dir', 'data/ocr'))
        self.markdown_dir = self._resolve_path(output_config.get('markdown_dir', 'data/markdown'))
        self.cleaned_dir = self._resolve_path(output_config.get('cleaned_dir', 'data/cleaned'))
        self.chunks_dir = self._resolve_path(output_config.get('chunks_dir', 'data/chunks'))
        
        # Create all necessary directories
        for directory in [self.input_dir, self.ocr_dir, self.markdown_dir,
                          self.cleaned_dir, self.chunks_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve paths relative to project root"""
        if relative_path.startswith('/'):
            return Path(relative_path)
        return self.project_root / relative_path
    
    def log_header(self, text: str):
        """Log section header"""
        header = "=" * 60
        self.logger.info("")
        self.logger.info(header)
        self.logger.info(text)
        self.logger.info(header)
    
    def run(self, input_dir: str = None, skip_ocr: bool = False, skip_convert: bool = False,
            skip_clean: bool = False, skip_chunk: bool = False, skip_vectorize: bool = False):
        """Run the complete pipeline"""
        self.log_header("Medical Data Ingestion Pipeline Started")
        self.logger.info(f"Config: {self.config_path}")
        self.logger.info(f"Input:  {self.input_dir}")
        self.logger.info(f"Pipeline outputs:")
        self.logger.info(f"  OCR:      {self.ocr_dir}")
        self.logger.info(f"  Markdown: {self.markdown_dir}")
        self.logger.info(f"  Cleaned:  {self.cleaned_dir}")
        self.logger.info(f"  Chunks:   {self.chunks_dir}")
        self.logger.info(f"Log:    {self.log_file}")
        self.logger.info(f"Timestamp: {datetime.now().strftime('%a %b %d %H:%M:%S %Z %Y')}")
        
        # Override input dir if provided
        if input_dir:
            self.input_dir = self._resolve_path(input_dir)
        
        if not self.input_dir.exists():
            self.logger.error(f"Input directory not found: {self.input_dir}")
            return False
        
        # Find PDFs
        pdf_files = list(self.input_dir.glob("**/*.pdf"))
        if not pdf_files:
            self.logger.warning(f"No PDF files found in {self.input_dir}")
            return True
        
        self.logger.info(f"Found {len(pdf_files)} PDF file(s) to process")
        self.logger.info("")
        
        successful = 0
        failed = 0
        failed_files = []
        
        # Load models once for all PDFs (significant time savings)
        if not skip_ocr:
            self.logger.info("Initializing Surya OCR models...")
            try:
                ocr_config = self.config.get('ocr', {})
                device = ocr_config.get('device', 'mps')
                self.predictors = initialize_models(device=device)
            except Exception as e:
                self.logger.error(f"Failed to initialize models: {e}")
                return False
        
        # Process each PDF
        for idx, pdf_file in enumerate(pdf_files, 1):
            self.logger.info("")
            self.logger.info(f"[{idx}/{len(pdf_files)}] Processing: {pdf_file.name}")
            
            filename = pdf_file.stem
            
            try:
        # Stage 1: PDF to OCR JSON (Surya)
                if not skip_ocr:
                    self.logger.info(f"  Stage 1/5: PDF → OCR JSON (Surya)")
                    ocr_json_path = self._stage1_ocr(pdf_file, filename)
                    self.logger.info(f"  ✓ OCR complete: {ocr_json_path.name}")
                else:
                    self.logger.info(f"  Stage 1/5: Skipped (--skip-ocr)")
                    ocr_json_path = self.ocr_dir / f"{filename}_ocr.json"
                
                # Stage 2: OCR JSON to Markdown (Surya Converter)
                if not skip_convert:
                    self.logger.info(f"  Stage 2/5: OCR JSON → Markdown")
                    converted_md_path = self._stage2_convert(ocr_json_path, filename)
                    self.logger.info(f"  ✓ Conversion complete: {converted_md_path.name}")
                else:
                    self.logger.info(f"  Stage 2/5: Skipped (--skip-convert)")
                    converted_md_path = self.markdown_dir / f"{filename}_converted.md"
                
                # Stage 3: Clean Markdown
                if not skip_clean:
                    self.logger.info(f"  Stage 3/5: Markdown → Cleaned")
                    cleaned_md_path = self._stage3_clean(converted_md_path, filename)
                    self.logger.info(f"  ✓ Cleaning complete: {cleaned_md_path.name}")
                else:
                    self.logger.info(f"  Stage 3/5: Skipped (--skip-clean)")
                    cleaned_md_path = self.cleaned_dir / f"{filename}_cleaned.md"
                
                # Stage 4: Chunk Markdown
                if not skip_chunk:
                    self.logger.info(f"  Stage 4/5: Markdown → Chunks")
                    chunks_json_path = self._stage4_chunk(cleaned_md_path, filename)
                    self.logger.info(f"  ✓ Chunking complete: {chunks_json_path.name}")
                else:
                    self.logger.info(f"  Stage 4/5: Skipped (--skip-chunk)")
                
                successful += 1
                
            except Exception as e:
                self.logger.error(f"  ✗ Failed processing {filename}: {e}")
                import traceback
                self.logger.error(f"  Traceback: {traceback.format_exc()}")
                failed += 1
                failed_files.append(filename)
        
        # Stage 5: Vectorization (once for all files)
        if not skip_vectorize and (successful > 0 or not skip_clean):
            self.logger.info("")
            self.logger.info("Stage 5/5: Vectorization (Embed & Index)")
            try:
                self._stage5_vectorize()
                self.logger.info("✓ Vectorization complete")
            except Exception as e:
                self.logger.error(f"✗ Vectorization failed: {e}")
                import traceback
                self.logger.error(f"  Traceback: {traceback.format_exc()}")
        elif skip_vectorize:
            self.logger.info("")
            self.logger.info("Stage 5/5: Skipped (--skip-vectorize)")
        
        # Summary
        self.log_header("Pipeline Complete")
        self.logger.info(f"Processed: {successful}/{len(pdf_files)} successful")
        if failed > 0:
            self.logger.warning(f"Failed: {failed} file(s)")
            for f in failed_files:
                self.logger.warning(f"  - {f}")
        self.logger.info("")
        self.logger.info("Output locations:")
        self.logger.info(f"  OCR JSONs:    {self.ocr_dir}")
        self.logger.info(f"  Markdown:     {self.markdown_dir}")
        self.logger.info(f"  Cleaned:      {self.cleaned_dir}")
        self.logger.info(f"  Chunks:       {self.chunks_dir}")
        self.logger.info(f"Log: {self.log_file}")
        
        return failed == 0
    
    def _stage1_ocr(self, pdf_file: Path, filename: str) -> Path:
        """Stage 1: PDF -> OCR JSON using Surya"""
        pdf_ocr_dir = self.ocr_dir / filename
        pdf_ocr_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Convert PDF to images
            images = load_pdf_images(str(pdf_file))
            self.logger.info(f"    • Rendered {len(images)} pages")
            
            # Run OCR
            detection_predictor = self.predictors["detection"]
            recognition_predictor = self.predictors["recognition"]
            
            results = []
            for i, image in enumerate(images):
                self.logger.debug(f"    • OCR page {i + 1}/{len(images)}")
                
                # Detection
                detection_result = detection_predictor([image])
                
                # Convert polygons to bboxes
                bboxes = []
                for poly_box in detection_result[0].bboxes:
                    if hasattr(poly_box, 'polygon') and len(poly_box.polygon) > 0:
                        xs = [p[0] for p in poly_box.polygon]
                        ys = [p[1] for p in poly_box.polygon]
                        bbox = [[min(xs), min(ys), max(xs), max(ys)]]
                        bboxes.extend(bbox)
                
                # Recognition
                if bboxes:
                    recognition_result = recognition_predictor(images=[image], bboxes=[bboxes])
                    results.append(recognition_result[0])
            
            # Serialize results
            json_output = serialize_surya_results(results)
            
            # Save OCR JSON
            ocr_json_path = self.ocr_dir / f"{filename}_ocr.json"
            with open(ocr_json_path, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"    • Saved OCR JSON: {ocr_json_path.name}")
            
            # Save debug visualizations
            self._save_debug_images(images, results, pdf_ocr_dir, filename)
            
            return ocr_json_path
            
        except Exception as e:
            raise RuntimeError(f"Stage 1 (OCR) failed: {str(e)}")
    
    def _save_debug_images(self, images, results, output_dir, filename):
        """Save debug visualization images with OCR boxes"""
        from PIL import ImageDraw
        
        debug_dir = output_dir / "debug_visualizations"
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        for i, (image, result) in enumerate(zip(images, results)):
            image_copy = image.copy()
            draw = ImageDraw.Draw(image_copy)
            
            # Draw bounding boxes
            for line in result.text_lines:
                box = line.bbox
                confidence = line.confidence
                color = "green" if confidence >= 0.80 else "red"
                draw.rectangle(box, outline=color, width=2)
            
            # Save debug image
            debug_image_path = debug_dir / f"{filename}_page_{i+1:03d}_debug.png"
            image_copy.save(debug_image_path)
            self.logger.debug(f"    • Saved debug image: {debug_image_path.name}")
    
    def _stage2_convert(self, ocr_json_path: Path, filename: str) -> Path:
        """Stage 2: OCR JSON -> Markdown using SuryaToMarkdown"""
        try:
            # Load OCR JSON
            with open(ocr_json_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            # Convert to markdown
            converter = SuryaToMarkdown()
            markdown_output = converter.convert(ocr_data)
            
            # Save converted markdown
            converted_md_path = self.markdown_dir / f"{filename}_converted.md"
            with open(converted_md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_output)
            
            self.logger.info(f"    • Converted markdown size: {len(markdown_output)} chars")
            
            return converted_md_path
            
        except Exception as e:
            raise RuntimeError(f"Stage 2 (Conversion) failed: {str(e)}")
    
    def _stage3_clean(self, converted_md_path: Path, filename: str) -> Path:
        """Stage 3: Clean Markdown"""
        try:
            # Read converted markdown
            with open(converted_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_size = len(content)
            
            # Clean
            cleaner = TextCleaner()
            cleaned = cleaner.clean(content)
            cleaned_size = len(cleaned)
            
            # Save cleaned markdown
            cleaned_md_path = self.cleaned_dir / f"{filename}_cleaned.md"
            with open(cleaned_md_path, 'w', encoding='utf-8') as f:
                f.write(cleaned)
            
            reduction_pct = 100 - (100 * cleaned_size // original_size)
            self.logger.info(f"    • Size reduction: {original_size} → {cleaned_size} chars ({reduction_pct}% removed)")
            
            return cleaned_md_path
            
        except Exception as e:
            raise RuntimeError(f"Stage 3 (Cleaning) failed: {str(e)}")
    
    def _stage4_chunk(self, cleaned_md_path: Path, filename: str) -> Path:
        """Stage 4: Chunk Markdown into JSON with metadata"""
        try:
            # Read cleaned markdown
            with open(cleaned_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Chunk - use config values
            chunk_config = self.config.get('chunking', {})
            max_tokens = chunk_config.get('max_tokens', 500)
            chunk_overlap = chunk_config.get('chunk_overlap', 300)
            
            chunker = MarkdownChunker(max_tokens=max_tokens)
            chunks = chunker.chunk(content)
            
            # Create output with metadata
            output_data = {
                "filename": filename,
                "source_file": cleaned_md_path.name,
                "total_chunks": len(chunks),
                "chunk_config": {
                    "max_tokens": max_tokens,
                    "chunk_overlap": chunk_overlap
                },
                "chunks": chunks
            }
            
            # Save chunks JSON
            chunks_json_path = self.chunks_dir / f"{filename}_chunks.json"
            with open(chunks_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"    • Created {len(chunks)} chunks (config: max_tokens={max_tokens})")
            
            return chunks_json_path
            
        except Exception as e:
            raise RuntimeError(f"Stage 4 (Chunking) failed: {str(e)}")
    
    def _stage5_vectorize(self):
        """Stage 5: Vectorize all cleaned documents"""
        self.logger.info(f"  • Initializing vectorizer...")
        vectorizer = MedicalVectorizer(config=self.config)
        
        self.logger.info(f"  • Model: {self.config.get('vectorization', {}).get('model_name', 'BAAI/bge-small-en-v1.5')}")
        self.logger.info(f"  • Embedding dimension: {vectorizer.embedding_dim}")
        self.logger.info(f"  • Qdrant URL: {self.config.get('vectorization', {}).get('qdrant_url', 'http://localhost:6333')}")
        self.logger.info(f"  • Collection: {vectorizer.collection_name}")
        
        self.logger.info(f"  • Processing: {self.cleaned_dir}")
        vectorizer.run(str(self.cleaned_dir))
        self.logger.info(f"  ✓ Vectorization complete")


def main():
    parser = argparse.ArgumentParser(
        description="Medical Data Ingestion Pipeline - 5 Stages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline Stages:
  1. PDF → OCR JSON     (Surya)
  2. OCR JSON → Markdown (SuryaToMarkdown converter)
  3. Markdown → Cleaned  (TextCleaner)
  4. Cleaned → Chunks   (MarkdownChunker)
  5. Chunks → Vectors   (MedicalVectorizer)

Examples:
  python scripts/run_pipeline.py                      # Run full pipeline
  python scripts/run_pipeline.py --skip-ocr           # Skip OCR only
  python scripts/run_pipeline.py --skip-vectorize     # Skip vectorization
  python scripts/run_pipeline.py --input-dir data/raw # Override input dir
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to config.yaml file (default: config/settings.yaml)'
    )
    parser.add_argument(
        '-i', '--input-dir',
        help='Override input directory for PDFs'
    )
    parser.add_argument(
        '--skip-ocr',
        action='store_true',
        help='Skip stage 1: PDF → OCR JSON'
    )
    parser.add_argument(
        '--skip-convert',
        action='store_true',
        help='Skip stage 2: OCR JSON → Markdown'
    )
    parser.add_argument(
        '--skip-clean',
        action='store_true',
        help='Skip stage 3: Clean Markdown'
    )
    parser.add_argument(
        '--skip-chunk',
        action='store_true',
        help='Skip stage 4: Chunk Markdown'
    )
    parser.add_argument(
        '--skip-vectorize',
        action='store_true',
        help='Skip stage 5: Vectorization'
    )
    
    args = parser.parse_args()
    
    try:
        pipeline = MedicalDataPipeline(config_path=args.config)
        success = pipeline.run(
            input_dir=args.input_dir,
            skip_ocr=args.skip_ocr,
            skip_convert=args.skip_convert,
            skip_clean=args.skip_clean,
            skip_chunk=args.skip_chunk,
            skip_vectorize=args.skip_vectorize
        )
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

