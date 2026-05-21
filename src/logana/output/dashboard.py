import time
from logana.analytics.accumulatorSet import AccumulatorSet

try:
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    RICH_AVAILABLE = True
except ModuleNotFoundError:
    RICH_AVAILABLE = False

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
        def __init__(self, *args, name=None, size=None, **kwargs):
            self.name = name
            self.size = size
            self.children = {}
            self.renderable = None

        def split_column(self, *layouts):
            for layout in layouts:
                if layout.name:
                    self.children[layout.name] = layout

        def split_row(self, *layouts):
            self.split_column(*layouts)

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
            self.args = args
            self.kwargs = kwargs

    class Table:
        def __init__(self, *args, **kwargs):
            self.columns = []
            self.rows = []

        def add_column(self, name, *args, **kwargs):
            self.columns.append(name)

        def add_row(self, *values):
            self.rows.append(values)

    class Text:
        @staticmethod
        def assemble(*parts):
            chunks = []
            for part in parts:
                chunks.append(str(part[0] if isinstance(part, tuple) else part))
            return "".join(chunks)

    class Align:
        @staticmethod
        def center(renderable):
            return renderable

class Dashboard:
    """A GoAccess-style real-time terminal user interface dashboard using rich when available."""

    def __init__(self, accumulators: AccumulatorSet):
        self.acc = accumulators
        self.layout = self._buildLayout()
        self.lastRedraw = 0.0
        self.redrawInterval = 0.1

    def _buildLayout(self) -> Layout:
        """Constructs the TUI dashboard panel layout grid."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=6),
        )
        layout["body"].split_column(
            Layout(name="metrics", size=5),
            Layout(name="errors", size=10),
            Layout(name="endpoints", size=11),
        )
        layout["metrics"].split_row(
            Layout(name="errorRate"),
            Layout(name="latency"),
        )
        return layout

    def update(self) -> None:
        """Triggers a redraw of all widgets, throttled to 10 FPS internally."""
        now = time.monotonic()
        if now - self.lastRedraw < self.redrawInterval:
            return
        self.lastRedraw = now

        self._updateHeader()
        self._updateErrorRate()
        self._updateLatency()
        self._updateErrors()
        self._updateEndpoints()
        self._updateFooter()

    def _updateHeader(self) -> None:
        lines = self.acc.eventCounter.totalLines
        events = self.acc.eventCounter.totalEvents
        quarantined = self.acc.eventCounter.totalQuarantined
        qRate = self.acc.quarantineTracker.rate * 100.0
        tp = self.acc.eventCounter.throughput
        elapsed = self.acc.eventCounter.elapsedTime

        m, s = divmod(int(elapsed), 60)
        h, m = divmod(m, 60)
        elapsedStr = f"{h:02d}:{m:02d}:{s:02d}"

        headerText = Text.assemble(
            (" logana ", "bold white on blue"),
            ("  |  Lines: ", "dim"), (f"{lines:,}", "cyan"),
            ("  |  Events: ", "dim"), (f"{events:,}", "green"),
            ("  |  Quarantined: ", "dim"), (f"{quarantined:,} ({qRate:.2f}%)", "yellow" if quarantined == 0 else "red"),
            ("  |  Throughput: ", "dim"), (f"{tp:,.0f} lines/sec", "magenta"),
            ("  |  Elapsed: ", "dim"), (elapsedStr, "white")
        )

        self.layout["header"].update(Panel(Align.center(headerText), border_style="blue"))

    def _updateErrorRate(self) -> None:
        errRate = self.acc.errorRate.overallErrorRate * 100.0
        totalErr = self.acc.errorRate.totalErrors

        rates = self.acc.errorRate.getRecentRates()
        spark = ""
        for rate in rates[-12:]:
            if rate == 0:
                spark += " "
            elif rate < 0.05:
                spark += "."
            elif rate < 0.15:
                spark += ":"
            elif rate < 0.30:
                spark += "-"
            elif rate < 0.50:
                spark += "="
            else:
                spark += "#"

        parts = [
            ("Overall Error Rate: ", "dim"), (f"{errRate:.2f}% ({totalErr:,} total errors)\n", "bold red"),
            ("Rate Trend (sparkline): ", "dim"), (spark if spark else "[no data yet]", "bold green"),
        ]
        if self.acc.errorRate.anomalies:
            lastAnomaly = self.acc.errorRate.anomalies[-1]
            if 3.0 <= abs(lastAnomaly.zScore) <= 50.0:
                parts.append((
                    f" ! SPIKE at {lastAnomaly.timestamp.strftime('%H:%M:%S')} "
                    f"(z={lastAnomaly.zScore:.1f})",
                    "bold red",
                ))

        panelText = Text.assemble(*parts)
        self.layout["errorRate"].update(Panel(panelText, title="Error Analytics", border_style="red"))

    def _updateLatency(self) -> None:
        count = self.acc.latencyDigest.count
        if count == 0:
            panelText = Text("No response-time data in this file.", style="dim")
        else:
            p50 = self.acc.latencyDigest.p50
            p95 = self.acc.latencyDigest.p95
            p99 = self.acc.latencyDigest.p99
            minVal = self.acc.latencyDigest.min
            maxVal = self.acc.latencyDigest.max
            panelText = Text.assemble(
                ("Median (p50): ", "dim"), (f"{p50:.1f} ms", "cyan"),
                ("  |  p95: ", "dim"), (f"{p95:.1f} ms", "yellow"),
                ("  |  p99: ", "dim"), (f"{p99:.1f} ms\n", "bold red"),
                ("Min: ", "dim"), (f"{minVal:.1f} ms", "green"),
                ("  |  Max: ", "dim"), (f"{maxVal:.1f} ms", "magenta"),
                ("  |  High-Conf Samples: ", "dim"), (f"{count:,}", "white"),
            )
        self.layout["latency"].update(Panel(panelText, title="Latency Digest", border_style="green"))

    def _updateErrors(self) -> None:
        table = Table(expand=True, box=None)
        table.add_column("Rank", width=5, justify="center")
        table.add_column("Count", width=8, justify="right")
        table.add_column("Error Message Pattern", style="bold red")
        table.add_column("Impacted Endpoints", style="dim italic")

        topClusters = self.acc.errorClusterer.getTopClusters(limit=5)
        for idx, cluster in enumerate(topClusters):
            msg = cluster.representative
            if len(msg) > 80:
                msg = msg[:77] + "..."
            endpointsStr = ", ".join(list(cluster.endpoints)[:3]) or "(none)"
            table.add_row(str(idx + 1), f"{cluster.count:,}", msg, endpointsStr)

        self.layout["errors"].update(Panel(table, title="Top Error Patterns", border_style="red"))

    def _updateEndpoints(self) -> None:
        table = Table(expand=True, box=None)
        table.add_column("Endpoint (URL Path)", style="bold cyan")
        table.add_column("Requests", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Error %", justify="right")
        table.add_column("p99 Latency", justify="right")
        table.add_column("Trend Direction", justify="center")

        topEndpoints = self.acc.endpointTable.getSortedEndpoints(sortBy="volume", limit=5)
        for stat in topEndpoints:
            if stat.trend == "DEGRADING":
                trendText = "[bold red]DEGRADING[/]"
            elif stat.trend == "IMPROVING":
                trendText = "[bold green]IMPROVING[/]"
            else:
                trendText = "STABLE"

            table.add_row(
                stat.endpoint,
                f"{stat.count:,}",
                f"{stat.errors:,}",
                f"{stat.errorRate * 100.0:.2f}%",
                f"{stat.p99Latency:.1f}ms",
                trendText
            )

        self.layout["endpoints"].update(Panel(table, title="Active Endpoints Performance", border_style="cyan"))

    def _updateFooter(self) -> None:
        score = self.acc.dataQuality.getOverallQualityScore() * 100.0

        driftText = "No format switches detected."
        driftStyle = "white"
        if self.acc.formatTracker.driftEvents:
            nSwitches = len(self.acc.formatTracker.driftEvents)
            lastDrift = self.acc.formatTracker.driftEvents[-1]
            driftText = f"{nSwitches} format switch(es), latest on line {lastDrift.lineNumber:,}: {lastDrift.fromFormat} -> {lastDrift.toFormat}"
            driftStyle = "bold yellow"

        # Build a per-field quality breakdown showing the 3 weakest fields
        fieldScores = []
        for f in self.acc.dataQuality.FIELDS:
            rates = self.acc.dataQuality.getFieldQualityRates(f)
            fieldScores.append((f, rates["known"]))
        fieldScores.sort(key=lambda x: x[1])
        weakest = fieldScores[:3]
        weakStr = ", ".join(f"{name} {val*100:.0f}%" for name, val in weakest)

        qualityColor = "green" if score >= 85 else "yellow" if score >= 60 else "red"

        q_breakdown = self.acc.quarantineTracker.getReasonBreakdown()
        q_text = "No quarantined lines."
        if q_breakdown:
            top = next(iter(q_breakdown.items()))
            q_text = f"{top[0]} ({top[1]}x)"

        panelText = Text.assemble(
            ("Schema: ", "dim"), (f"{driftText}\n", driftStyle),
            ("Quarantine: ", "dim"), (f"{q_text}\n", "yellow"),
            ("Data Quality: ", "dim"), (f"{score:.1f}%", f"bold {qualityColor}"),
            ("  |  Weakest Fields: ", "dim"), (weakStr, "yellow"),
        )
        self.layout["footer"].update(Panel(panelText, title="Diagnostics", border_style="purple"))
