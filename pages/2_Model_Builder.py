from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository sources are importable when executed via `streamlit run`.
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from model_builder.ui.pages.model_builder_page import run_page


def main() -> None:
    run_page()


if __name__ == "__main__":
    main()
