import subprocess
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any
from .base import BaseExtractor

# Setup precise logging
logger = logging.getLogger(__name__)

class PDFMarkerExtractor(BaseExtractor):
    """
    Wrapper for the 'marker' CLI tool to convert PDF to Markdown.
    """
    
    def __init__(self, output_dir: str = "data/interim"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract(self, file_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Executes the marker CLI command.
        
        Equivalent to: 
        marker_single <file_path> --output-dir <output_dir>
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        # Define the output folder for this specific file (Marker creates a subfolder)
        # e.g. data/interim/My_Report/
        stem_name = file_path.stem
        target_folder = self.output_dir / stem_name
        
        # Command construction
        cmd = [
            "marker_single",
            str(file_path),
            "--output_dir", str(self.output_dir)
        ]

        logger.info(f"Extracting {file_path.name} using Marker...")

        try:
            # Prepare environment with KMP_DUPLICATE_LIB_OK for macOS OpenMP conflicts
            env = os.environ.copy()
            env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
            
            # Execute command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,  # Raises CalledProcessError on non-zero exit code
                env=env
            )
            
            # Locate the result file
            # Marker usually outputs to: output_dir / <filename_stem> / <filename_stem>.md
            expected_md_file = target_folder / f"{stem_name}.md"
            expected_meta_file = target_folder / f"{stem_name}_meta.json"

            if not expected_md_file.exists():
                raise FileNotFoundError(f"Marker finished but MD file missing: {expected_md_file}")

            # Read the generated markdown
            with open(expected_md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Read metadata if available (Marker produces OCR stats)
            metadata = {}
            if expected_meta_file.exists():
                with open(expected_meta_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

            logger.info(f"Successfully extracted: {file_path.name}")
            
            return {
                "content": content,
                "metadata": {
                    "source": str(file_path),
                    "extractor": "marker",
                    "ocr_stats": metadata
                }
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Marker failed for {file_path.name}.\nStderr: {e.stderr}")
            raise RuntimeError(f"Extraction failed: {e.stderr}")
