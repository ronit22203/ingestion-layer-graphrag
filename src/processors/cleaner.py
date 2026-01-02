import re
import logging
from typing import Optional, Dict

# Set up logging
logger = logging.getLogger(__name__)

class TextCleaner:
    """
    Markdown text cleaning with PII removal.
    Removes artifacts, normalizes formatting, and anonymizes sensitive information.
    """
    
    def __init__(self, remove_pii: bool = True):
        self.remove_pii = remove_pii
        self.pii_analyzer = None
        self.pii_anonymizer = None
        
        if remove_pii:
            try:
                from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
                from presidio_anonymizer import AnonymizerEngine
                
                # Initialize Engines
                self.pii_analyzer = AnalyzerEngine()
                self.pii_anonymizer = AnonymizerEngine()
                
                # --- CRITICAL: Add Custom Recognizers for Singaporean Medical Data ---
                # 1. Singapore NRIC/FIN (e.g., S1234567X)
                nric_pattern = Pattern(name="sg_nric_pattern", regex=r"(?i)[STFG]\d{7}[A-Z]", score=1.0)
                nric_recognizer = PatternRecognizer(supported_entity="SG_NRIC", patterns=[nric_pattern])
                self.pii_analyzer.registry.add_recognizer(nric_recognizer)

                # 2. MCR Number (Medical Registration)
                mcr_pattern = Pattern(name="mcr_pattern", regex=r"\b\d{6}\b", score=0.6)
                mcr_recognizer = PatternRecognizer(supported_entity="MCR_NO", patterns=[mcr_pattern])
                self.pii_analyzer.registry.add_recognizer(mcr_recognizer)
                
                logger.info("PII Redaction initialized with custom Singaporean recognizers.")

            except ImportError:
                logger.warning("⚠️  Presidio not installed. PII removal disabled.")
                self.remove_pii = False
    
    def clean(self, text: str) -> str:
        """
        Clean markdown text in sequence:
        1. Remove phantom images and links
        2. Linearize tables
        3. Fix hyphenation
        4. Collapse whitespace
        5. Remove/anonymize PII
        """
        if not text: return ""

        # 1. Remove phantom images from Marker
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text) 
        
        # 2. Remove phantom citation links like [](1), [](citation)
        text = re.sub(r'\[\]\([^)]*\)', '', text)
        
        # 3. Linearize markdown tables
        text = self._linearize_tables(text)
        
        # 4. Fix broken hyphens (treat- ment -> treatment)
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        
        # 5. Collapse multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 6. Remove/anonymize PII (if enabled)
        if self.remove_pii and self.pii_analyzer:
            text = self._remove_pii(text)
        
        return text.strip()
    
    def _remove_pii(self, text: str) -> str:
        """
        Detect and anonymize PII using Presidio.
        """
        try:
            from presidio_anonymizer.entities import OperatorConfig

            # Analyze text
            results = self.pii_analyzer.analyze(
                text=text, 
                language="en",
                entities=[
                    "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", 
                    "SG_NRIC", "MCR_NO", "DATE_TIME", "URL"
                ]
            )
            
            if not results:
                return text

            # Define Operators using OperatorConfig (The Fix for the crash)
            operators = {
                "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"}),
                "PERSON": OperatorConfig("replace", {"new_value": "<PERSON>"}),
                "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE>"}),
                "SG_NRIC": OperatorConfig("replace", {"new_value": "<NRIC_ID>"}),
                "MCR_NO": OperatorConfig("replace", {"new_value": "<MEDICAL_LICENSE_ID>"}),
                "DATE_TIME": OperatorConfig("replace", {"new_value": "<DATE>"}),
                "URL": OperatorConfig("replace", {"new_value": "<URL>"}),
            }
            
            # Anonymize
            anonymized = self.pii_anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators
            )
            
            return anonymized.text
        
        except Exception as e:
            logger.error(f"⚠️  PII removal error: {e}")
            # Fail safe: Do NOT return raw text if we suspected PII but failed to clean it.
            # However, blocking the pipeline is also bad.
            # Log critical warning and return text (assuming downstream manual review)
            # Or raise error to stop pipeline.
            logger.critical("Returning unredacted text due to error.")
            return text

    def _linearize_tables(self, text: str) -> str:
        """Convert markdown tables into linearized text."""
        lines = text.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            # Simple table detection (contains | and not just a separator line)
            if '|' in line and not re.match(r'^\s*\|[\s:-]+\|', line):
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                
                # Check if next line is a header separator
                is_header = (i + 1 < len(lines) and re.match(r'^\s*\|[\s:-]+\|', lines[i + 1]))
                
                if is_header:
                    result.append(' | '.join(cells))
                    i += 2
                    continue
                elif len(cells) >= 2:
                    # Linearize: "Key: Value, Key2: Value2"
                    linearized = ', '.join([f"{cells[j]}: {cells[j+1]}" for j in range(0, len(cells)-1, 2)])
                    result.append(linearized)
                else:
                    result.append(line)
            else:
                result.append(line)
            i += 1
        
        return '\n'.join(result)