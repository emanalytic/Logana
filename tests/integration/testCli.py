from click.testing import CliRunner

from logana.cli.cliMain import main


def test_cliSummaryRunsOnFixture(openStackLogPath: str):
    result = CliRunner().invoke(main, [openStackLogPath, "--log-timezone", "UTC"])
    assert result.exit_code == 0
    assert "Log ingestion processed" in result.output


def test_cliDashboardRunsOnFixture(openStackLogPath: str):
    result = CliRunner().invoke(
        main, [openStackLogPath, "--format", "dashboard", "--log-timezone", "UTC"]
    )
    assert result.exit_code == 0
