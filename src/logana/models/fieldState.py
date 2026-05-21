from dataclasses import dataclass, field
from typing import Generic, TypeVar, Union, Optional, Dict

T = TypeVar('T')

@dataclass(frozen=True)
class Known(Generic[T]):
    """Field was successfully parsed with a given confidence."""
    value: T
    confidence: float   # 0.0 to 1.0
    rawToken: str       # The original substring from the log line
    meta: Optional[Dict[str, str]] = field(default=None)

@dataclass(frozen=True)
class Absent:
    """Field is genuinely not present/applicable in the parsed log format."""
    pass

@dataclass(frozen=True)
class Unknown(Generic[T]):
    """Field could not be parsed due to uncertainty or error."""
    reason: str
    bestGuess: Optional[T] = None
    guessConfidence: float = 0.0

FieldState = Union[Known[T], Absent, Unknown[T]]

def isKnown(state: FieldState[T]) -> bool:
    """Checks if the field state is Known."""
    return isinstance(state, Known)

def isAbsent(state: FieldState[T]) -> bool:
    """Checks if the field state is Absent."""
    return isinstance(state, Absent)

def isUnknown(state: FieldState[T]) -> bool:
    """Checks if the field state is Unknown."""
    return isinstance(state, Unknown)

def getValueOrDefault(state: FieldState[T], defaultVal: T) -> T:
    """Returns the value if Known, or the best guess if Unknown (if present), otherwise defaultVal."""
    if isinstance(state, Known):
        return state.value
    if isinstance(state, Unknown) and state.bestGuess is not None:
        return state.bestGuess
    return defaultVal
