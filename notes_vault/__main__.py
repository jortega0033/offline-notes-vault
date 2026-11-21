"""Entry point: python -m notes_vault --data-dir PATH --port PORT"""

import sqlite3
import sys

from .server import create_server
from .storage import StorageError


def main(argv=None):
    from .config import parse_args  # argparse exits with code 2 on bad input

    data_dir, port = parse_args(argv)
    try:
        server = create_server(data_dir, port)
    except (StorageError, sqlite3.Error, OSError) as exc:
        print(f"error: cannot start: {exc}", file=sys.stderr)
        return 2
    try:
        print(f"Offline Notes Vault listening on http://127.0.0.1:{server.server_address[1]}/", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
