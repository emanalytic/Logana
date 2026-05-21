import time
from typing import List, Sequence, Tuple

from logana.analytics.accumulatorSet import AccumulatorSet
from logana.output.insightReport import generateInsights

try:
    from rich import box
    from rich.console import Group
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ModuleNotFoundError:
    RICH_AVAILABLE = False
    box = None  # type: ignore[assignment]

    class Live:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update(self, *args, **kwargs):
            pass

    class Layout:
        def __init__(self, *args, name=None, size=None, ratio=None, **kwargs):
            self.name = name
            self.size = size
            self.children = {}
            self.renderable = None

        def split_column(self, *layouts):
            for layout in layouts:
                if layout.name:
                    self.children[layout.name] = layout

        def split_row(self, *layouts):
            for layout in layouts:
                if layout.name:
                    self.children[layout.name] = layout

        def update(self, renderable):
            self.renderable = renderable

        def __getitem__(self, name):
            if name in self.children:
                return self.children[name]
            for child in self.children.values():
                try:
                    return child[name]
                except KeyError:
                    continue
            raise KeyError(name)

        def __contains__(self, name):
            return name in self.children

    class Panel:
        def __init__(self, renderable, *args, **kwargs):
            self.renderable = renderable

    class Table:
        def __init__(self, *args, **kwargs):
            self.columns = []
            self.rows = []

        def add_column(self, name, *args, **kwargs):
            self.columns.append(name)

        def add_row(self, *values):
            self.rows.append(values)

        @classmethod
        def grid(cls, *args, **kwargs):
            return cls()

    class Text:
        @staticmethod
        def assemble(*parts):
            return "".join(str(p[0] if isinstance(p, tuple) else p) for p in parts)

        def __init__(self, text="", style=""):
            self.text = text

    class Group:
        def __init__(self, *items):
            self.items = items

_PANEL_PAD = (0, 1)
_TABLE_BOX = box.SIMPLE_HEAD if RICH_AVAILABLE else None
_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"
_SEVERITY_STYLE = {"alert": "bold red", "warn": "bold yellow", "info": "cyan"}
_SEVERITY_ICON = {"alert": "!!", "warn": "!", "info": "·"}


def _sparkline(values: Sequence[float], width: int = 16) -> str:
    if not values:
        return "—"
    window = list(values[-width:])
    peak = max(window) or 1e-9
    chars: List[str] = []
    for value in window:
        if value <= 0:
            chars.append(" ")
            continue
        idx = min(int((value / peak) * (len(_SPARK_BLOCKS) - 1)), len(_SPARK_BLOCKS) - 1)
        chars.append(_SPARK_BLOCKS[idx])
    return "".join(chars)


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
    return Text.assemble((f"{label:<13}", "dim"), (value, value_style))


def _health_status(acc: AccumulatorSet) -> Tuple[str, str]:
    """Overall health label and Rich style for the header badge."""
    q_rate = acc.quarantineTracker.rate * 100.0
    err_rate = acc.errorRate.overallErrorRate * 100.0

    if err_rate >= 10.0 or q_rate >= 15.0:
        return "CRITICAL", "bold white on red"
    if err_rate >= 2.0 or q_rate >= 5.0 or acc.errorRate.anomalies:
        return "DEGRADED", "bold black on yellow"
    return "HEALTHY", "bold white on green"


def _time_span_line(acc: AccumulatorSet) -> Text:
    span = acc.logTimeSpan.toDict()
    if not span.get("available"):
        return Text("Log time range: not enough timestamps yet", style="dim italic")
    first = span["first"]
    last = span["last"]
    seconds = span.get("spanSeconds") or 0
    if seconds >= 3600:
        duration = f"{seconds / 3600:.1f}h"
    elif seconds >= 60:
        duration = f"{seconds / 60:.0f}m"
    else:
        duration = f"{seconds:.0f}s"
    return Text.assemble(
        ("Coverage ", "dim"),
        (f"{duration}", "bold white"),
        ("  from ", "dim"),
        (first[11:19] if len(first) > 19 else first, "cyan"),
        (" → ", "dim"),
        (last[11:19] if len(last) > 19 else last, "cyan"),
    )


def _format_mix(acc: AccumulatorSet, limit: int = 4) -> str:
    dist = acc.fileProfile.toDict().get("formatDistribution", {})
    if not dist:
        return "—"
    total = sum(dist.values()) or 1
    parts = []
    for name, count in list(dist.items())[:limit]:
        pct = 100.0 * count / total
        parts.append(f"{name} {pct:.0f}%")
    return " · ".join(parts)


