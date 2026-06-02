"""Poetry 脚本入口：`poetry run yingshi-ai`。"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> None:
    import uvicorn

    from main import app

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
