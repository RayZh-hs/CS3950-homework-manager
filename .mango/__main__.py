#!/usr/bin/env python3

from __future__ import annotations

import argparse

from _homework_manager import fetch_homework, list_homeworks, submit_homework


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mango homework",
        description="Canvas homework manager commands.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list",
        help="List available homeworks online.",
    )
    list_parser.set_defaults(handler=lambda args: list_homeworks())

    fetch_parser = subparsers.add_parser(
        "fetch",
        help="Fetch one homework from Canvas.",
    )
    fetch_parser.add_argument("query", help="Assignment id or name keyword")
    fetch_parser.set_defaults(handler=lambda args: fetch_homework(args.query))

    submit_parser = subparsers.add_parser(
        "submit",
        help="Build and submit one homework.",
    )
    submit_parser.add_argument("query", help="Assignment id or name keyword")
    submit_parser.set_defaults(handler=lambda args: submit_homework(args.query))

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
