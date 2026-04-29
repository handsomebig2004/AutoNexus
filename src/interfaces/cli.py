"""Command-line input interface.

What this file does:
    Reads a user request from --text, --file, or stdin/PowerShell pipeline and
    converts it into a UserRequest object.

How it works:
    Input priority is --text first, --file second, stdin third. The module only
    normalizes input and prints JSON; requirement_agent can later consume the
    same UserRequest schema without knowing where the text came from.

How to call it:
    python -m src.interfaces.cli --text "预测客户是否流失"
    python -m src.interfaces.cli --file request.txt
    Get-Content request.txt | python -m src.interfaces.cli
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from src.schemas.user_request import UserRequest
from src.utils.io import read_text, write_json


def read_user_request_from_cli(argv: Sequence[str] | None = None) -> UserRequest:
    """Read CLI arguments/stdin and return a normalized UserRequest."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return read_user_request_from_args(args, parser)


def read_user_request_from_args(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> UserRequest:
    """Convert parsed CLI args/stdin into a normalized UserRequest."""

    has_text = bool(args.text and args.text.strip())
    has_file = bool(args.file)

    if has_text and has_file:
        parser.error("Use only one input source: --text or --file.")

    if has_text:
        return UserRequest(
            request_text=args.text,
            source="cli",
            metadata={"interface": "cli"},
        )

    if has_file:
        source_path = Path(args.file)
        return UserRequest(
            request_text=_strip_bom(read_text(source_path, encoding=args.encoding)),
            source="file",
            source_path=str(source_path),
            metadata={"interface": "cli", "encoding": args.encoding},
        )

    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read()
        return UserRequest(
            request_text=_strip_bom(stdin_text),
            source="stdin",
            metadata={"interface": "cli"},
        )

    parser.error("No input provided. Use --text, --file, or pipe text through stdin.")
    raise AssertionError("argparse parser.error should exit before this line.")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Read a user request and output a normalized UserRequest JSON.",
    )
    parser.add_argument(
        "--text",
        help="User request text.",
    )
    parser.add_argument(
        "--file",
        help="Path to a text/markdown file containing the user request.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Encoding used when reading --file. Default: utf-8-sig.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the normalized UserRequest JSON.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    _configure_standard_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    request = read_user_request_from_args(args, parser)
    data = request.to_json_dict()

    if args.output:
        write_json(args.output, data)

    print(request.model_dump_json(indent=2))
    return 0


def _configure_standard_streams() -> None:
    for stream in [sys.stdin, sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")


if __name__ == "__main__":
    raise SystemExit(main())
