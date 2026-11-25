"""Command line interface for the JD Analyser platform."""

import argparse
import asyncio
from pathlib import Path

from app.db.session import async_session_maker
from app.services.feedback import export_dpo


async def run_export_dpo(output_path: str = "data/dpo-preference-pairs.jsonl") -> int:
    """Run DPO export against the configured database."""
    async with async_session_maker() as session:
        jsonl = await export_dpo(session, output_path=output_path)
        count = len(jsonl.strip().split("\n")) if jsonl.strip() else 0
        out_path = Path(output_path).resolve()
        print(f"Exported {count} preference pairs to {out_path}")
        return count


def main() -> None:
    parser = argparse.ArgumentParser(description="JD Analyser CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-dpo", help="Export DPO preference pairs to JSONL")
    export_parser.add_argument(
        "--output",
        "-o",
        default="data/dpo-preference-pairs.jsonl",
        help="Target output path for JSONL file (default: data/dpo-preference-pairs.jsonl)",
    )

    args = parser.parse_args()
    if args.command == "export-dpo":
        asyncio.run(run_export_dpo(output_path=args.output))


if __name__ == "__main__":
    main()
