import ipaddress
from logana.models.fieldState import FieldState, Known, Unknown, Absent
from logana.extractors.base import BaseExtractor

class IpAddressExtractor(BaseExtractor[str]):
    """Extractor for IP addresses (supporting IPv4 and IPv6)."""
    
    def __init__(self):
        super().__init__("ipAddress")

    def extract(self, token: str) -> FieldState[str]:
        cleaned = self.cleanToken(token)
        if not cleaned:
            return Absent()

        try:
            ip = ipaddress.ip_address(cleaned)
            return Known(str(ip), 0.95, token)
        except ValueError:
            # Check if it has a subset that looks like an IP but failed validation
            if '.' in cleaned and len(cleaned.split('.')) == 4:
                return Unknown(f"Malformed IP address format: '{cleaned}'", cleaned, 0.2)
            return Absent()
