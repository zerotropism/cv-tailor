"""Console entry point: `cv-tailor` starts the Streamlit UI, whatever the working directory."""

import sys
from pathlib import Path

from streamlit.web import cli


def main() -> None:
    app = Path(__file__).with_name("main.py")
    sys.argv = ["streamlit", "run", str(app), *sys.argv[1:]]
    sys.exit(cli.main())
