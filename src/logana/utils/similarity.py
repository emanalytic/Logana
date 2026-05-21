import re
from typing import Set

# Regular expression patterns for token normalization
IP_PATTERN = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
HEX_PATTERN = re.compile(r'\b0x[0-9a-fA-F]+\b')
UUID_PATTERN = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
NUMBER_PATTERN = re.compile(r'\b\d+\b')

def tokenize(text: str) -> Set[str]:
    """Tokenizes and normalizes log messages for Jaccard similarity clustering.
    
    Replaces variable payloads (IPs, hex digits, UUIDs, numeric values) with 
    standardized placeholders to allow structurally identical logs to group easily.
    """
    if not text:
        return set()
        
    normalized = text.lower()
    
    # Substitute variable parameters with placeholder tokens
    normalized = IP_PATTERN.sub('<ip>', normalized)
    normalized = HEX_PATTERN.sub('<hex>', normalized)
    normalized = UUID_PATTERN.sub('<uuid>', normalized)
    normalized = NUMBER_PATTERN.sub('<num>', normalized)
    
    # Extract structural alphabetic words and the placeholders
    tokens = set()
    for token in re.findall(r'<[a-z]+>|[a-zA-Z]+', normalized):
        tokens.add(token)
        
    return tokens

def jaccardSimilarity(setA: Set[str], setB: Set[str]) -> float:
    """Computes the Jaccard similarity coefficient between two token sets.
    
    Returns 1.0 if both sets are empty, and a float in range [0.0, 1.0] otherwise.
    """
    if not setA and not setB:
        return 1.0
    if not setA or not setB:
        return 0.0
        
    intersection = len(setA.intersection(setB))
    union = len(setA.union(setB))
    return float(intersection) / float(union)
