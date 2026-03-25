from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.parse
import zipfile
from datetime import datetime
from typing import Any
from urllib import request


def read_env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def parse_timeout(raw_value: str) -> float:
    default = 20.0
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 5.0), 60.0)


def parse_timestamp(raw_value: str | None) -> float:
    if not raw_value:
        return 0.0
    normalized = raw_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def format_labels(labels: dict[str, str] | None) -> str:
    if not labels:
        return ""
    items = [f'{key}="{escape_label(value)}"' for key, value in sorted(labels.items())]
    return "{" + ",".join(items) + "}"


class MetricBuilder:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.seen: set[str] = set()

    def gauge(self, name: str, value: float | int, help_text: str, labels: dict[str, str] | None = None) -> None:
        if name not in self.seen:
            self.lines.append(f"# HELP {name} {help_text}")
            self.lines.append(f"# TYPE {name} gauge")
            self.seen.add(name)
        self.lines.append(f"{name}{format_labels(labels)} {value}")

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"


class GitHubClient:
    def __init__(self, api_url: str, token: str, timeout_seconds: float) -> None:
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def get_bytes(self, url: str, accept: str = "application/vnd.github+json") -> bytes:
        headers = {
            "Accept": accept,
            "User-Agent": "ai-ci-eval-metrics-poller",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = request.Request(url=url, headers=headers, method="GET")
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            return response.read()

    def get_json(self, url: str) -> dict[str, Any]:
        return json.loads(self.get_bytes(url).decode("utf-8"))


def fetch_latest_completed_run(
    client: GitHubClient,
    owner: str,
    repo: str,
    workflow_ref: str,
    branch: str,
) -> dict[str, Any]:
    workflow_escaped = urllib.parse.quote(workflow_ref, safe="")
    params = {
        "status": "completed",
        "per_page": "1",
    }
    if branch:
        params["branch"] = branch
    query = urllib.parse.urlencode(params)
    url = f"{client.api_url}/repos/{owner}/{repo}/actions/workflows/{workflow_escaped}/runs?{query}"
    payload = client.get_json(url)
    runs = payload.get("workflow_runs", [])
    if not runs:
        raise RuntimeError("no completed workflow runs found")
    return runs[0]


def fetch_eval_summary(
    client: GitHubClient,
    owner: str,
    repo: str,
    run_id: int,
    artifact_name: str,
) -> tuple[dict[str, Any] | None, bool]:
    url = f"{client.api_url}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    payload = client.get_json(url)
    artifacts = payload.get("artifacts", [])
    artifact = None
    for candidate in artifacts:
        if candidate.get("name") == artifact_name and not candidate.get("expired", False):
            artifact = candidate
            break

    if artifact is None:
        return None, False

    archive_url = str(artifact.get("archive_download_url", "")).strip()
    if not archive_url:
        return None, False

    archive_bytes = client.get_bytes(archive_url, accept="application/octet-stream")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = [name for name in archive.namelist() if name.endswith(".json")]
        if not members:
            return None, False
        summary_payload = json.loads(archive.read(sorted(members)[0]).decode("utf-8"))

    if not isinstance(summary_payload, dict):
        return None, False
    return summary_payload, True


def build_failure_payload(now: float) -> str:
    metrics = MetricBuilder()
    metrics.gauge("ai_ci_eval_last_poll_timestamp_seconds", now, "Unix timestamp of the most recent CI eval poll attempt.")
    metrics.gauge("ai_ci_eval_last_poll_success", 0, "Whether the most recent CI eval poll attempt succeeded (1) or failed (0).")
    metrics.gauge("ai_ci_eval_last_poll_failure", 1, "Whether the most recent CI eval poll attempt failed (1) or succeeded (0).")
    return metrics.render()


def build_success_payload(now: float, latest_run: dict[str, Any], summary: dict[str, Any] | None, artifact_available: bool) -> str:
    metrics = MetricBuilder()
    run_id = as_int(latest_run.get("id"))
    run_number = as_int(latest_run.get("run_number"))
    run_attempt = as_int(latest_run.get("run_attempt"))
    run_conclusion = str(latest_run.get("conclusion") or "unknown").strip().lower() or "unknown"
    run_timestamp = parse_timestamp(latest_run.get("updated_at") or latest_run.get("created_at"))
    run_age_seconds = max(0.0, now - run_timestamp) if run_timestamp > 0 else 0.0

    metrics.gauge("ai_ci_eval_last_poll_timestamp_seconds", now, "Unix timestamp of the most recent CI eval poll attempt.")
    metrics.gauge("ai_ci_eval_last_poll_success", 1, "Whether the most recent CI eval poll attempt succeeded (1) or failed (0).")
    metrics.gauge("ai_ci_eval_last_poll_failure", 0, "Whether the most recent CI eval poll attempt failed (1) or succeeded (0).")
    metrics.gauge("ai_ci_eval_latest_run_id", run_id, "Latest completed CI workflow run id.")
    metrics.gauge("ai_ci_eval_latest_run_number", run_number, "Latest completed CI workflow run number.")
    metrics.gauge("ai_ci_eval_latest_run_attempt", run_attempt, "Latest completed CI workflow run attempt number.")
    metrics.gauge("ai_ci_eval_latest_run_timestamp_seconds", run_timestamp, "Unix timestamp of the latest completed CI workflow run update time.")
    metrics.gauge("ai_ci_eval_latest_run_age_seconds", run_age_seconds, "Age in seconds of the latest completed CI workflow run.")
    metrics.gauge("ai_ci_eval_latest_run_success", 1 if run_conclusion == "success" else 0, "Whether the latest completed CI workflow run concluded with success.")
    metrics.gauge("ai_ci_eval_latest_run_failure", 1 if run_conclusion == "failure" else 0, "Whether the latest completed CI workflow run concluded with failure.")
    metrics.gauge(
        "ai_ci_eval_latest_run_conclusion",
        1,
        "One-hot metric carrying the latest completed CI workflow run conclusion label.",
        labels={"conclusion": run_conclusion},
    )
    metrics.gauge(
        "ai_ci_eval_latest_artifact_available",
        1 if artifact_available else 0,
        "Whether the latest completed CI workflow run produced an eval summary artifact.",
    )
    metrics.gauge(
        "ai_ci_eval_summary_available",
        1 if summary is not None else 0,
        "Whether deterministic eval summary data is available for the latest completed CI workflow run.",
    )

    if summary is not None:
        total = as_int(summary.get("total"))
        passed = as_int(summary.get("passed"))
        failed = as_int(summary.get("failed"))
        pass_rate = (passed / total) if total > 0 else 0.0

        metrics.gauge("ai_ci_eval_total_cases", total, "Total deterministic eval cases in the latest CI eval summary.")
        metrics.gauge("ai_ci_eval_passed_cases", passed, "Passed deterministic eval cases in the latest CI eval summary.")
        metrics.gauge("ai_ci_eval_failed_cases", failed, "Failed deterministic eval cases in the latest CI eval summary.")
        metrics.gauge("ai_ci_eval_pass_rate", pass_rate, "Deterministic eval pass rate from the latest CI eval summary.")

        by_category = summary.get("by_category", {})
        if isinstance(by_category, dict):
            for category, category_summary in sorted(by_category.items()):
                if not isinstance(category_summary, dict):
                    continue
                category_total = as_int(category_summary.get("total"))
                category_passed = as_int(category_summary.get("passed"))
                category_failed = as_int(category_summary.get("failed"))
                category_pass_rate = (category_passed / category_total) if category_total > 0 else 0.0
                labels = {"category": str(category)}

                metrics.gauge(
                    "ai_ci_eval_category_total",
                    category_total,
                    "Total deterministic eval cases for a category in the latest CI eval summary.",
                    labels=labels,
                )
                metrics.gauge(
                    "ai_ci_eval_category_passed",
                    category_passed,
                    "Passed deterministic eval cases for a category in the latest CI eval summary.",
                    labels=labels,
                )
                metrics.gauge(
                    "ai_ci_eval_category_failed",
                    category_failed,
                    "Failed deterministic eval cases for a category in the latest CI eval summary.",
                    labels=labels,
                )
                metrics.gauge(
                    "ai_ci_eval_category_pass_rate",
                    category_pass_rate,
                    "Deterministic eval pass rate for a category in the latest CI eval summary.",
                    labels=labels,
                )

    return metrics.render()


def push_metrics(pushgateway_url: str, pushgateway_job_name: str, payload: str, timeout_seconds: float) -> None:
    job_escaped = urllib.parse.quote(pushgateway_job_name, safe="")
    target_url = f"{pushgateway_url.rstrip('/')}/metrics/job/{job_escaped}"
    req = request.Request(
        url=target_url,
        data=payload.encode("utf-8"),
        method="PUT",
        headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
    )
    with request.urlopen(req, timeout=timeout_seconds):
        return


def main() -> int:
    owner = read_env("GITHUB_OWNER", "edwardmccormick")
    repo = read_env("GITHUB_REPO", "argocd-example-apps")
    workflow_ref = read_env("GITHUB_WORKFLOW_FILE", "validate-manifests.yaml")
    branch = read_env("GITHUB_BRANCH", "main")
    artifact_name = read_env("EVAL_ARTIFACT_NAME", "ai-eval-summary")
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    github_api_url = read_env("GITHUB_API_URL", "https://api.github.com")
    pushgateway_url = read_env("PUSHGATEWAY_URL", "http://pushgateway.observability.svc.cluster.local:9091")
    pushgateway_job_name = read_env("PUSHGATEWAY_JOB_NAME", "ai-ci-eval")
    timeout_seconds = parse_timeout(read_env("REQUEST_TIMEOUT_SECONDS", "20"))

    client = GitHubClient(api_url=github_api_url, token=github_token, timeout_seconds=timeout_seconds)
    now = time.time()

    try:
        latest_run = fetch_latest_completed_run(
            client=client,
            owner=owner,
            repo=repo,
            workflow_ref=workflow_ref,
            branch=branch,
        )
        summary, artifact_available = fetch_eval_summary(
            client=client,
            owner=owner,
            repo=repo,
            run_id=as_int(latest_run.get("id")),
            artifact_name=artifact_name,
        )
        payload = build_success_payload(now=now, latest_run=latest_run, summary=summary, artifact_available=artifact_available)
    except Exception as exc:  # noqa: BLE001
        payload = build_failure_payload(now=now)
        try:
            push_metrics(
                pushgateway_url=pushgateway_url,
                pushgateway_job_name=pushgateway_job_name,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
        except Exception as push_exc:  # noqa: BLE001
            print(f"failed to push poll failure metrics: {push_exc}", file=sys.stderr)
        print(f"failed to collect CI eval metrics: {exc}", file=sys.stderr)
        return 1

    push_metrics(
        pushgateway_url=pushgateway_url,
        pushgateway_job_name=pushgateway_job_name,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
