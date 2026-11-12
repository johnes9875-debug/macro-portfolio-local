from __future__ import annotations

import argparse
from .scheduler import run_if_due


def main():
    p = argparse.ArgumentParser(prog="macro-portfolio")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="Run latest closed NYSE session")
    run.add_argument("--force", action="store_true")
    run.add_argument("--with-section-l", action="store_true")
    args = p.parse_args()
    if args.cmd == "run":
        run_if_due(force=args.force, include_diagnostic_l=args.with_section_l)


if __name__ == "__main__":
    main()
