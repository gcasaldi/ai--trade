"""Package only site assets and the public dashboard export for GitHub Pages."""
import argparse
import json
from pathlib import Path
import shutil


def build(source: Path, output: Path, snapshot: Path | None = None, failed=False):
    output.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "app.js", "planner.js"):
        shutil.copyfile(source / name, output / name)
    payload = {"schema_version": 1, "status": "waiting", "assets": []}
    if snapshot and snapshot.exists():
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("assets"), list):
            raise ValueError("Invalid public dashboard schema")
    if failed:
        payload["status"] = "unavailable"
    (output / "data.json").write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    (output / ".nojekyll").touch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument("--failed", action="store_true")
    args = parser.parse_args()
    build(Path(__file__).resolve().parents[1] / "site", args.output, args.snapshot, args.failed)
