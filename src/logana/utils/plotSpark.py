"""Optional plotext sparklines for terminal dashboards."""

from __future__ import annotations

from typing import List, Optional


def buildSparkline(values: List[float], width: int = 36, height: int = 6) -> Optional[str]:
    """Return a plotext chart string, or None if plotext is unavailable or values empty."""
    if not values:
        return None
    try:
        import plotext as plt
    except ImportError:  # pragma: no cover
        return None

    plt.clf()
    plt.theme("dark")
    plt.plot(values)
    plt.plotsize(width, height)
    plt.canvas_color("black")
    plt.axes_color("black")
    plt.ticks_color("white")
    return plt.build()
