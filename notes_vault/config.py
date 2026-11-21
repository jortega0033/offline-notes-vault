"""Command-line parsing and data-directory validation."""

import argparse
import os
import tempfile
from pathlib import Path

DEFAULT_PORT = 8765


class ConfigError(Exception):
    pass


def _port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer 0..65535") from None
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be in 0..65535")
    return port


def build_parser():
    p = argparse.ArgumentParser(prog="notes_vault", description="Offline Notes Vault (127.0.0.1 only)")
    p.add_argument("--data-dir", required=True, help="directory holding notes.sqlite3 (created if missing)")
    p.add_argument("--port", type=_port, default=DEFAULT_PORT, help="TCP port, 0 picks a free one")
    return p


def validate_data_dir(raw):
    """Return the resolved data directory, creating it if needed."""
    if not isinstance(raw, (str, os.PathLike)) or not str(raw).strip():
        raise ConfigError("data directory must not be empty")
    if "\x00" in str(raw):
        raise ConfigError("data directory contains a NUL character")
    path = Path(raw)
    try:
        if path.exists() and not path.is_dir():
            raise ConfigError(f"data directory is not a directory: {path}")
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
    except ConfigError:
        raise
    except OSError as exc:
        raise ConfigError(f"data directory is not usable: {path} ({exc.strerror or exc})") from None
    return path.resolve()


def parse_args(argv=None):
    """Return (data_dir, port). Exits with code 2 on invalid input."""
    parser = build_parser()
    ns = parser.parse_args(argv)
    try:
        data_dir = validate_data_dir(ns.data_dir)
    except ConfigError as exc:
        parser.error(str(exc))
    return data_dir, ns.port
