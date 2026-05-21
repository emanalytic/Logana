"""Run logana on all LogHub fixture logs in tests/fixtures/ and print a comparison table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from logana.output.summaryReport import generateSummary
from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.pipelineRunner import runPipeline

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def analyze(path: Path) -> dict:
    config = PipelineConfig.fromCli()
    acc = runPipeline(str(path), config)
    return {
        "file": path.name,
        "lines": acc.eventCounter.totalLines,
        "events": acc.eventCounter.totalEvents,
        "quarantined": acc.eventCounter.totalQuarantined,
        "quarantinePct": round(acc.quarantineTracker.rate * 100, 2),
        "errorPct": round(acc.errorRate.overallErrorRate * 100, 2),
        "latencySamples": acc.latencyDigest.count,
        "errorClusters": len(acc.errorClusterer.clusters),
        "formats": acc.fileProfile.toDict().get("formatDistribution", {}),
        "summary": generateSummary(acc),
    }


def main() -> int:
    logs = sorted(FIXTURES.glob("*.log"))
    results = [analyze(p) for p in logs]
    print(json.dumps(results, indent=2))
    print("\n--- table ---")
    print(f"{'file':<22} {'lines':>6} {'events':>6} {'q%':>6} {'err%':>6} {'lat':>6}")
    for r in results:
        print(
            f"{r['file']:<22} {r['lines']:>6} {r['events']:>6} "
            f"{r['quarantinePct']:>5.1f}% {r['errorPct']:>5.1f}% {r['latencySamples']:>6}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
