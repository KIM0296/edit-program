"""``python -m aie_web [port]`` (with ``apps/web`` on ``sys.path``): loopback only."""

import sys

import uvicorn


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    uvicorn.run("aie_web.app:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
