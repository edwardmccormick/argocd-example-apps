from __future__ import annotations

import argparse
import json
import sys

from engine import run_eval


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic evals against the local doc QA engine.")
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--eval-file", required=True)
    parser.add_argument("--mode", default="extractive", choices=["extractive", "generative"])
    args = parser.parse_args()

    summary = run_eval(args.corpus_dir, args.eval_file, mode=args.mode)
    print(json.dumps(summary, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
