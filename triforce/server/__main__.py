"""Run the DANTE UI bridge: ``python -m triforce.server``.

Equivalent to: uvicorn triforce.server.app:app --host 127.0.0.1 --port 8420
Loopback only — never bind 0.0.0.0.
"""

import sys


def main() -> None:
    try:
        import uvicorn
    except ImportError:
        from triforce.server.app import INSTALL_HINT

        sys.exit(INSTALL_HINT)

    uvicorn.run("triforce.server.app:app", host="127.0.0.1", port=8420)


if __name__ == "__main__":
    main()
