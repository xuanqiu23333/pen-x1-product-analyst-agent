from pathlib import Path
import csv
import json
from app.schemas.models import Fact


def load_project_facts(data_root: Path) -> dict[str, Fact]:
    payload = json.loads((data_root / "internal" / "pen_x1.json").read_text(encoding="utf-8-sig"))
    result: dict[str, Fact] = {}
    for key, value in payload.items():
        if key in {"data_nature", "source_name"}:
            continue
        result[key] = Fact(id=key, category="project", name=key.replace("_", " "), value=value, source_name=payload["source_name"], data_nature="FACT")
    return result


def load_json(data_root: Path, relative_path: str):
    return json.loads((data_root / relative_path).read_text(encoding="utf-8-sig"))


def load_reviews(data_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((data_root / "reviews").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source:
            rows.extend(csv.DictReader(source))
    unique: dict[str, dict[str, str]] = {row["review_id"]: row for row in rows}
    return list(unique.values())
