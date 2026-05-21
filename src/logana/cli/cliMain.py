import sys
from datetime import date
from typing import Optional
import click
from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.dashboard import Dashboard, Live, RICH_AVAILABLE
from logana.output.jsonExport import exportToJson
from logana.output.summaryReport import generateSummary
from logana.pipeline.pipelineConfig import PipelineConfig
from logana.pipeline.pipelineRunner import runPipeline


def _safeEcho(text: str) -> None:
    """Print text without crashing on Windows consoles that lack Unicode glyphs."""
    try:
        click.echo(text)
    except UnicodeEncodeError:
        click.echo(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ))


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--format",
    "outputFormat",
    type=click.Choice(["summary", "json", "dashboard"], case_sensitive=False),
    default="summary",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--quarantine-threshold",
    "quarantineThreshold",
    type=click.FloatRange(min=0.0, max=1.0),
    default=0.3,
    show_default=True,
    help="Minimum confidence required before a parse is accepted.",
)
@click.option(
    "--log-timezone",
    "logTimezone",
    default="local",
    show_default=True,
    help="IANA timezone for naive timestamps (e.g. America/Chicago, UTC, local).",
)
@click.option(
    "--naive-timestamps",
    "naiveTimestamps",
    type=click.Choice(["local", "utc"], case_sensitive=False),
    default="local",
    show_default=True,
    help="Whether naive timestamps without offsets are local wall time or UTC.",
)
@click.option(
    "--reference-date",
    "referenceDate",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Reference date for syslog entries missing a year (YYYY-MM-DD).",
)
@click.option(
    "--encoding",
    "encoding",
    default="utf-8",
    show_default=True,
    help="Text encoding for the log file (utf-8, utf-8-sig, latin-1).",
)
@click.option(
    "--allow-synthetic-timestamps",
    "allowSyntheticTimestamps",
    is_flag=True,
    default=False,
    help="Assign low-confidence ingestion time when no timestamp is found.",
)
@click.option(
    "--profile",
    "profile",
    type=click.Choice(["strict", "pragmatic", "forensics"], case_sensitive=False),
    default="pragmatic",
    show_default=True,
    help="Quarantine strictness: strict (all fields), pragmatic (timestamp only), forensics (synthetic time).",
)
def main(
    file_path: str,
    outputFormat: str,
    quarantineThreshold: float,
    logTimezone: str,
    naiveTimestamps: str,
    referenceDate: Optional[click.DateTime],
    encoding: str,
    allowSyntheticTimestamps: bool,
    profile: str,
) -> Optional[int]:
    """Analyze a log file and print streaming analytics."""
    ref = referenceDate.date() if referenceDate else None
    config = PipelineConfig.fromCli(
        quarantineThreshold=quarantineThreshold,
        logTimezone=logTimezone,
        naiveTimestamps=naiveTimestamps.lower(),
        referenceDate=ref,
        encoding=encoding,
        allowSyntheticTimestamps=allowSyntheticTimestamps,
        profile=profile.lower(),
    )

    if outputFormat.lower() == "dashboard":
        accumulators = _runWithDashboard(file_path, config)
        if not RICH_AVAILABLE:
            _safeEcho("Dashboard mode requires rich; falling back to summary output.")
            _safeEcho(generateSummary(accumulators))
        return None

    accumulators = runPipeline(file_path, config)
    if outputFormat.lower() == "json":
        _safeEcho(exportToJson(accumulators, time_context=config.resolvedTimeContext()))
    else:
        _safeEcho(generateSummary(accumulators))
    return None


def _runWithDashboard(filePath: str, config: PipelineConfig) -> AccumulatorSet:
    accumulators = AccumulatorSet(max_endpoints=config.maxEndpoints)
    dashboard = Dashboard(accumulators)
    dashboard.redrawInterval = 0.0
    dashboard.update()

    with Live(
        dashboard.layout,
        refresh_per_second=8,
        transient=False,
        vertical_overflow="visible",
    ) as live:
        def onProgress() -> None:
            dashboard.update()
            live.update(dashboard.layout)

        runPipeline(filePath, config, onProgress=onProgress, accumulators=accumulators)
        dashboard.update()
        live.update(dashboard.layout)

    return accumulators


if __name__ == "__main__":
    main()
