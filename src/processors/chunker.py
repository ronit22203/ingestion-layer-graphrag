import re
from typing import List, Dict

class MarkdownChunker:
    """Context-aware hierarchical chunker for medical markdown documents."""
    
    def __init__(self, max_tokens: int = 512):
        """
        Args:
            max_tokens: Maximum tokens per chunk (rough estimate: 1 token ≈ 4 chars)
        """
        self.max_tokens = max_tokens
    
    def chunk(self, text: str) -> List[Dict[str, str]]:
        """
        Split markdown into context-aware chunks.
        
        Returns:
            List of dicts with 'content', 'context', and 'level' keys
        """
        sections = self._parse_sections(text)
        chunks = []
        
        # Fallback: If no sections found (no headers), create a dummy section to force splitting
        if not sections and text.strip():
            sections = [{
                'context_path': 'Document Body',
                'level': 1,
                'content': text,
                'page_number': 1
            }]
        
        for section in sections:
            chunk_text = self._build_chunk_with_context(section)
            
            # Rule B: If section <512 tokens, keep it whole
            if self._estimate_tokens(chunk_text) <= self.max_tokens:
                chunks.append({
                    'content': chunk_text,
                    'context': section['context_path'],
                    'level': section['level'],
                    'page_number': section.get('page_number', 1)
                })
            else:
                # Split large sections while preserving context
                chunks.extend(self._split_large_section(section))
        
        return chunks
    
    def _parse_sections(self, text: str) -> List[Dict]:
        """Parse markdown into hierarchical sections (the tree structure)."""
        lines = text.split('\n')
        sections = []
        current_headers = ['', '', '', '']  # H1, H2, H3, H4
        current_content = []
        current_level = 0
        current_page_number = 1  # Default to page 1
        
        for line in lines:
            # Step 0: Check for page markers - treat as mandatory section breaks
            page_match = re.match(r'^<!--\s*PAGE:\s*(\d+)\s*-->$', line)
            if page_match:
                # Save previous section if we have content
                if current_content:
                    sections.append(self._create_section(
                        current_headers, current_level, current_content, current_page_number
                    ))
                    current_content = []
                
                current_page_number = int(page_match.group(1))
                continue
            
            # Step 1: Identify headers (lines starting with #)
            header_match = re.match(r'^(#{1,4})\s+(.+)$', line)
            
            if header_match:
                # Save previous section if exists
                if current_content:
                    sections.append(self._create_section(
                        current_headers, current_level, current_content, current_page_number
                    ))
                    current_content = []
                
                # Step 2: Update header hierarchy (parent-child relationships)
                level = len(header_match.group(1))
                current_level = level
                current_headers[level - 1] = header_match.group(2)
                
                # Clear child headers (maintain tree structure)
                for i in range(level, 4):
                    current_headers[i] = ''
            else:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections.append(self._create_section(
                current_headers, current_level, current_content, current_page_number
            ))
        
        return sections
    
    def _create_section(self, headers: List[str], level: int, content: List[str], page_number: int = 1) -> Dict:
        """Create a section with its full context path."""
        # Build breadcrumb: "Clinical Studies > Efficacy Results"
        context_parts = [h for h in headers[:level] if h]
        return {
            'context_path': ' > '.join(context_parts),
            'level': level,
            'content': '\n'.join(content).strip(),
            'headers': headers.copy(),
            'page_number': page_number
        }
    
    def _build_chunk_with_context(self, section: Dict) -> str:
        """
        Step 3 Rule C: Prepend context breadcrumb to content.
        
        Example:
            Context: Clinical Studies > Efficacy Results
            
            The drug showed 50% improvement...
        """
        if section['context_path']:
            return f"Context: {section['context_path']}\n\n{section['content']}"
        return section['content']
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 chars for English)."""
        return len(text) // 4
    
    def _split_large_section(self, section: Dict) -> List[Dict]:
        """Split large sections while preserving context and respecting atomic blocks."""
        chunks = []
        content = section['content']
        page_number = section.get('page_number', 1)
        
        # Rule A: Never split lists or code blocks
        if self._is_atomic_block(content):
            return [{
                'content': self._build_chunk_with_context(section),
                'context': section['context_path'],
                'level': section['level'],
                'page_number': page_number
            }]
        
        # Split by paragraphs (natural boundaries)
        paragraphs = content.split('\n\n')
        current_chunk = []
        
        for para in paragraphs:
            test_content = '\n\n'.join(current_chunk + [para])
            test_chunk = f"Context: {section['context_path']}\n\n{test_content}"
            
            if self._estimate_tokens(test_chunk) > self.max_tokens and current_chunk:
                # Save current chunk with context
                chunk_content = '\n\n'.join(current_chunk)
                chunks.append({
                    'content': f"Context: {section['context_path']}\n\n{chunk_content}",
                    'context': section['context_path'],
                    'level': section['level'],
                    'page_number': page_number
                })
                current_chunk = [para]
            else:
                current_chunk.append(para)
        
        # Add remaining content
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunks.append({
                'content': f"Context: {section['context_path']}\n\n{chunk_content}",
                'context': section['context_path'],
                'level': section['level'],
                'page_number': page_number
            })
        
        return chunks
    
    def _is_atomic_block(self, text: str) -> bool:
        """
        Rule A: Check if content is a list or code block that shouldn't be split.
        However, if the 'atomic' block is already over our limit, we must split it anyway.
        """
        # If the atomic block is oversized, don't protect it - allow splitting
        if self._estimate_tokens(text) > self.max_tokens:
            return False
        
        # Check for markdown lists (-, *, +)
        if re.search(r'^\s*[-*+]\s', text, re.MULTILINE):
            return True
        # Check for numbered lists
        if re.search(r'^\s*\d+\.\s', text, re.MULTILINE):
            return True
        # Check for code blocks
        if '```' in text:
            return True
        return False
