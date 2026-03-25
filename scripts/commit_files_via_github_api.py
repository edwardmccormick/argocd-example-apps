from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def api_request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-image-pinner",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def create_commit(repo: str, branch: str, message: str, files: list[str], token: str, max_attempts: int = 3) -> str:
    api_root = f"https://api.github.com/repos/{repo}"

    for attempt in range(1, max_attempts + 1):
        ref = api_request("GET", f"{api_root}/git/ref/heads/{branch}", token)
        head_sha = ref["object"]["sha"]

        commit = api_request("GET", f"{api_root}/git/commits/{head_sha}", token)
        base_tree_sha = commit["tree"]["sha"]

        tree_entries = []
        for file_path in files:
            path = Path(file_path)
            tree_entries.append(
                {
                    "path": file_path,
                    "mode": "100644",
                    "type": "blob",
                    "content": path.read_text(encoding="utf-8"),
                }
            )

        tree = api_request(
            "POST",
            f"{api_root}/git/trees",
            token,
            {"base_tree": base_tree_sha, "tree": tree_entries},
        )

        new_commit = api_request(
            "POST",
            f"{api_root}/git/commits",
            token,
            {
                "message": message,
                "tree": tree["sha"],
                "parents": [head_sha],
            },
        )

        try:
            api_request(
                "PATCH",
                f"{api_root}/git/refs/heads/{branch}",
                token,
                {"sha": new_commit["sha"], "force": False},
            )
            return new_commit["sha"]
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 422 and attempt < max_attempts:
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"Failed to update branch ref: HTTP {exc.code} {body}") from exc

    raise RuntimeError("Failed to update branch ref after retries")


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit local files to GitHub using the Git database API.")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--message", required=True)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN environment variable is required")

    for file_path in args.files:
        path = Path(file_path)
        if not path.is_file():
            raise RuntimeError(f"File not found: {file_path}")

    commit_sha = create_commit(args.repo, args.branch, args.message, args.files, token)
    print(json.dumps({"commit_sha": commit_sha, "files": args.files}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
