from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixturesDir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def complexLogPath(fixturesDir: Path) -> str:
    return str(fixturesDir / "complex.log")


@pytest.fixture
def sample2LogPath(fixturesDir: Path) -> str:
    return str(fixturesDir / "sample2.log")


@pytest.fixture
def hdfsLogPath(fixturesDir: Path) -> str:
    return str(fixturesDir / "hdfs_sample.log")
