import orjson
from typing import Any, Dict, Optional
from logana.analytics.accumulatorSet import AccumulatorSet
from logana.models.quarantineEntry import QuarantineEntry
from logana.output.insightReport import generateInsights
from logana.pipeline.timeContext import PipelineTimeContext

def _latencyBlock(accumulators: AccumulatorSet) -> Dict[str, Any]:
    digest = accumulators.latencyDigest
    block: Dict[str, Any] = {
        "count": digest.count,
        "lowConfidenceCount": digest.lowConfidenceCount,
        "unknownCount": digest.unknownCount,
        "available": digest.count > 0,
    }
    if digest.count > 0:
        block.update({
            "p50": digest.p50,
            "p95": digest.p95,
            "p99": digest.p99,
            "min": digest.min,
            "max": digest.max,
        })
    else:
        block["message"] = "No response-time samples were parsed from this file."
    return block


def _formatDriftBlock(accumulators: AccumulatorSet) -> Dict[str, Any]:
    drifts = accumulators.formatTracker.driftEvents
    block: Dict[str, Any] = {
        "count": len(drifts),
        "available": bool(drifts),
    }
    if drifts:
        block["latest"] = {
            "lineNumber": drifts[-1].lineNumber,
            "fromFormat": drifts[-1].fromFormat,
            "toFormat": drifts[-1].toFormat,
            "timestamp": drifts[-1].timestamp.isoformat() if drifts[-1].timestamp else None,
        }
        block["recent"] = [
            {
                "lineNumber": drift.lineNumber,
                "fromFormat": drift.fromFormat,
                "toFormat": drift.toFormat,
                "timestamp": drift.timestamp.isoformat() if drift.timestamp else None,
            }
            for drift in drifts[-5:]
        ]
    return block


def exportToJson(
    accumulators: AccumulatorSet,
    time_context: Optional[PipelineTimeContext] = None,
) -> str:
    """Serializes the complete analytical state of all streaming accumulators into JSON."""
    time_config: Dict[str, Any] = {}
    if time_context is not None:
        time_config = {
            "logTimezone": str(time_context.default_tz),
            "naivePolicy": time_context.naive_policy,
            "referenceYear": time_context.reference_year,
        }

    recent_quarantine = accumulators.quarantineTracker.getRecentSamples(limit=10)
    quarantine_samples = [
        {
            "lineNumber": entry.lineNumber,
            "reason": entry.reason,
            "preview": entry.rawContent[:120],
        }
        for entry in recent_quarantine
        if isinstance(entry, QuarantineEntry)
    ]

    data = {
        "summary": {
            "totalLines": accumulators.eventCounter.totalLines,
            "totalEvents": accumulators.eventCounter.totalEvents,
            "totalQuarantined": accumulators.eventCounter.totalQuarantined,
            "quarantineRate": accumulators.quarantineTracker.rate,
            "overallErrorRate": accumulators.errorRate.overallErrorRate,
            "throughput": accumulators.eventCounter.throughput,
            "elapsedTime": accumulators.eventCounter.elapsedTime,
        },
        "time": time_config,
        "logTimeSpan": accumulators.logTimeSpan.toDict(),
        "fileProfile": accumulators.fileProfile.toDict(),
        "formatDrift": _formatDriftBlock(accumulators),
        "insights": generateInsights(accumulators),
        "keywords": accumulators.keywordCounter.getTop(),
        "latency": _latencyBlock(accumulators),
        "endpoints": [
            {
                "endpoint": stat.endpoint,
                "count": stat.count,
                "errors": stat.errors,
                "errorRate": stat.errorRate,
                "p50Latency": stat.p50Latency,
                "p95Latency": stat.p95Latency,
                "p99Latency": stat.p99Latency,
                "trend": stat.trend,
            }
            for stat in accumulators.endpointTable.getSortedEndpoints(sortBy="volume", limit=100)
        ],
        "errors": [
            {
                "representative": cluster.representative,
                "count": cluster.count,
                "lastSeen": cluster.lastSeen.isoformat(),
                "endpoints": list(cluster.endpoints),
            }
            for cluster in accumulators.errorClusterer.getTopClusters(limit=100)
        ],
        "quarantine": {
            "reasonBreakdown": accumulators.quarantineTracker.getReasonBreakdown(),
            "recentSamples": quarantine_samples,
        },
        "schema": {
            "formatDistribution": accumulators.formatTracker.getFormatDistribution(),
            "driftEvents": [
                {
                    "lineNumber": drift.lineNumber,
                    "fromFormat": drift.fromFormat,
                    "toFormat": drift.toFormat,
                    "timestamp": drift.timestamp.isoformat() if drift.timestamp else None,
                }
                for drift in accumulators.formatTracker.driftEvents
            ],
        },
        "quality": {
            "overallScore": accumulators.dataQuality.getOverallQualityScore(),
            "fields": {
                field: {
                    "rates": accumulators.dataQuality.getFieldQualityRates(field),
                    "averageConfidence": accumulators.dataQuality.getAverageConfidence(field),
                }
                for field in accumulators.dataQuality.FIELDS
            },
        },
        "anomalies": [
            {
                "timestamp": anomaly.timestamp.isoformat(),
                "metricValue": anomaly.metricValue,
                "baseline": anomaly.baseline,
                "zScore": anomaly.zScore,
                "direction": anomaly.direction,
            }
            for anomaly in sorted(
                accumulators.errorRate.anomalies + accumulators.quarantineTracker.anomalies,
                key=lambda a: a.timestamp,
            )
        ],
    }
    return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")
