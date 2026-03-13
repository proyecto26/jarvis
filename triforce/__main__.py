"""Entry point for `python -m triforce` execution."""

import os
import subprocess
import sys


def main():
    """Run Jarvis via ADK CLI."""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(["adk", "run", "triforce"], cwd=parent_dir)


if __name__ == "__main__":
    main()
