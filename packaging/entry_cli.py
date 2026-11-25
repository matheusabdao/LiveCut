"""Entry point for the console executable (``LiveCut-cli.exe``)."""

import sys

from livecut.app import cli_main

if __name__ == "__main__":
    sys.exit(cli_main())
