import argparse
import os
import sys
from pathlib import Path

from .server import serve


def default_ui():
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "ui", Path("/usr/share/lumen/ui"), Path("/usr/local/share/lumen/ui")):
        if (candidate / "index.html").exists():
            return candidate
    return here.parent / "ui"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lumend", description="Lumen shell daemon")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LUMEN_PORT", 7777)))
    parser.add_argument("--ui", type=Path, default=None, help="directory with the UI files")
    parser.add_argument("--mode", choices=["session", "greeter"], default="session")
    parser.add_argument("--mock", action="store_true", help="serve fake data (UI development)")
    args = parser.parse_args(argv)
    if args.mock:
        os.environ["LUMEN_MOCK"] = "1"
    try:
        serve(args.port, args.ui or default_ui(), args.mode)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
