import hashlib
from pathlib import Path


def checksum(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: str | Path) -> list[dict]:
    import csv
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def read_parquet(path: str | Path) -> list[dict]:
    import pyarrow.parquet as pq
    table = pq.read_table(str(path))
    return table.to_pylist()
