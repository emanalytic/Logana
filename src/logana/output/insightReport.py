from typing import Any, Dict, List
from logana.analytics.accumulatorSet import AccumulatorSet

def generateInsights(accumulators: AccumulatorSet) -> List[Dict[str, Any]]:
    """Builds short actionable highlight bullets from accumulator state."""
    highlights: List[Dict[str, Any]] = []
    q_rate = accumulators.quarantineTracker.rate * 100.0

    if q_rate > 5.0:
        breakdown = accumulators.quarantineTracker.getReasonBreakdown()
        top_reason = next(iter(breakdown), "unknown")
        highlights.append({
            "type": "quarantine",
            "severity": "warn",
            "message": f"{q_rate:.1f}% of lines quarantined; top reason: {top_reason}",
        })

    if accumulators.errorRate.anomalies:
        last = accumulators.errorRate.anomalies[-1]
        if 3.0 <= abs(last.zScore) <= 50.0:
            highlights.append({
                "type": "anomaly",
                "severity": "alert",
                "message": (
                    f"Error-rate spike at {last.timestamp.strftime('%H:%M:%S')} UTC "
                    f"(z={last.zScore:.1f})"
                ),
            })

    if accumulators.formatTracker.driftEvents:
        drift = accumulators.formatTracker.driftEvents[-1]
        highlights.append({
            "type": "drift",
            "severity": "info",
            "message": (
                f"Format changed from {drift.fromFormat} to {drift.toFormat} "
                f"near line {drift.lineNumber}"
            ),
        })

    top_eps = accumulators.endpointTable.getSortedEndpoints(sortBy="volume", limit=1)
    if top_eps and top_eps[0].endpoint != "(unattributed)":
        ep = top_eps[0]
        highlights.append({
            "type": "traffic",
            "severity": "info",
            "message": f"Busiest activity '{ep.endpoint}' with {ep.count:,} events",
        })

    top_errors = accumulators.errorClusterer.getTopClusters(limit=1)
    if top_errors:
        highlights.append({
            "type": "error",
            "severity": "warn",
            "message": (
                f"Top error pattern ({top_errors[0].count}x): "
                f"{top_errors[0].representative[:80]}"
            ),
        })

    span = accumulators.logTimeSpan.toDict()
    if span.get("available"):
        highlights.append({
            "type": "time",
            "severity": "info",
            "message": (
                f"Log covers {span['spanSeconds']:.0f}s "
                f"from {span['first']} to {span['last']}"
            ),
        })

    if accumulators.latencyDigest.count == 0:
        highlights.append({
            "type": "latency",
            "severity": "info",
            "message": "No response-time field detected in parsed events.",
        })

    return highlights
