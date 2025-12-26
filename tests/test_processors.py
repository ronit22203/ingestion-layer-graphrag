#!/usr/bin/env python
"""
Test script for TextCleaner and MarkdownChunker
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processors.cleaner import TextCleaner
from src.processors.chunker import MarkdownChunker

if __name__ == "__main__":
    import yaml
    
    # Load config from settings.yaml
    config_path = project_root / "config" / "settings.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Load test markdown file from interim folder (as per settings.yaml)
    interim_dir = project_root / config['preprocessing']['input_dir']
    
    # Find the first .md file in interim folder
    md_files = list(interim_dir.rglob("*.md"))
    
    if not md_files:
        print(f"✗ No markdown files found in: {interim_dir}")
        print("\nTesting with sample data instead...\n")
        md_file = None
        
        # Sample test data
        sample_text = """# Clinical Studies

## Contraindications

Do not use in patients with [](hypersensitivity).

| Drug | Dosage |
|------|--------|
| Med-A | 5mg |
| Med-B | 10mg |

The drug showed significant improve-
ment in symptoms.


## Efficacy Results

### Phase 2 Trial
Treatment showed 50% improvement compared to placebo.

### Phase 3 Trial  
- Primary endpoint met
- Secondary endpoints pending
- Safety profile acceptable
"""
    else:
        md_file = md_files[0]
        print(f"✓ Found markdown file: {md_file.relative_to(project_root)}")
        with open(md_file, 'r', encoding='utf-8') as f:
            sample_text = f.read()
    
    print("\n" + "="*60)
    print("TESTING TEXT CLEANER")
    print("="*60 + "\n")
    
    cleaner = TextCleaner()
    cleaned = cleaner.clean(sample_text)
    
    print(f"Original length: {len(sample_text)} characters")
    print(f"Cleaned length:  {len(cleaned)} characters")
    print(f"\nFirst 500 chars of cleaned text:")
    print("-" * 60)
    print(cleaned[:500])
    print("-" * 60)
    
    print("\n" + "="*60)
    print("TESTING MARKDOWN CHUNKER")
    print("="*60 + "\n")
    
    chunker = MarkdownChunker(max_tokens=512)
    chunks = chunker.chunk(cleaned)
    
    print(f"Total chunks created: {len(chunks)}\n")
    
    # Show first 3 chunks
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"--- Chunk {i} ---")
        print(f"Context: {chunk['context']}")
        print(f"Level: H{chunk['level']}")
        print(f"Content preview: {chunk['content'][:200]}...")
        print(f"Estimated tokens: {len(chunk['content']) // 4}")
        print()
    
    if len(chunks) > 3:
        print(f"... and {len(chunks) - 3} more chunks")
    
    print("\n✓ Processor tests completed!")
