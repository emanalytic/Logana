from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixturesDir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def openStackLogPath(fixturesDir: Path) -> str:
    return str(fixturesDir / "OpenStack_2k.log")


@pytest.fixture
def linuxLogPath(fixturesDir: Path) -> str:
    return str(fixturesDir / "Linux_2k.log")


@pytest.fixture
def hdfsLogPath(fixturesDir: Path) -> str:
    return str(fixturesDir / "HDFS_2k.log")
