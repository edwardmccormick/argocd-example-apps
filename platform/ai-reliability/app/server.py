from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from engine import answer_question, load_corpus


logging.basicConfig(level=logging.INFO, format="%(message)s")

CORPUS_DIR = os.environ.get("AI_CORPUS_DIR", "/corpus")
PORT = int(os.environ.get("PORT", "8080"))
TOP_K = int(os.environ.get("TOP_K", "3"))
DEFAULT_MODE = os.environ.get("AI_DEFAULT_MODE", "extractive").strip().lower()


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.request_counts = Counter()
        self.workflow_counts = Counter()
        self.structured_counts = Counter()
        self.retrieval_hits = Counter()
        self.token_counts = Counter()
        self.duration_buckets = Counter()
        self.duration_sum = Counter()
        self.duration_count = Counter()
        self.buckets = [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]

    def observe(
        self,
        status: str,
        result: str,
        structured_valid: bool,
        hits: int,
        duration_seconds: float,
        mode: str,
        token_usage: dict | None = None,
    ) -> None:
        with self._lock:
            self.request_counts[(status, mode)] += 1
            self.workflow_counts[(result, mode)] += 1
            self.structured_counts[("valid" if structured_valid else "invalid", mode)] += 1
            self.retrieval_hits[mode] += hits
            self.retrieval_hits["total"] += hits
            if token_usage:
                self.token_counts[("prompt", mode)] += int(token_usage.get("prompt_estimate", 0))
                self.token_counts[("response", mode)] += int(token_usage.get("response_estimate", 0))
            self.duration_sum[mode] += duration_seconds
            self.duration_sum["total"] += duration_seconds
            self.duration_count[mode] += 1
            self.duration_count["total"] += 1
            for bucket in self.buckets:
                if duration_seconds <= bucket:
                    self.duration_buckets[(bucket, mode)] += 1
                    self.duration_buckets[(bucket, "total")] += 1
            self.duration_buckets[("+Inf", mode)] += 1
            self.duration_buckets[("+Inf", "total")] += 1

    def render(self) -> str:
        lines = [
            "# HELP ai_docqa_requests_total Total requests served by the document QA endpoint.",
            "# TYPE ai_docqa_requests_total counter",
        ]
        for (status, mode), count in sorted(self.request_counts.items()):
            lines.append(f'ai_docqa_requests_total{{endpoint="/ask",status="{status}",mode="{mode}"}} {count}')

        lines.extend(
            [
                "# HELP ai_docqa_workflow_completions_total End-to-end request outcomes.",
                "# TYPE ai_docqa_workflow_completions_total counter",
            ]
        )
        for (result, mode), count in sorted(self.workflow_counts.items()):
            lines.append(f'ai_docqa_workflow_completions_total{{result="{result}",mode="{mode}"}} {count}')

        lines.extend(
            [
                "# HELP ai_docqa_structured_output_total Structured output validation outcomes.",
                "# TYPE ai_docqa_structured_output_total counter",
            ]
        )
        for (result, mode), count in sorted(self.structured_counts.items()):
            lines.append(f'ai_docqa_structured_output_total{{result="{result}",mode="{mode}"}} {count}')

        lines.extend(
            [
                "# HELP ai_docqa_retrieval_hits_total Total citations returned across all requests.",
                "# TYPE ai_docqa_retrieval_hits_total counter",
            ]
        )
        for mode, count in sorted(self.retrieval_hits.items()):
            lines.append(f'ai_docqa_retrieval_hits_total{{mode="{mode}"}} {count}')

        lines.extend(
            [
                "# HELP ai_docqa_token_usage_total Estimated or provider-reported token usage.",
                "# TYPE ai_docqa_token_usage_total counter",
            ]
        )
        for (kind, mode), count in sorted(self.token_counts.items()):
            lines.append(f'ai_docqa_token_usage_total{{kind="{kind}",mode="{mode}"}} {count}')

        lines.extend(
            [
                "# HELP ai_docqa_request_duration_seconds Request duration histogram.",
                "# TYPE ai_docqa_request_duration_seconds histogram",
            ]
        )
        rendered_modes = sorted({mode for (_, mode) in self.duration_buckets.keys()} | {"total"})
        for bucket in self.buckets:
            for mode in rendered_modes:
                lines.append(
                    f'ai_docqa_request_duration_seconds_bucket{{le="{bucket}",mode="{mode}"}} {self.duration_buckets[(bucket, mode)]}'
                )
        for mode in rendered_modes:
            lines.append(
                f'ai_docqa_request_duration_seconds_bucket{{le="+Inf",mode="{mode}"}} {self.duration_buckets[("+Inf", mode)]}'
            )
        for mode in rendered_modes:
            lines.append(f'ai_docqa_request_duration_seconds_sum{{mode="{mode}"}} {self.duration_sum[mode]}')
            lines.append(f'ai_docqa_request_duration_seconds_count{{mode="{mode}"}} {self.duration_count[mode]}')
        return "\n".join(lines) + "\n"


METRICS = Metrics()
CHUNKS = load_corpus(CORPUS_DIR)


class Handler(BaseHTTPRequestHandler):
    server_version = "ai-docqa/0.1"

    def _parsed_path(self):
        return urlparse(self.path)

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, payload: str, status: int = HTTPStatus.OK, content_type: str = "text/plain; version=0.0.4") -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = self._parsed_path()
        if parsed.path == "/healthz":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/readyz":
            self._send_json({"status": "ready", "corpus_chunks": len(CHUNKS)})
            return

        if parsed.path == "/metrics":
            self._send_text(METRICS.render())
            return

        if parsed.path == "/":
            self._send_json(
                {
                    "service": "ai-docqa",
                    "default_mode": DEFAULT_MODE,
                    "supported_modes": ["extractive", "generative"],
                    "corpus_chunks": len(CHUNKS),
                    "routes": ["/ask", "/healthz", "/readyz", "/metrics"],
                }
            )
            return

        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = self._parsed_path()
        if parsed.path != "/ask":
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return

        started = time.perf_counter()
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            payload = json.loads(body or b"{}")
            question = payload.get("question", "")
            query_mode = parse_qs(parsed.query).get("mode", [None])[0]
            mode = payload.get("mode") or query_mode or DEFAULT_MODE
            response = answer_question(question, CHUNKS, top_k=int(payload.get("top_k", TOP_K)), mode=mode)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            response["latency_ms"] = latency_ms

            json.dumps(response)
            METRICS.observe(
                status="success" if response["grounded"] else "insufficient_context",
                result=response["result"],
                structured_valid=True,
                hits=len(response["citations"]),
                duration_seconds=latency_ms / 1000.0,
                mode=response["mode"],
                token_usage=response.get("token_usage"),
            )

            logging.info(
                json.dumps(
                    {
                        "event": "ai_docqa_request",
                        "question": question,
                        "mode": response["mode"],
                        "result": response["result"],
                        "grounded": response["grounded"],
                        "latency_ms": latency_ms,
                        "documents": [citation["document"] for citation in response["citations"]],
                    }
                )
            )
            self._send_json(response)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            METRICS.observe(
                status="error",
                result="error",
                structured_valid=False,
                hits=0,
                duration_seconds=latency_ms / 1000.0,
                mode="unknown",
            )
            logging.info(
                json.dumps(
                    {
                        "event": "ai_docqa_error",
                        "latency_ms": latency_ms,
                        "error": str(exc),
                    }
                )
            )
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    logging.info(json.dumps({"event": "startup", "port": PORT, "corpus_chunks": len(CHUNKS)}))
    server.serve_forever()


if __name__ == "__main__":
    main()
