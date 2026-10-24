"""Entry point for the background task and the login worker.

Run as a script with `python -I -S path/to/fortiauto/launch.py <command>`:
- no `-m`, so Python skips loading runpy (about 1 MB);
- `-I -S` keeps site-packages, PYTHON* variables and the current folder off
  sys.path, so nothing installed on the machine can interfere.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fortiauto.cli import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
