"""Command line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import RuntimeConfig
from .console.server import ConsoleServer
from .runtime import LineControlRuntime


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""

    parser = argparse.ArgumentParser(prog="line-control")
    parser.add_argument("--host", default="127.0.0.1", help="bind address")
    parser.add_argument("--port", type=int, default=8080, help="bind port")
    parser.add_argument("--data-dir", default="data", help="journal and snapshot directory")
    parser.add_argument("--web-dir", default="web", help="directory holding the console pages")
    parser.add_argument("--line", default="line-a", help="line name reported by the console")
    parser.add_argument(
        "--check",
        action="store_true",
        help="boot the runtime, print the restore report and the health payload, then exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the console or run a single boot check."""

    args = build_parser().parse_args(argv)
    config = RuntimeConfig(
        data_dir=Path(args.data_dir),
        host=args.host,
        port=args.port,
        web_dir=Path(args.web_dir),
        line_name=args.line,
    )
    runtime = LineControlRuntime(config)
    try:
        report = runtime.bootstrap()
        if args.check:
            print(
                json.dumps(
                    {"restore": report, "health": runtime.health()},
                    sort_keys=True,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        server = ConsoleServer(runtime)
        server.bind()
        print(f"listening on {server.url}")
        print(f"health check {server.url}/api/health")
        print(f"restart replay {report['replayed_records']} records snapshot={report['used_snapshot_id']}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("stopping")
        finally:
            server.stop()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
