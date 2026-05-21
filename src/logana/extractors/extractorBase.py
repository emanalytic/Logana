from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from logana.models.fieldState import FieldState

T = TypeVar('T')

class BaseExtractor(ABC, Generic[T]):
    """Base class for all field extractors. Centralizes cleaning logic and defines the extractor contract."""
    
    def __init__(self, fieldName: str):
        self.fieldName = fieldName

    @abstractmethod
    def extract(self, token: str) -> FieldState[T]:
        """Extracts a value from a raw log token, returning a FieldState[T] representing uncertainty."""
        pass

    def cleanToken(self, token: str) -> str:
        """Removes common log enclosing characters like brackets, quotes, parentheses, and whitespaces."""
        return token.strip(' []"\'(),;')
