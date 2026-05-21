import math
from typing import List

class Centroid:
    """A single centroid in the T-Digest approximation, representing a cluster of data points."""
    
    def __init__(self, mean: float, weight: float = 1.0):
        self.mean = mean
        self.weight = weight

    def __lt__(self, other: 'Centroid') -> bool:
        return self.mean < other.mean


class TDigest:
    """Streaming percentile estimation with bounded memory.
    
    Maintains a set of centroids that approximate the full distribution.
    Supports: quantile queries (p50, p95, p99), min, max, count.
    Memory: O(compression) where compression defaults to 100.
    """
    
    def __init__(self, compression: float = 100.0):
        self.compression = compression
        self.centroids: List[Centroid] = []
        self.buffer: List[Centroid] = []
        self.totalWeight = 0.0
        self.minVal = float('inf')
        self.maxVal = float('-inf')

    def add(self, value: float, weight: float = 1.0) -> None:
        """Adds a single data point or weighted cluster of data points to the T-Digest."""
        if weight <= 0.0:
            return
            
        self.buffer.append(Centroid(value, weight))
        self.totalWeight += weight
        
        if value < self.minVal:
            self.minVal = value
        if value > self.maxVal:
            self.maxVal = value
            
        # Flush buffer if it grows too large to maintain bounded memory
        if len(self.buffer) > self.compression * 20:
            self.merge()

    def merge(self) -> None:
        """Merges buffered data points into the main sorted list of centroids, combining clusters as needed."""
        if not self.buffer:
            return
            
        # Combine existing centroids and buffered new data points, sorted by mean
        allCentroids = sorted(self.centroids + self.buffer, key=lambda c: c.mean)
        self.buffer.clear()
        
        if not allCentroids:
            self.centroids = []
            return

        merged: List[Centroid] = []
        curr = allCentroids[0]
        merged.append(curr)
        
        qLimit = 0.0
        W = self.totalWeight
        
        for nextCentroid in allCentroids[1:]:
            combinedWeight = curr.weight + nextCentroid.weight
            
            # Estimate quantile limits for the proposed combined centroid
            q0 = qLimit / W
            q1 = (qLimit + combinedWeight) / W
            
            q0 = max(0.0, min(1.0, q0))
            q1 = max(0.0, min(1.0, q1))
            
            # Using the k1 scale function: k1(q1) - k1(q0) <= 1.0
            # which is: (compression / 2pi) * (asin(2q1 - 1) - asin(2q0 - 1)) <= 1.0
            k0 = math.asin(2.0 * q0 - 1.0)
            k1 = math.asin(2.0 * q1 - 1.0)
            diffK = (self.compression / (2.0 * math.pi)) * (k1 - k0)
            
            # Allow merging if the scale function difference is <= 1.0, 
            # or if the combined weight is extremely small (e.g. <= 1.0)
            if diffK <= 1.0 or combinedWeight <= 1.0:
                # Merge nextCentroid into the current centroid
                newMean = curr.mean + (nextCentroid.mean - curr.mean) * nextCentroid.weight / combinedWeight
                curr.mean = newMean
                curr.weight = combinedWeight
            else:
                # Close current centroid and start a new one
                qLimit += curr.weight
                curr = Centroid(nextCentroid.mean, nextCentroid.weight)
                merged.append(curr)
                
        self.centroids = merged

    def quantile(self, q: float) -> float:
        """Estimates the value at the given quantile q (0.0 to 1.0)."""
        if q < 0.0 or q > 1.0:
            raise ValueError("Quantile must be between 0.0 and 1.0")
            
        # Ensure buffer is completely merged first
        self.merge()
        
        if not self.centroids:
            return 0.0
            
        if len(self.centroids) == 1:
            return self.centroids[0].mean

        if q == 0.0:
            return self.minVal
        if q == 1.0:
            return self.maxVal

        targetWeight = q * self.totalWeight
        currentWeight = 0.0
        
        for i, c in enumerate(self.centroids):
            centroidWeight = c.weight
            centroidTarget = currentWeight + centroidWeight / 2.0
            
            if targetWeight == centroidTarget:
                return c.mean
            elif targetWeight < centroidTarget:
                # Interpolate between centroids
                if i == 0:
                    t = targetWeight / (centroidWeight / 2.0)
                    return self.minVal + t * (c.mean - self.minVal)
                else:
                    prev = self.centroids[i - 1]
                    prevTarget = currentWeight - prev.weight / 2.0
                    t = (targetWeight - prevTarget) / (centroidTarget - prevTarget)
                    return prev.mean + t * (c.mean - prev.mean)
                    
            currentWeight += centroidWeight
            
        # Interpolate between last centroid and maxVal
        last = self.centroids[-1]
        lastTarget = self.totalWeight - last.weight / 2.0
        if targetWeight > lastTarget:
            t = (targetWeight - lastTarget) / (self.totalWeight - lastTarget)
            return last.mean + t * (self.maxVal - last.mean)
            
        return self.maxVal
