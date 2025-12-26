# Extraction Stage Documentation

## Overview

The extraction stage converts PDF documents into clean Markdown format using the Marker library (which internally uses Surya OCR and Pix2Struct table detection).

## PDFMarkerExtractor Class

Located in `src/extractors/pdf_marker.py`, this class wraps the Marker library to provide a consistent interface for PDF processing.

### Usage

```python
from src.extractors.pdf_marker import PDFMarkerExtractor
from pathlib import Path

# Initialize extractor
extractor = PDFMarkerExtractor(output_dir="data/interim")

# Process single PDF
result = extractor.extract(Path("data/raw/paper.pdf"))

# Access results
print(f"Content: {result['content'][:500]}")
print(f"Metadata: {result['metadata']}")
```

### Output Structure

The extractor returns a dictionary with:

```python
{
    'content': str,          # Full markdown text
    'metadata': {
        'filename': str,      # Original filename
        'pages': int,         # Number of pages
        'images': int,        # Number of extracted images
        'tables': int,        # Number of detected tables
        'extraction_time': float  # Processing time in seconds
    },
    'output_file': Path       # Path to saved markdown file
}
```

### File Organization

Extracted files are organized as:

```
data/interim/
├── Document_Title/
│   ├── Document_Title.md      # Main markdown content
│   ├── Document_Title_meta.json  # Metadata JSON
│   └── images/                # Extracted images
│       ├── image_001.png
│       └── image_002.png
```

## What Marker Does

### Text Extraction
- Uses OCR for both digital and scanned PDFs
- Preserves reading order and flow
- Handles multi-column layouts

### Table Detection
- Converts tables to Markdown format
- Preserves table structure
- Detects nested tables

### Image Handling
- Extracts images from PDFs
- Saves with descriptive filenames
- Includes image references in Markdown

### Layout Understanding
- Identifies headers, paragraphs, lists
- Preserves document hierarchy
- Handles mathematical formulas

## Configuration

From `config/settings.yaml`:

```yaml
pdf_to_markdown:
  output_subdir: "data/interim"  # Where to save markdown
  batch_size: 10                 # PDFs to process in parallel
  verbose: true                  # Detailed logging
```

## Performance Characteristics

- **Speed**: 10-20 seconds per 50-page PDF (varies by complexity)
- **Accuracy**: 95-99% on text extraction (depends on PDF quality)
- **Memory**: 2-4GB per process (monitor for large batches)

## Common Issues

### Issue: "marker is not installed"

```bash
pip install marker-pdf
```

### Issue: Out of Memory

Reduce batch size in settings.yaml:

```yaml
batch_size: 5
```

### Issue: Poor OCR Quality

For scanned PDFs with low quality:
1. Consider preprocessing with higher resolution
2. Increase DPI settings if available
3. Check if original PDF is corrupted

## Limitations

1. Complex scientific figures may not extract well (image extraction is literal)
2. Handwritten annotations are not extracted
3. Some embedded objects may be missed
4. Very large documents (1000+ pages) may cause memory issues

## Integration with Pipeline

The extraction stage outputs Markdown that feeds into the processing stage:

```
PDF Input
   |
   v
[PDFMarkerExtractor]
   - OCR text
   - Detect tables
   - Extract images
   |
   v
Markdown Output (data/interim/)
   |
   v
[TextCleaner + MarkdownChunker]
   - Clean phantom links
   - Hierarchical chunking
   |
   v
[Vectorization]
```

## Advanced Usage

### Custom Output Directory

```python
extractor = PDFMarkerExtractor(output_dir="/custom/path")
```

### Batch Processing

```python
from pathlib import Path

extractor = PDFMarkerExtractor(output_dir="data/interim")
pdf_dir = Path("data/raw")

for pdf_file in pdf_dir.glob("*.pdf"):
    result = extractor.extract(pdf_file)
    print(f"Processed: {result['metadata']['filename']}")
```

### Error Handling

```python
try:
    result = extractor.extract(pdf_file)
except FileNotFoundError:
    print(f"PDF not found: {pdf_file}")
except Exception as e:
    print(f"Extraction failed: {e}")
```

## Testing

Test PDF extraction:

```bash
make test-pdf
# Or
python tests/test_pdf_marker.py
```

This verifies:
- PDF file exists
- Marker library is installed
- Extraction produces valid Markdown
- Output directory structure is correct
