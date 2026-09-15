#!/usr/bin/env python3
"""Compatibility entry point for the production football pipeline."""

from main import daemon, preview, run
import sys


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        daemon()
    elif "--preview" in sys.argv:
        preview()
    else:
        run(dry_run="--dry-run" in sys.argv)
