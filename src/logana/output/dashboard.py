"""Live terminal dashboard for streaming log analysis."""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

from logana.analytics.accumulatorSet import AccumulatorSet
from logana.analytics.endpointTable import EndpointStats
from logana.output.insightReport import generateInsights

try:
    from rich import box
    from rich.console import Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ModuleNotFoundError:
    RICH_AVAILABLE = False
    box = None  # type: ignore[assignment]

    class Live:  # noqa: D101
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, *args, **kwargs):
            pass

    class Layout:  # noqa: D101
        def __init__(self, *args, name=None, size=None, ratio=None, **kwargs):
            self.name = name
            self.children: dict = {}

        def split_column(self, *layouts):
            for child in layouts:
                if child.name:
                    self.children[child.name] = child

        def split_row(self, *layouts):
            self.split_column(*layouts)

        def update(self, renderable):
            pass

        def __getitem__(self, name):
            if name in self.children:
                return self.children[name]
            for child in self.children.values():
                try:
                    return child[name]
                except KeyError:
                    continue
            raise KeyError(name)

    class Panel:  # noqa: D101
        def __init__(self, renderable, *args, **kwargs):
            self.renderable = renderable

    class Table:  # noqa: D101
        def __init__(self, *args, **kwargs):
            self.columns: list = []
            self.rows: list = []

        def add_column(self, name, *args, **kwargs):
            self.columns.append(name)

        def add_row(self, *values):
            self.rows.append(values)

        @classmethod
        def grid(cls, *args, **kwargs):
            return cls()

    class Text:  # noqa: D101
        @staticmethod
        def assemble(*parts):
            return "".join(str(p[0] if isinstance(p, tuple) else p) for p in parts)

        def __init__(self, text="", style=""):
            self.text = text

    class Group:  # noqa: D101
        def __init__(self, *items):
            self.items = items


_PANEL_PAD = (0, 1)
_TABLE_BOX = box.SIMPLE_HEAD if RICH_AVAILABLE else None


@dataclass(frozen=True)
class _Glyphs:
    arrow: str
    mid: str
    dash: str
    up: str
    down: str
    spark: str
    dot: str
    sep: str  # trimmed mid, for title line

    @classmethod
    def for_stdout(cls) -> _Glyphs:
        enc = (getattr(sys.stdout, "encoding", None) or "").lower().replace("_", "-")
        ascii_mode = not enc or ("utf" not in enc and enc not in ("utf8",))
        if ascii_mode:
            return cls("->", " | ", "-", "^", "v", "._:|#", ".", "|")
        return cls("→", " · ", "—", "▲", "▼", "▁▂▃▄▅▆▇█", "·", "·")


G = _Glyphs.for_stdout()
_SEVERITY_STYLE = {"alert": "bold red", "warn": "bold yellow", "info": "cyan"}
_SEVERITY_ICON = {"alert": "!!", "warn": "!", "info": G.dot}


@dataclass(frozen=True)
class _Overview:
    """Single source for header/snapshot counts (matches summary report math)."""

    lines: int
    accepted: int
    quarantined: int
    accept_pct: float
    quarantine_pct: float
    error_pct: float
    throughput: float
    elapsed_sec: float


def _overview(acc: AccumulatorSet) -> _Overview:
    ec = acc.eventCounter
    lines = ec.totalLines
    accepted = ec.totalEvents
    quarantined = ec.totalQuarantined
    return _Overview(
        lines=lines,
        accepted=accepted,
        quarantined=quarantined,
        accept_pct=100.0 * accepted / lines if lines else 0.0,
        quarantine_pct=100.0 * quarantined / lines if lines else 0.0,
        error_pct=acc.errorRate.overallErrorRate * 100.0,
        throughput=ec.throughput,
        elapsed_sec=ec.elapsedTime,
    )


def _weakest_fields(acc: AccumulatorSet, limit: int = 3) -> list[tuple[str, float]]:
    ranked = [
        (field, acc.dataQuality.getFieldQualityRates(field)["known"])
        for field in acc.dataQuality.FIELDS
    ]
    ranked.sort(key=lambda item: item[1])
    return ranked[:limit]


