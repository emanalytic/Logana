from click.testing import CliRunner
from logana.cli.cliMain import main


def test_cliSummaryRunsOnFixture(complexLogPath: str):
    result = CliRunner().invoke(main, [complexLogPath])
    assert result.exit_code == 0
    assert "Log ingestion processed" in result.output


def test_cliDashboardRunsOnFixture(complexLogPath: str):
    result = CliRunner().invoke(main, [complexLogPath, "--format", "dashboard"])
    assert result.exit_code == 0
