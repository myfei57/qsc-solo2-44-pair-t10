"""The command line entry point and its single boot check."""

from __future__ import annotations

import json
from pathlib import Path

from bgs.__main__ import build_parser, main


def test_parser_defaults_match_the_documented_start_command():
    args = build_parser().parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 8080
    assert args.data_dir == "data"
    assert args.web_dir == "web"
    assert args.check is False


def test_check_mode_prints_the_health_payload(capsys, tmp_path: Path):
    exit_code = main(["--check", "--data-dir", str(tmp_path / "data")])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["health"]["status"] == "ok"
    assert printed["restore"]["used_snapshot_id"] is None


def test_check_mode_reports_a_replay_on_the_second_run(capsys, tmp_path: Path):
    data_dir = str(tmp_path / "data")
    main(["--check", "--data-dir", data_dir])
    capsys.readouterr()

    main(["--check", "--data-dir", data_dir])

    printed = json.loads(capsys.readouterr().out)
    assert printed["restore"]["replayed_records"] >= 1


def test_check_mode_accepts_a_custom_line_name(capsys, tmp_path: Path):
    main(["--check", "--data-dir", str(tmp_path / "data"), "--line", "line-b"])

    assert json.loads(capsys.readouterr().out)["health"]["line"] == "line-b"