def _truncate(text: str, max_len: int, suffix: str = "...") -> str:
    if len(text) <= max_len:
        return text
    keep = max_len - len(suffix)
    return text[:keep] + suffix if keep > 0 else suffix


def _sparkline(values: Sequence[float], width: int = 12) -> str:
    if not values:
        return G.dash
    window = list(values[-width:])
    peak = max(window) or 1e-9
    blocks = G.spark
    empty = blocks[0]
    return "".join(
        empty if value <= 0
        else blocks[min(int((value / peak) * (len(blocks) - 1)), len(blocks) - 1)]
        for value in window
    )


def _panel(renderable, title: str, border_style: str, subtitle: str = "") -> Panel:
    return Panel(
        renderable,
        title=title,
        subtitle=subtitle,
        border_style=border_style,
        padding=_PANEL_PAD,
        title_align="left",
    )


def _metric_row(label: str, value: str, value_style: str = "bold white") -> Text:
    return Text.assemble((f"{label:<14} ", "dim"), (value, value_style))


def _health_badge(acc: AccumulatorSet) -> tuple[str, str]:
    ov = _overview(acc)
    if ov.lines == 0:
        return "LOADING", "bold white on blue"
    q_rate = ov.quarantine_pct
    err_rate = ov.error_pct
    if err_rate >= 10.0 or q_rate >= 15.0:
        return "CRITICAL", "bold white on red"
    if err_rate >= 2.0 or q_rate >= 5.0 or acc.errorRate.anomalies:
        return "DEGRADED", "bold black on yellow"
    return "HEALTHY", "bold white on green"


def _elapsed_label(seconds: float) -> str:
    total = max(int(seconds), 0)
    if total < 60:
        return f"{max(seconds, 0.0):.1f}s"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _err_pct_style(pct: float) -> str:
    if pct >= 10:
        return "red"
    if pct > 0:
        return "yellow"
    return "green"


def _time_span_line(acc: AccumulatorSet) -> Text:
    span = acc.logTimeSpan.toDict()
    if not span.get("available"):
        return Text("Log time range: not enough timestamps yet", style="dim italic")
    seconds = span.get("spanSeconds") or 0
    if seconds >= 3600:
        duration = f"{seconds / 3600:.1f}h"
    elif seconds >= 60:
        duration = f"{seconds / 60:.0f}m"
    else:
        duration = f"{seconds:.0f}s"
    first_dt = acc.logTimeSpan.first
    last_dt = acc.logTimeSpan.last
    t0 = first_dt.strftime("%H:%M:%S") if first_dt else G.dash
    t1 = last_dt.strftime("%H:%M:%S") if last_dt else G.dash
    return Text.assemble(
        ("Coverage ", "dim"),
        (duration, "bold white"),
        ("  from ", "dim"),
        (t0, "cyan"),
        (f" {G.arrow} ", "dim"),
        (t1, "cyan"),
    )


def _format_mix(acc: AccumulatorSet, limit: int = 4) -> str:
    """Share of accepted lines per parser (excludes quarantined)."""
    dist = acc.fileProfile.toDict().get("formatDistribution", {})
    if not dist:
        return G.dash
    total = sum(dist.values()) or 1
    ranked = sorted(dist.items(), key=lambda item: item[1], reverse=True)[:limit]
    parts = [f"{name} {100.0 * count / total:.0f}%" for name, count in ranked]
    return ", ".join(parts)


