from __future__ import annotations

import json
import logging
import os
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib import error, request
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LangSmithRun:
    id: str
    name: str
    run_type: str
    parent_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LangSmithClient:
    def __init__(self) -> None:
        self.enabled = os.environ.get("LANGSMITH_TRACING", "").strip().lower() == "true"
        self.api_key = os.environ.get("LANGSMITH_API_KEY", "").strip()
        self.endpoint = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com").strip().rstrip("/")
        self.project = os.environ.get("LANGSMITH_PROJECT", "local-reliability-lab").strip() or "local-reliability-lab"
        self.workspace_id = os.environ.get("LANGSMITH_WORKSPACE_ID", "").strip()
        self.timeout_seconds = self._parse_timeout(os.environ.get("LANGSMITH_TIMEOUT_SECONDS", "2.5"))
        self.available = self.enabled and bool(self.api_key)
        self._queue: queue.Queue[tuple[str, str, dict[str, Any]]] = queue.Queue(maxsize=256)
        self._worker: threading.Thread | None = None

        if self.available:
            self._worker = threading.Thread(target=self._drain_queue, name="langsmith-tracing", daemon=True)
            self._worker.start()

    def _parse_timeout(self, raw_value: str) -> float:
        default = 2.5
        try:
            parsed = float(raw_value)
        except (TypeError, ValueError):
            logging.warning(
                "Invalid LANGSMITH_TIMEOUT_SECONDS '%s'; falling back to %.1f seconds",
                raw_value,
                default,
            )
            return default
        return min(max(parsed, 0.2), 5.0)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }
        if self.workspace_id:
            headers["x-tenant-id"] = self.workspace_id
        return headers

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> None:
        if not self.available:
            return

        req = request.Request(
            url=f"{self.endpoint}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds):
                return
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logging.info(
                json.dumps(
                    {
                        "event": "langsmith_trace_error",
                        "status": exc.code,
                        "path": path,
                        "detail": detail[:500],
                    }
                )
            )
        except Exception as exc:  # noqa: BLE001
            logging.info(
                json.dumps(
                    {
                        "event": "langsmith_trace_error",
                        "path": path,
                        "detail": str(exc),
                    }
                )
            )

    def _enqueue(self, method: str, path: str, payload: dict[str, Any]) -> None:
        if not self.available:
            return
        try:
            self._queue.put_nowait((method, path, payload))
        except queue.Full:
            logging.info(json.dumps({"event": "langsmith_trace_dropped", "path": path, "reason": "queue_full"}))

    def _drain_queue(self) -> None:
        while True:
            method, path, payload = self._queue.get()
            try:
                self._request(method, path, payload)
            finally:
                self._queue.task_done()

    def start_run(
        self,
        name: str,
        run_type: str,
        inputs: dict[str, Any],
        parent_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> LangSmithRun | None:
        if not self.available:
            return None

        run = LangSmithRun(
            id=str(uuid4()),
            name=name,
            run_type=run_type,
            parent_run_id=parent_run_id,
            metadata=metadata or {},
        )
        payload: dict[str, Any] = {
            "id": run.id,
            "name": name,
            "run_type": run_type,
            "inputs": inputs,
            "start_time": _utc_now(),
            "session_name": self.project,
        }
        if parent_run_id:
            payload["parent_run_id"] = parent_run_id
        if metadata:
            payload["extra"] = {"metadata": metadata}
        if tags:
            payload["tags"] = tags
        self._enqueue("POST", "/runs", payload)
        return run

    def end_run(
        self,
        run: LangSmithRun | None,
        outputs: dict[str, Any] | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if run is None or not self.available:
            return

        payload: dict[str, Any] = {
            "end_time": _utc_now(),
        }
        if outputs is not None:
            payload["outputs"] = outputs
        if error_message:
            payload["error"] = error_message
        merged_metadata = dict(run.metadata)
        if metadata:
            merged_metadata.update(metadata)
        if merged_metadata:
            payload["extra"] = {"metadata": merged_metadata}
        self._enqueue("PATCH", f"/runs/{run.id}", payload)
