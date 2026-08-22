from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Notebook:
    """Append-only JSONL lab notebook, one file per agent slot."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        run_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, agent: str) -> Path:
        return self.run_dir / f"{agent}.jsonl"

    def log(self, agent: str, event_type: str, payload: Any) -> dict:
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "agent": agent,
            "type": event_type,
            "payload": payload,
        }
        with self.path_for(agent).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def entries(self, agent: str | None = None) -> list[dict]:
        paths = (
            sorted(self.run_dir.glob("*.jsonl"))
            if agent is None
            else [self.path_for(agent)]
        )
        out: list[dict] = []
        for path in paths:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.append(json.loads(line))
        return out
