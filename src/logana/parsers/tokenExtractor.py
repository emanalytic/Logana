from typing import Dict, List
from logana.models.fieldState import FieldState, Known
from logana.parsers.parserBase import Parser, ParseResult
from logana.parsers.fieldKit import ParserFieldKit
from logana.pipeline.timeContext import PipelineTimeContext, defaultTimeContext

class TokenExtractor(Parser):
    """Fallback parser that tokenizes arbitrary log lines and 
    scans each token to extract fields statistically."""
    
    def __init__(self, time_context: PipelineTimeContext | None = None):
        super().__init__("tokenExtractor")
        self.kit = ParserFieldKit(time_context or defaultTimeContext())

    def parse(self, text: str, lineNumber: int) -> ParseResult:
        cleaned = text.strip()
        tokens = cleaned.split()
        
        fields: Dict[str, FieldState] = self.kit.emptyStandardFields()
        fields["message"] = Known(cleaned, 1.0, cleaned)

        self.kit.scanTokens(fields, tokens, lineText=cleaned)

        return ParseResult(
            self.parserId,
            fields,
            text,
            lineNumber,
            []
        )
