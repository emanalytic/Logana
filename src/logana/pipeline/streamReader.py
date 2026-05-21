import gzip
import os
from typing import Generator

def streamReader(
    filePath: str,
    encoding: str = "utf-8",
) -> Generator[str, None, None]:
    """Reads a file line by line with UTF-8/latin-1 fallback and optional gzip."""
    if not os.path.exists(filePath):
        raise FileNotFoundError(f"Log file not found at path: {filePath}")

    open_path = filePath
    use_gzip = filePath.endswith(".gz")

    def _open_text(path: str, enc: str):
        if use_gzip:
            return gzip.open(path, mode="rt", encoding=enc, errors="replace")
        return open(path, mode="r", encoding=enc, errors="replace")

    try:
        with _open_text(open_path, encoding) as handle:
            for line in handle:
                if line.startswith("\ufeff"):
                    line = line.lstrip("\ufeff")
                yield line
    except (UnicodeDecodeError, OSError):
        with _open_text(open_path, "latin-1") as handle:
            for line in handle:
                yield line
