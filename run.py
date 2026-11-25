"""One command: python run.py [--offline] [--host 0.0.0.0] [--port 8000]."""

import sys

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 or newer is needed.")

from bothsides.main import run

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