class Dashboard:
    """Live terminal dashboard: KPIs, alerts, errors, endpoints, and diagnostics."""

    def __init__(self, accumulators: AccumulatorSet):
        self.acc = accumulators
        self.layout = self._build_layout()
        self.lastRedraw = 0.0
        self.redrawInterval = 0.1

    def _build_layout(self) -> Layout:
        """Stack layout: wide snapshot + errors; only error/latency share one row."""
        root = Layout()
        root.split_column(
            Layout(name="header", size=7),
            Layout(name="alerts", size=5),
            Layout(name="body"),
            Layout(name="footer", size=8),
        )
        root["body"].split_column(
            Layout(name="metrics", size=10),
            Layout(name="snapshot", size=7),
            Layout(name="errors", size=11),
            Layout(name="endpoints", size=13),
        )
        root["metrics"].split_row(
            Layout(name="errorRate", ratio=1),
            Layout(name="latency", ratio=1),
        )
        root["endpoints"].split_row(
            Layout(name="byVolume", ratio=1),
            Layout(name="byErrors", ratio=1),
        )
        return root

    def _paint(self, slot: str, body, title: str, border: str, subtitle: str = "") -> None:
        self.layout[slot].update(_panel(body, title, border, subtitle))

    def update(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.lastRedraw < self.redrawInterval:
            return
        self.lastRedraw = now
        self._update_header()
        self._update_alerts()
        self._update_error_rate()
        self._update_latency()
        self._update_snapshot()
        self._update_errors()
        self._update_endpoints_by_volume()
        self._update_endpoints_by_errors()
        self._update_footer()

    def _update_header(self) -> None:
        ov = _overview(self.acc)
        elapsed_str = _elapsed_label(ov.elapsed_sec)

        health, health_style = _health_badge(self.acc)
        q_style = (
            "green"
            if ov.quarantined == 0
            else "yellow"
            if ov.quarantine_pct < 5
            else "red"
        )

        grid = Table.grid(expand=True, padding=(0, 2))
        for _ in range(5):
            grid.add_column(ratio=1)
        grid.add_row(
            Text("Lines", style="dim"),
            Text("Accepted", style="dim"),
            Text("Quarantined", style="dim"),
            Text("Accepted %", style="dim"),
            Text("Throughput", style="dim"),
        )
        grid.add_row(
            Text(f"{ov.lines:,}", style="bold cyan"),
            Text(f"{ov.accepted:,}", style="bold green"),
            Text(
                f"{ov.quarantined:,} ({ov.quarantine_pct:.1f}%)",
                style=f"bold {q_style}",
            ),
            Text(f"{ov.accept_pct:.1f}%", style="bold white"),
            Text(f"{ov.throughput:,.0f}/s", style="bold magenta"),
        )

        title = Text.assemble(
            (" logana ", "bold white on blue"),
            ("  ", ""),
            (health, health_style),
            (f"  {G.sep}  ", "dim"),
            ("elapsed ", "dim"),
            (elapsed_str, "bold white"),
        )
        self._paint("header", Group(title, _time_span_line(self.acc), grid), "Overview", "blue")

    def _update_alerts(self) -> None:
        ov = _overview(self.acc)
        if ov.lines == 0:
            body = Text("Reading log file…", style="dim italic")
            self._paint("alerts", body, "What needs attention", "yellow")
            return

        insights = generateInsights(self.acc)[:4]
        if not insights:
            body = Text(
                f"No issues flagged yet {G.dash} metrics look normal so far.",
                style="dim italic",
            )
        else:
            rows = []
            for item in insights:
                sev = item.get("severity", "info")
                icon = _SEVERITY_ICON.get(sev, G.dot)
                style = _SEVERITY_STYLE.get(sev, "white")
                rows.append(Text.assemble((f"{icon} ", style), (item["message"], style)))
            body = Group(*rows)
        self._paint(
            "alerts",
            body,
            "What needs attention",
            "yellow",
            subtitle="Actionable findings from this file",
        )

    def _update_error_rate(self) -> None:
        ov = _overview(self.acc)
        err_rate = ov.error_pct
        if err_rate >= 5:
            rate_style = "bold red"
        elif err_rate > 0:
            rate_style = "bold yellow"
        else:
            rate_style = "bold green"
        recent = [r * 100.0 for r in self.acc.errorRate.getRecentRates()]
        rows: list[Text] = [
            Text.assemble(
                (f"{err_rate:5.1f}%", rate_style),
                (" of accepted", "dim"),
            ),
            _metric_row("Error lines", f"{self.acc.errorRate.totalErrors:,}", "white"),
            _metric_row("Trend", _sparkline(recent), "cyan"),
        ]
        anomalies = self.acc.errorRate.anomalies
        if anomalies:
            last = anomalies[-1]
            if 3.0 <= abs(last.zScore) <= 50.0:
                rows.append(
                    Text.assemble(
                        ("Spike ", "bold red"),
                        (last.timestamp.strftime("%H:%M:%S"), "white"),
                        (f"  z={last.zScore:.1f}", "dim"),
                    )
                )
        self._paint("errorRate", Group(*rows), "Errors", "red")

    def _update_latency(self) -> None:
        digest = self.acc.latencyDigest
        if digest.count == 0:
            body: object = Group(
                Text("No latency data yet", style="dim"),
                Text("Need HTTP paths or response-time fields", style="dim italic"),
            )
        else:
            table = Table(show_header=False, box=None, pad_edge=False, expand=True)
            table.add_column(style="dim", width=8)
            table.add_column(justify="right")
            for label, val, style in (
                ("p50", digest.p50, "bold cyan"),
                ("p95", digest.p95, "bold yellow"),
                ("p99", digest.p99, "bold red"),
            ):
                table.add_row(label, Text(f"{val:,.0f} ms", style=style))
            table.add_row("n", Text(f"{digest.count:,}", style="dim"))
            body = table

        slowest = self.acc.endpointTable.getSortedEndpoints(sortBy="latency", limit=1)
        if slowest and slowest[0].p99Latency > 0 and slowest[0].count >= 3:
            ep = _truncate(slowest[0].endpoint, 28)
            ms = slowest[0].p99Latency
            slow_row = _metric_row("Slow p99", f"{ep} {ms:,.0f}ms", "magenta")
            body = Group(body, slow_row)
        self._paint("latency", body, "Latency", "green")

    def _update_snapshot(self) -> None:
        ov = _overview(self.acc)
        quality = self.acc.dataQuality.getOverallQualityScore() * 100.0
        q_style = "green" if quality >= 85 else "yellow" if quality >= 60 else "red"
        rows = [
            _metric_row(
                "Accepted",
                f"{ov.accept_pct:.1f}%",
                "green" if ov.accept_pct >= 90 else "yellow",
            ),
            _metric_row("Field quality", f"{quality:.1f}%", f"bold {q_style}"),
            _metric_row("Error groups", str(len(self.acc.errorClusterer.clusters)), "white"),
            _metric_row("Parsers", _format_mix(self.acc), "cyan"),
        ]
        drift = self.acc.formatTracker.driftEvents
        if drift:
            rows.append(_metric_row("Format drift", f"{len(drift)} switch(es)", "yellow"))
        self._paint(
            "snapshot",
            Group(*rows),
            "File snapshot",
            "blue",
            subtitle="Mix & parse health",
        )

    def _update_errors(self) -> None:
        table = Table(expand=True, box=_TABLE_BOX, show_lines=False, pad_edge=False)
        table.add_column("#", width=3, justify="right", style="dim")
        table.add_column("cnt", width=6, justify="right", style="bold")
        table.add_column("time", width=8, style="dim")
        table.add_column("pattern", ratio=3, no_wrap=False)
        table.add_column("paths", ratio=1, style="dim", no_wrap=False)

        clusters = self.acc.errorClusterer.getTopClusters(limit=5)
        if not clusters:
            table.add_row(
                G.dash,
                G.dash,
                G.dash,
                Text("No errors detected", style="dim italic"),
                G.dash,
            )
        else:
            for idx, cluster in enumerate(clusters):
                paths = ", ".join(sorted(cluster.endpoints)[:2]) or G.dash
                if len(cluster.endpoints) > 2:
                    paths += f" +{len(cluster.endpoints) - 2}"
                seen = (
                    cluster.lastSeen.strftime("%H:%M:%S")
                    if cluster.lastSeen
                    else G.dash
                )
                table.add_row(
                    str(idx + 1),
                    f"{cluster.count:,}",
                    seen,
                    _truncate(cluster.representative, 64),
                    paths,
                )
        self._paint(
            "errors",
            table,
            "Error patterns",
            "red",
            subtitle=f"Grouped by Drain3 {G.dash} variables masked",
        )

    def _endpoint_table(self, stats: list[EndpointStats], empty_msg: str) -> Table:
        table = Table(expand=True, box=_TABLE_BOX, show_lines=False, pad_edge=False)
        table.add_column("path", ratio=2, style="cyan", no_wrap=False)
        table.add_column("n", width=5, justify="right")
        table.add_column("err%", width=6, justify="right")
        table.add_column("p99", width=7, justify="right")
        table.add_column("trend", width=9, justify="center")

        if not stats:
            table.add_row(Text(empty_msg, style="dim italic"), G.dash, G.dash, G.dash, G.dash)
            return table

        for stat in stats:
            err_pct = stat.errorRate * 100.0
            if stat.trend == "DEGRADING":
                trend = Text(f"{G.down} latency", style="red")
            elif stat.trend == "IMPROVING":
                trend = Text(f"{G.up} latency", style="green")
            else:
                trend = Text(G.dash, style="dim")
            table.add_row(
                _truncate(stat.endpoint, 36),
                f"{stat.count:,}",
                Text(f"{err_pct:.1f}%", style=_err_pct_style(err_pct)),
                f"{stat.p99Latency:,.0f}ms" if stat.p99Latency else G.dash,
                trend,
            )
        return table

    def _update_endpoints_by_volume(self) -> None:
        stats = self.acc.endpointTable.getSortedEndpoints(sortBy="volume", limit=5)
        self._paint(
            "byVolume",
            self._endpoint_table(stats, "No HTTP paths yet"),
            "Most traffic",
            "cyan",
        )

    def _update_endpoints_by_errors(self) -> None:
        stats = [
            s
            for s in self.acc.endpointTable.getSortedEndpoints(sortBy="errorRate", limit=8)
            if s.count >= 3 and s.errors > 0
        ][:5]
        self._paint(
            "byErrors",
            self._endpoint_table(stats, "No endpoints with errors (≥3 reqs)"),
            "Highest error %",
            "red",
        )

    def _update_footer(self) -> None:
        diag = Table(show_header=False, box=None, pad_edge=False, expand=True)
        diag.add_column("Label", style="dim", width=14)
        diag.add_column("Detail", overflow="fold")

        breakdown = self.acc.quarantineTracker.getReasonBreakdown()
        quarantine = (
            G.mid.join(f"{reason} ({cnt:,})" for reason, cnt in list(breakdown.items())[:3])
            if breakdown
            else f"None {G.dash} all lines accepted"
        )
        diag.add_row("Quarantine", Text(quarantine, style="yellow"))

        weak = _weakest_fields(self.acc)
        diag.add_row(
            "Weak fields",
            ", ".join(f"{name} {val * 100:.0f}%" for name, val in weak) or G.dash,
        )

        lat = self.acc.latencyDigest
        if lat.lowConfidenceCount or lat.unknownCount:
            diag.add_row(
                "Latency gaps",
                Text(
                    f"low-confidence {lat.lowConfidenceCount:,}{G.mid}"
                    f"unknown {lat.unknownCount:,}",
                    style="dim",
                ),
            )

        hints: list[str] = []
        ov = _overview(self.acc)
        if ov.quarantine_pct > 5:
            hints.append(f"High quarantine {G.arrow} try --log-timezone or --reference-date")
        if lat.count == 0 and ov.accepted > 50:
            hints.append(f"No latency {G.arrow} file may be syslog-only or missing duration fields")
        if hints:
            diag.add_row("Tip", Text(G.mid.join(hints), style="italic cyan"))

        self._paint("footer", diag, "Diagnostics & next steps", "purple")
