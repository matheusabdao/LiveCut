"""Entry point for the windowed executable (``LiveCut.exe``).

Dispatches through ``livecut.app.main`` so the installer can call
``LiveCut.exe --provision``. With no arguments it opens the GUI.
"""

import sys

from livecut.app import main

if __name__ == "__main__":
    sys.exit(main())
