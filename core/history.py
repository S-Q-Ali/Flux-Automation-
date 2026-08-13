import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path


class SessionHistory:
    def __init__(self, path=None):
        if path is None:
            path = Path(__file__).resolve().parent.parent / "session_history.jsonl"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = uuid.uuid4().hex[:12]
        self._lock = threading.Lock()

    def record(self, event, **data):
        entry = {
            "ts": time.time(),
            "iso": datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "event": event,
        }
        entry.update(data)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")