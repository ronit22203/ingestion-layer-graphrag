#!/usr/bin/env python3
"""
Medical Data Ingestion Pipeline - Main Entry Point
Orchestrates the complete pipeline: PDF -> Markdown -> Clean -> Vectorize
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import yaml
import subprocess

# Get project root (1 level up from this script: ingestion/run.py)
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingestion"))

from preprocesser import process_file, process_directory
from vectorizer import MedicalVectorizer, ConfigLoader


class PipelineLogger:
    """Setup and manage logging for the pipeline"""
    
    @staticmethod
    def setup(log_file: str) -> logging.Logger:
        logger = logging.getLogger("pipeline")
        logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger


class MedicalDataPipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self, config_path: str = None):
        """Initialize pipeline with configuration"""
        if config_path is None:
            config_path = PROJECT_ROOT / "ingestion" / "config.yaml"
        
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.project_root = PROJECT_ROOT
        self.log_file = self.project_root / self.config.get('log_file', 'ingestion.log')
        self.logger = PipelineLogger.setup(str(self.log_file))
        
        # Resolve paths
        self.input_dir = self._resolve_path(self.config.get('input_dir'))
        self.raw_dir = self._resolve_path(
            self.config.get('pdf_to_markdown', {}).get('output_subdir', 'output_docs/raw')
        )
        self.clean_dir = self._resolve_path(
            self.config.get('preprocessing', {}).get('output_dir', 'output_docs/cleaned')
        )
        
        # Create necessary directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.clean_dir.mkdir(parents=True, exist_ok=True)
    
    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve paths relative to project root"""
        if relative_path.startswith('/'):
            return Path(relative_path)
        return self.project_root / relative_path
    
    def log_header(self, text: str):
        """Log section header"""
        header = "=" * 50
        self.logger.info("")
        self.logger.info(header)
        self.logger.info(text)
        self.logger.info(header)
    
    def run(self, input_dir: str = None, skip_ocr: bool = False, skip_clean: bool = False, skip_vectorize: bool = False):
        """Run the complete pipeline"""
        self.log_header("Medical Data Ingestion Pipeline Started")
        self.logger.info(f"Config: {self.config_path}")
        self.logger.info(f"Input:  {self.input_dir}")
        self.logger.info(f"Raw:    {self.raw_dir}")
        self.logger.info(f"Clean:  {self.clean_dir}")
        self.logger.info(f"Log:    {self.log_file}")
        
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
        
        successful = 0
        failed = 0
        
        # Process each PDF
        for pdf_file in pdf_files:
            self.logger.info("")
            self.logger.info(f"Processing: {pdf_file.name}")
            
            filename = pdf_file.stem
            pdf_raw_dir = self.raw_dir / filename
            
            try:
                # Step 1: PDF to Markdown (OCR)
                if not skip_ocr:
                    self._run_ocr(pdf_file, pdf_raw_dir)
                    self.logger.info(f"✓ OCR complete: {filename}")
                
                # Step 2: Preprocessing (Clean Markdown)
                if not skip_clean:
                    self._run_preprocessing(pdf_raw_dir)
                    self.logger.info(f"✓ Preprocessing complete: {filename}")
                
                successful += 1
                
            except Exception as e:
                self.logger.error(f"✗ Failed processing {filename}: {e}", exc_info=True)
                failed += 1
        
        # Step 3: Vectorization (once for all files)
        if not skip_vectorize and successful > 0:
            try:
                self._run_vectorization()
                self.logger.info("✓ Vectorization complete: all files")
            except Exception as e:
                self.logger.error(f"✗ Vectorization failed: {e}", exc_info=True)
        
        # Summary
        self.log_header("Pipeline Complete")
        self.logger.info(f"Processed: {successful}/{len(pdf_files)} successful")
        if failed > 0:
            self.logger.warning(f"Failed: {failed} file(s)")
        self.logger.info(f"Output: {self.clean_dir}")
        self.logger.info(f"Log: {self.log_file}")
        
        return failed == 0
    
    def _run_ocr(self, pdf_file: Path, output_dir: Path):
        """Run PDF to Markdown conversion"""
        output_dir.mkdir(parents=True, exist_ok=True)
        script = self.project_root / "ingestion" / "pdf_to_markdown.sh"
        
        result = subprocess.run(
            [str(script), str(pdf_file), str(output_dir)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"OCR failed: {result.stderr}")
    
    def _run_preprocessing(self, raw_dir: Path):
        """Run markdown preprocessing"""
        if raw_dir.exists() and raw_dir.is_dir():
            process_directory(str(raw_dir), str(self.clean_dir), config=self.config)
    
    def _run_vectorization(self):
        """Run vectorization for all cleaned documents"""
        vectorizer = MedicalVectorizer(config=self.config)
        vectorizer.run(str(self.clean_dir))


def main():
    parser = argparse.ArgumentParser(
        description="Medical Data Ingestion Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/ingestion/run.py                           # Run full pipeline
  python src/ingestion/run.py --config custom.yaml      # Use custom config
  python src/ingestion/run.py --skip-ocr                # Skip OCR, only clean & vectorize
  python src/ingestion/run.py --skip-vectorize          # Skip vectorization
  python src/ingestion/run.py --input-dir /path/to/pdfs # Override input directory
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to config.yaml file (default: src/ingestion/config.yaml)'
    )
    parser.add_argument(
        '-i', '--input-dir',
        help='Override input directory for PDFs'
    )
    parser.add_argument(
        '--skip-ocr',
        action='store_true',
        help='Skip PDF to Markdown conversion'
    )
    parser.add_argument(
        '--skip-clean',
        action='store_true',
        help='Skip preprocessing/cleaning step'
    )
    parser.add_argument(
        '--skip-vectorize',
        action='store_true',
        help='Skip vectorization step'
    )
    
    args = parser.parse_args()
    
    try:
        pipeline = MedicalDataPipeline(config_path=args.config)
        success = pipeline.run(
            input_dir=args.input_dir,
            skip_ocr=args.skip_ocr,
            skip_clean=args.skip_clean,
            skip_vectorize=args.skip_vectorize
        )
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

