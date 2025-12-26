import re

class TextCleaner:
    def clean(self, text: str) -> str:
        # 1. Remove phantom images from Marker
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text) 
        
        # 2. Remove phantom citation links like [](1), [](citation), etc.
        text = re.sub(r'\[\]\([^)]*\)', '', text)
        
        # 3. Linearize markdown tables (convert | Drug | 5mg | to "Drug: 5mg")
        text = self._linearize_tables(text)
        
        # 4. Fix broken hyphens (treat- ment -> treatment)
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        
        # 5. Collapse multiple newlines (structural noise)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _linearize_tables(self, text: str) -> str:
        """Convert markdown tables into linearized text for better RAG performance."""
        lines = text.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Detect table row (contains pipes but not just separator)
            if '|' in line and not re.match(r'^\s*\|[\s:-]+\|', line):
                # Extract cells from table row
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                
                # Check if next line is a header separator (|---|---|)
                is_header = (i + 1 < len(lines) and 
                           re.match(r'^\s*\|[\s:-]+\|', lines[i + 1]))
                
                if is_header:
                    # This is a header row, skip separator on next iteration
                    result.append(' | '.join(cells))
                    i += 2  # Skip header and separator
                    continue
                elif len(cells) >= 2:
                    # Regular data row: "Key: Value" format
                    linearized = ', '.join([f"{cells[j]}: {cells[j+1]}" 
                                          for j in range(0, len(cells)-1, 2)])
                    result.append(linearized)
                else:
                    result.append(line)
            else:
                result.append(line)
            
            i += 1
        
        return '\n'.join(result)
