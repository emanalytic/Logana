from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.insightReport import generateInsights

def _latencyPhrase(accumulators: AccumulatorSet) -> str:
    digest = accumulators.latencyDigest
    if digest.count == 0:
        return "No response-time data was detected in the log stream."
    return (
        f"System latency was bounded with a median response time of {digest.p50:.1f}ms "
        f"and a p99 of {digest.p99:.1f}ms (n={digest.count:,})"
    )

def generateSummary(accumulators: AccumulatorSet) -> str:
    """Generates a high-level, human-readable one-paragraph summary of the parsed logs."""
    totalLines = accumulators.eventCounter.totalLines
    totalEvents = accumulators.eventCounter.totalEvents
    totalQuarantined = accumulators.eventCounter.totalQuarantined
    qRate = accumulators.quarantineTracker.rate * 100.0
    errRate = accumulators.errorRate.overallErrorRate * 100.0
    throughput = accumulators.eventCounter.throughput
    elapsed = accumulators.eventCounter.elapsedTime

    latencyPhrase = _latencyPhrase(accumulators)

    topEndpoints = accumulators.endpointTable.getSortedEndpoints(sortBy="volume", limit=1)
    topEndpointStr = "N/A"
    if topEndpoints:
        topEndpointStr = f"'{topEndpoints[0].endpoint}' ({topEndpoints[0].count} requests)"

    topErrors = accumulators.errorClusterer.getTopClusters(limit=1)
    topErrorStr = "None"
    if topErrors:
        rep = topErrors[0].representative
        if len(rep) > 50:
            rep = rep[:47] + "..."
        topErrorStr = f"'{rep}' (occurred {topErrors[0].count} times)"

    qualityScore = accumulators.dataQuality.getOverallQualityScore() * 100.0

    span = accumulators.logTimeSpan.toDict()
    span_phrase = ""
    if span.get("available"):
        span_phrase = (
            f" Log events span {span['spanSeconds']:.0f}s of wall time "
            f"({span['first']} -> {span['last']})."
        )

    insights = generateInsights(accumulators)
    insight_phrase = ""
    if insights:
        insight_phrase = f" Key finding: {insights[0]['message']}."

    return (
        f"Log ingestion processed {totalLines:,} lines in {elapsed:.2f} seconds "
        f"({throughput:,.1f} lines/sec), successfully parsing {totalEvents:,} events "
        f"while quarantining {totalQuarantined:,} malformed records ({qRate:.2f}% quarantine rate). "
        f"The application encountered an overall error rate of {errRate:.2f}%. "
        f"{latencyPhrase}, with the busiest endpoint being {topEndpointStr}. "
        f"We identified {len(accumulators.errorClusterer.clusters)} distinct error clusters, led by {topErrorStr}. "
        f"The comprehensive parsed data quality score is {qualityScore:.1f}%."
        f"{span_phrase}{insight_phrase}"
    )
