"""Command-line interface for the candidate transformer."""

from __future__ import annotations

import argparse
import json
from datetime import date

from candidate_transformer.core.models import InputPaths
from candidate_transformer.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser used by console scripts and tests."""

    parser = argparse.ArgumentParser(description="Transform multi-source candidate data into canonical JSON.")
    parser.add_argument("--recruiter-csv", help="Path to recruiter CSV export")
    parser.add_argument("--ats-json", help="Path to ATS JSON blob")
    parser.add_argument("--notes-txt", help="Path to recruiter notes text")
    parser.add_argument("--resume", help="Path to a resume PDF file")
    parser.add_argument("--github-url", help="GitHub profile URL, for example https://github.com/octocat")
    parser.add_argument("--github-cache", help="Optional cached GitHub API response used if the live API is unavailable")
    parser.add_argument("--config", help="Optional projection config JSON")
    parser.add_argument("--output", help="Optional output JSON path; stdout is used when omitted")
    parser.add_argument("--default-region", default="US", help="Default phone region for local numbers")
    parser.add_argument("--run-date", default=None, help="Deterministic run date for open-ended experience, YYYY-MM-DD")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the transformer CLI and return a process exit code."""

    args = build_parser().parse_args(argv)
    config = _load_json(args.config) if args.config else None
    run_date = date.fromisoformat(args.run_date) if args.run_date else None
    try:
        output = run_pipeline(
            InputPaths(args.recruiter_csv, args.ats_json, args.notes_txt, args.resume, args.github_url, args.github_cache),
            config=config,
            default_region=args.default_region,
            run_date=run_date,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    serialized = json.dumps(output, indent=2, sort_keys=True)
    print(serialized)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(serialized + "\n")
    return 0


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    raise SystemExit(main())