class Dashboard:
    """Live terminal dashboard: KPIs, alerts, errors, endpoints, and diagnostics."""

    def __init__(self, accumulators: AccumulatorSet):
        self.acc = accumulators
        self.layout = self._buildLayout()
        self.lastRedraw = 0.0
        self.redrawInterval = 0.1

    def _buildLayout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=8),
            Layout(name="alerts", size=6),
            Layout(name="body"),
            Layout(name="footer", size=9),
        )
        layout["body"].split_column(
            Layout(name="metrics", size=11),
            Layout(name="errors", size=12),
            Layout(name="endpoints", size=14),
        )
        layout["metrics"].split_row(
            Layout(name="errorRate", ratio=1),
            Layout(name="latency", ratio=1),
            Layout(name="snapshot", ratio=1),
        )
        layout["endpoints"].split_row(
            Layout(name="byVolume", ratio=1),
            Layout(name="byErrors", ratio=1),
        )
        return layout

    def update(self) -> None:
        now = time.monotonic()
        if now - self.lastRedraw < self.redrawInterval:
            return
        self.lastRedraw = now

        self._updateHeader()
        self._updateAlerts()
        self._updateErrorRate()
        self._updateLatency()
        self._updateSnapshot()
        self._updateErrors()
        self._updateEndpointsByVolume()
        self._updateEndpointsByErrors()
        self._updateFooter()

    def _updateHeader(self) -> None:
        lines = self.acc.eventCounter.totalLines
        events = self.acc.eventCounter.totalEvents
        quarantined = self.acc.eventCounter.totalQuarantined
        q_rate = self.acc.quarantineTracker.rate * 100.0
        throughput = self.acc.eventCounter.throughput
        elapsed = self.acc.eventCounter.elapsedTime
        parse_pct = (100.0 * events / lines) if lines else 0.0

        m, s = divmod(int(elapsed), 60)
        h, m = divmod(m, 60)
        elapsed_str = f"{h:02d}:{m:02d}:{s:02d}"

        health, health_style = _health_status(self.acc)
        q_style = "green" if quarantined == 0 else "yellow" if q_rate < 5 else "red"

        grid = Table.grid(expand=True, padding=(0, 2))
        for _ in range(5):
            grid.add_column(ratio=1)
        grid.add_row(
            Text("Lines", style="dim"),
            Text("Accepted", style="dim"),
            Text("Quarantined", style="dim"),
            Text("Parse rate", style="dim"),
            Text("Throughput", style="dim"),
        )
        grid.add_row(
            Text(f"{lines:,}", style="bold cyan"),
            Text(f"{events:,}", style="bold green"),
            Text(f"{quarantined:,} ({q_rate:.1f}%)", style=f"bold {q_style}"),
            Text(f"{parse_pct:.0f}%", style="bold white"),
            Text(f"{throughput:,.0f}/s", style="bold magenta"),
        )

        title = Text.assemble(
            (" logana ", "bold white on blue"),
            ("  ", ""),
            (health, health_style),
            ("  ·  ", "dim"),
            ("elapsed ", "dim"),
            (elapsed_str, "bold white"),
        )

        self.layout["header"].update(
            _panel(Group(title, _time_span_line(self.acc), "", grid), "Overview", "blue")
        )

    def _updateAlerts(self) -> None:
        insights = generateInsights(self.acc)[:4]
        if not insights:
            body = Text("No issues flagged yet — keep watching as the file streams.", style="dim italic")
        else:
            rows: List[Text] = []
            for item in insights:
                sev = item.get("severity", "info")
                icon = _SEVERITY_ICON.get(sev, "·")
                style = _SEVERITY_STYLE.get(sev, "white")
                rows.append(Text.assemble((f"{icon} ", style), (item["message"], style)))
            body = Group(*rows)

        self.layout["alerts"].update(
            _panel(body, "What needs attention", "yellow", subtitle="Actionable findings from this file")
        )

    def _updateErrorRate(self) -> None:
        err_rate = self.acc.errorRate.overallErrorRate * 100.0
        total_err = self.acc.errorRate.totalErrors
        rates = [r * 100.0 for r in self.acc.errorRate.getRecentRates()]
        spark = _sparkline(rates)

        rows: List[Text] = [
            Text.assemble(
                (f"{err_rate:5.1f}%", "bold red" if err_rate >= 5 else "bold yellow" if err_rate > 0 else "bold green"),
                ("  of events are errors", "dim"),
            ),
            _metric_row("Error events", f"{total_err:,}", "white"),
            _metric_row("Trend", spark, "cyan"),
        ]

        if self.acc.errorRate.anomalies:
            last = self.acc.errorRate.anomalies[-1]
            if 3.0 <= abs(last.zScore) <= 50.0:
                rows.append(
                    Text.assemble(
                        ("Spike ", "bold red"),
                        (last.timestamp.strftime("%H:%M:%S"), "white"),
                        (f"  z={last.zScore:.1f}", "dim"),
                    )
                )

        self.layout["errorRate"].update(_panel(Group(*rows), "Errors", "red"))

    def _updateLatency(self) -> None:
        count = self.acc.latencyDigest.count
        if count == 0:
            body = Group(
                Text("No latency data yet", style="dim"),
                Text("Need HTTP paths or response-time fields", style="dim italic"),
            )
        else:
            p50 = self.acc.latencyDigest.p50
            p95 = self.acc.latencyDigest.p95
            p99 = self.acc.latencyDigest.p99
            table = Table(show_header=False, box=None, pad_edge=False, expand=True)
            table.add_column(style="dim", width=8)
            table.add_column(justify="right")
            table.add_row("p50", Text(f"{p50:,.0f} ms", style="bold cyan"))
            table.add_row("p95", Text(f"{p95:,.0f} ms", style="bold yellow"))
            table.add_row("p99", Text(f"{p99:,.0f} ms", style="bold red"))
            table.add_row("n", Text(f"{count:,}", style="dim"))
            body = table

        slowest = self.acc.endpointTable.getSortedEndpoints(sortBy="latency", limit=1)
        if slowest and slowest[0].p99Latency > 0 and slowest[0].count >= 3:
            ep = slowest[0].endpoint
            if len(ep) > 28:
                ep = ep[:25] + "..."
            body = Group(
                body,
                Text(""),
                _metric_row("Slowest p99", f"{ep} ({slowest[0].p99Latency:,.0f} ms)", "magenta"),
            )

        self.layout["latency"].update(_panel(body, "Latency", "green"))

    def _updateSnapshot(self) -> None:
        profile = self.acc.fileProfile.toDict()
        parse_rate = profile.get("parseRate", 0.0) * 100.0
        clusters = len(self.acc.errorClusterer.clusters)
        quality = self.acc.dataQuality.getOverallQualityScore() * 100.0
        q_color = "green" if quality >= 85 else "yellow" if quality >= 60 else "red"

        rows = [
            _metric_row("Parse OK", f"{parse_rate:.0f}%", "green" if parse_rate >= 90 else "yellow"),
            _metric_row("Field quality", f"{quality:.0f}%", f"bold {q_color}"),
            _metric_row("Error groups", f"{clusters}", "white"),
            _metric_row("Formats", _format_mix(self.acc), "cyan"),
        ]

        if self.acc.formatTracker.driftEvents:
            n = len(self.acc.formatTracker.driftEvents)
            rows.append(_metric_row("Format drift", f"{n} switch(es)", "yellow"))

        self.layout["snapshot"].update(
            _panel(Group(*rows), "File snapshot", "blue", subtitle="Mix & parse health")
        )

    def _updateErrors(self) -> None:
        table = Table(expand=True, box=_TABLE_BOX, show_lines=True, pad_edge=True)
        table.add_column("#", width=3, justify="right", style="dim")
        table.add_column("×", width=7, justify="right", style="bold")
        table.add_column("Last seen", width=9, style="dim")
        table.add_column("Pattern (Drain template)", ratio=2)
        table.add_column("Paths", ratio=1, style="dim")

        top = self.acc.errorClusterer.getTopClusters(limit=5)
        if not top:
            table.add_row("—", "—", "—", Text("No errors detected", style="dim italic"), "—")
        else:
            for idx, cluster in enumerate(top):
                msg = cluster.representative
                if len(msg) > 64:
                    msg = msg[:61] + "..."
                paths = ", ".join(sorted(cluster.endpoints)[:2]) or "—"
                if len(cluster.endpoints) > 2:
                    paths += f" +{len(cluster.endpoints) - 2}"
                seen = cluster.lastSeen.strftime("%H:%M:%S")
                table.add_row(str(idx + 1), f"{cluster.count:,}", seen, msg, paths)

        self.layout["errors"].update(
            _panel(table, "Error patterns", "red", subtitle="Grouped by Drain3 — variables masked")
        )

    def _endpoint_table(self, stats_list, empty_msg: str) -> Table:
        table = Table(expand=True, box=_TABLE_BOX, show_lines=True, pad_edge=True)
        table.add_column("Path", ratio=2, style="cyan")
        table.add_column("n", width=6, justify="right")
        table.add_column("err%", width=7, justify="right")
        table.add_column("p99", width=8, justify="right")
        table.add_column("", width=10, justify="center")

        if not stats_list:
            table.add_row(Text(empty_msg, style="dim italic"), "—", "—", "—", "—")
            return table

        for stat in stats_list:
            path = stat.endpoint
            if len(path) > 36:
                path = path[:33] + "..."
            err_pct = stat.errorRate * 100.0
            err_style = "red" if err_pct >= 10 else "yellow" if err_pct > 0 else "green"
            if stat.trend == "DEGRADING":
                trend = Text("▼ latency", style="red")
            elif stat.trend == "IMPROVING":
                trend = Text("▲ latency", style="green")
            else:
                trend = Text("—", style="dim")
            table.add_row(
                path,
                f"{stat.count:,}",
                Text(f"{err_pct:.1f}%", style=err_style),
                f"{stat.p99Latency:,.0f}ms" if stat.p99Latency else "—",
                trend,
            )
        return table

    def _updateEndpointsByVolume(self) -> None:
        stats = self.acc.endpointTable.getSortedEndpoints(sortBy="volume", limit=5)
        self.layout["byVolume"].update(
            _panel(
                self._endpoint_table(stats, "No HTTP paths yet"),
                "Most traffic",
                "cyan",
            )
        )

    def _updateEndpointsByErrors(self) -> None:
        stats = [
            s
            for s in self.acc.endpointTable.getSortedEndpoints(sortBy="errorRate", limit=8)
            if s.count >= 3 and s.errors > 0
        ][:5]
        self.layout["byErrors"].update(
            _panel(
                self._endpoint_table(stats, "No endpoints with errors (≥3 reqs)"),
                "Highest error %",
                "red",
            )
        )

    def _updateFooter(self) -> None:
        diag = Table(show_header=False, box=None, pad_edge=False, expand=True)
        diag.add_column("Label", style="dim", width=14)
        diag.add_column("Detail", overflow="fold")

        q_breakdown = self.acc.quarantineTracker.getReasonBreakdown()
        if q_breakdown:
            parts = [f"{reason} ({cnt:,})" for reason, cnt in list(q_breakdown.items())[:3]]
            quarantine = " · ".join(parts)
        else:
            quarantine = "None — all lines accepted"

        weak_fields: List[Tuple[str, float]] = []
        for field in self.acc.dataQuality.FIELDS:
            rates = self.acc.dataQuality.getFieldQualityRates(field)
            weak_fields.append((field, rates["known"]))
        weak_fields.sort(key=lambda x: x[1])
        weak = ", ".join(f"{name} {val * 100:.0f}%" for name, val in weak_fields[:3])

        diag.add_row("Quarantine", Text(quarantine, style="yellow"))
        diag.add_row("Weak fields", weak)

        if self.acc.latencyDigest.lowConfidenceCount or self.acc.latencyDigest.unknownCount:
            diag.add_row(
                "Latency gaps",
                Text(
                    f"low-confidence {self.acc.latencyDigest.lowConfidenceCount:,} · "
                    f"unknown {self.acc.latencyDigest.unknownCount:,}",
                    style="dim",
                ),
            )

        hints: List[str] = []
        q_rate = self.acc.quarantineTracker.rate * 100.0
        if q_rate > 5:
            hints.append("High quarantine → try --log-timezone or --reference-date")
        if self.acc.latencyDigest.count == 0 and self.acc.eventCounter.totalEvents > 50:
            hints.append("No latency → file may be syslog-only or missing duration fields")
        if hints:
            diag.add_row("Tip", Text(" · ".join(hints), style="italic cyan"))

        self.layout["footer"].update(
            _panel(diag, "Diagnostics & next steps", "purple")
        )
