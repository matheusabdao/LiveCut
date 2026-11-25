"""Unified entry point for LiveCut.

``LiveCut.exe`` with no arguments opens the GUI. With arguments it behaves like
the CLI. ``--provision`` is used by the installer to download the components.
"""

from __future__ import annotations

import sys
from typing import List, Optional


def cli_main(argv: Optional[List[str]] = None) -> int:
    from . import crash, logging_setup

    logging_setup.setup_logging()
    crash.install_handlers(show_dialog=False)

    import run_cli

    return run_cli.main(argv)


def gui_main(argv: Optional[List[str]] = None) -> int:
    from . import crash, logging_setup

    logging_setup.setup_logging(console=False)
    crash.install_handlers(show_dialog=True)

    import run_gui

    return run_gui.main()


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] == "--provision":
        from .provisioning import provision_main

        return provision_main(args)

    if args and args[0] in ("--version", "-V"):
        from . import __version__

        print(__version__)
        return 0

    if args:
        return cli_main(args)

    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
