# Processing Stage Documentation

## Overview

The processing stage cleans and chunks Markdown documents with a focus on preserving semantic context. This stage consists of two components:

1. **TextCleaner** - Normalizes and cleans Markdown
2. **MarkdownChunker** - Hierarchically splits documents while preserving context

## TextCleaner

Located in `src/processors/cleaner.py`, this class removes artifacts from the extraction stage and normalizes text.

### Usage

```python
from src.processors.cleaner import TextCleaner

cleaner = TextCleaner()
cleaned_text = cleaner.clean(raw_markdown)
```

### Cleaning Rules

#### Rule 1: Remove Phantom Citation Links

**Problem**: Marker sometimes converts citations `[1]` into dead links `[](1)`

**Solution**: Regex removes all `[](...)` patterns

```python
# Before: "Smith et al. [](citation) showed..."
# After:  "Smith et al. showed..."
```

#### Rule 2: Linearize Markdown Tables

**Problem**: Markdown tables break RAG retrieval because each cell is isolated

**Solution**: Convert tables to key-value text format

```markdown
# Before
| Drug      | Dosage | Side Effects  |
|-----------|--------|---------------|
| Aspirin   | 500mg  | Headache      |
| Ibuprofen | 200mg  | Nausea        |

# After
Drug: Aspirin, Dosage: 500mg, Side Effects: Headache
Drug: Ibuprofen, Dosage: 200mg, Side Effects: Nausea
```

The linearization intelligently handles:
- Header rows (preserves column names)
- Data rows (creates key-value pairs)
- Separator rows (skips them)

#### Rule 3: Merge Hyphenated Words

**Problem**: PDF OCR splits words across lines: "treat-\nment" 

**Solution**: Regex merges split words

```python
# Before: "The drug showed improve-\nment"
# After:  "The drug showed improvement"
```

#### Rule 4: Collapse Multiple Newlines

**Problem**: Excessive whitespace creates structural noise

**Solution**: Reduce 3+ newlines to 2 (preserve paragraph breaks)

```python
# Before: "Conclusion.\n\n\n\n## References"
# After:  "Conclusion.\n\n## References"
```

### Implementation Details

```python
def clean(self, text: str) -> str:
    # 1. Remove phantom images from Marker
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    
    # 2. Remove phantom citation links like [](1), [](citation)
    text = re.sub(r'\[\]\([^)]*\)', '', text)
    
    # 3. Linearize markdown tables
    text = self._linearize_tables(text)
    
    # 4. Fix broken hyphens
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    
    # 5. Collapse multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
```

### Testing

```bash
make test-processors
```

Output shows:
- Original vs cleaned text length
- Sample of cleaned output
- Cleaning effectiveness metrics

## MarkdownChunker

Located in `src/processors/chunker.py`, this class implements context-aware hierarchical chunking.

### Problem Statement

Standard RAG chunking splits documents by token count (e.g., 500 tokens):

```python
# Standard RAG approach
chunk_1 = text[0:500]      # May end mid-sentence
chunk_2 = text[500:1000]   # May start mid-thought
```

This breaks semantic coherence. The LLM retrieves a chunk about "Efficacy Results" but doesn't know what drug or trial context it refers to.

### Solution: Context-Aware Hierarchical Chunking

Our chunker:
1. Respects document structure (headers, lists, code)
2. Prepends full breadcrumb context to each chunk
3. Never splits atomic blocks
4. Maintains semantic coherence

### Usage

```python
from src.processors.chunker import MarkdownChunker

chunker = MarkdownChunker(max_tokens=512)
chunks = chunker.chunk(markdown_text)

# Output: List of dicts with content, context, level
for chunk in chunks:
    print(f"Context: {chunk['context']}")
    print(f"Content: {chunk['content'][:200]}")
```

### Algorithm: Four-Step Process

#### Step 1: Parse Document Structure

Scans for header lines and builds a tree structure representing document hierarchy.

#### Step 2: Evaluate Section Size

Estimates tokens using rough approximation (1 token ~ 4 characters). Small sections (<512 tokens) are kept whole.

#### Step 3: Handle Large Sections

Large sections are split by paragraphs while preserving context and protecting atomic blocks.

#### Step 4: Build Final Chunks with Context

Each chunk gets prepended with full header breadcrumb for semantic context.

### Chunking Rules

**Rule A: Atomic Blocks**

Never split:
- Markdown lists (-, *, +, or numbered)
- Code blocks (```...```)
- Mathematical formulas
- Quoted text blocks

**Rule B: Whole Sections**

Keep <512 token sections intact to preserve coherence.

**Rule C: Context Prepending**

Every chunk includes full header breadcrumb:

```
Context: Clinical Studies > Results > Primary Endpoint

The trial enrolled 250 patients...
```

### Examples

#### Example 1: Medical Paper with Context

Input:
```markdown
# Efficacy of Drug X

## Methods

Study design involved...

## Results

### Primary Endpoint

The primary endpoint was met with p < 0.05.
```

Output chunks include:
```python
{
    'content': 'Context: Efficacy of Drug X > Results > Primary Endpoint\n\nThe primary endpoint was met...',
    'context': 'Efficacy of Drug X > Results > Primary Endpoint',
    'level': 3
}
```

#### Example 2: Protecting Atomic Blocks

Input:
```markdown
## Contraindications

- Do not use with hepatic impairment
- Avoid in pregnancy
- Contraindicated with certain medications
```

Output (list is never split):
```python
{
    'content': 'Context: Clinical Studies > Contraindications\n\n- Do not use...',
    'context': 'Clinical Studies > Contraindications',
    'level': 2
}
```

### Configuration

From `config/settings.yaml`:

```yaml
vectorization:
  chunk_size: 1500          # Max tokens per chunk
  chunk_overlap: 300        # Overlap between chunks
  headers_to_split: ["#", "##", "###"]  # Header levels to preserve
```

### Performance

For a typical 50-page medical paper:
- Parsing: <100ms
- Chunking: 500-1000ms
- Total overhead: <2 seconds

### Testing

```bash
make test-processors
```

Shows:
- Input markdown statistics
- Number of chunks created
- Sample chunks with context
- Estimated token distribution

## Integration with Pipeline

```
Markdown Input (from PDFMarkerExtractor)
   |
   v
[TextCleaner]
   - Remove phantom links
   - Linearize tables
   - Merge hyphenated words
   |
   v
Cleaned Markdown
   |
   v
[MarkdownChunker]
   - Parse structure
   - Respect headers
   - Prepend context
   - Split intelligently
   |
   v
Context-Aware Chunks
   |
   v
[Vectorization (see storage.md)]
```

## Limitations and Future Improvements

Current limitations:
- Header detection is basic (only # patterns)
- Token estimation is rough
- No special handling for very long paragraphs

Planned improvements:
- Configurable context format
- Support for different header styles
- Chunk overlap implementation
- Automatic chunk size optimization
- Semantic similarity-based splitting
