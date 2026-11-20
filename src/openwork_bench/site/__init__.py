"""Build the static leaderboard site: one self-contained HTML file with the data embedded."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

TEMPLATE = Path(__file__).with_name("template.html")


def build_site(leaderboard: Path, out_dir: Path) -> Path:
    data = json.loads(Path(leaderboard).read_text())
    # Escape "</" so the JSON can never close the <script> tag it is embedded in.
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("__OWB_DATA__", payload)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html)
    shutil.copyfile(leaderboard, out_dir / "leaderboard.json")
    return out_dir / "index.html"
