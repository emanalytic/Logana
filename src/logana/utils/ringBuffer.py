from typing import Generic, TypeVar, List
import collections

T = TypeVar('T')

class RingBuffer(Generic[T]):
    """Generic bounded ring buffer with O(1) push, median, and MAD calculations."""
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.data = collections.deque(maxlen=capacity)

    def push(self, item: T) -> None:
        """Pushes a new item into the ring buffer, evicting the oldest if capacity is reached."""
        self.data.append(item)

    @property
    def count(self) -> int:
        """Returns the number of elements in the ring buffer."""
        return len(self.data)

    def clear(self) -> None:
        """Clears all elements from the ring buffer."""
        self.data.clear()

    def getValues(self) -> List[T]:
        """Returns the values in the ring buffer as a list."""
        return list(self.data)

    def __iter__(self):
        return iter(self.data)

    def median(self) -> float:
        """Returns the median of the values in the buffer. Returns 0.0 if empty."""
        if not self.data:
            return 0.0
        sortedVals = sorted(float(x) for x in self.data)
        n = len(sortedVals)
        if n % 2 == 1:
            return float(sortedVals[n // 2])
        else:
            return float((sortedVals[n // 2 - 1] + sortedVals[n // 2]) / 2.0)

    def mad(self) -> float:
        """Returns the Median Absolute Deviation (MAD) of the values in the buffer. Returns 0.0 if empty."""
        if not self.data:
            return 0.0
        med = self.median()
        absDiffs = [abs(float(x) - med) for x in self.data]
        sortedDiffs = sorted(absDiffs)
        n = len(sortedDiffs)
        if n % 2 == 1:
            return float(sortedDiffs[n // 2])
        else:
            return float((sortedDiffs[n // 2 - 1] + sortedDiffs[n // 2]) / 2.0)
