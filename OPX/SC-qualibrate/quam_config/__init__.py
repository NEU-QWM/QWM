

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUAM_STATE_PATH = PROJECT_ROOT / "quam_state"

os.environ.setdefault("QUAM_STATE_PATH", str(QUAM_STATE_PATH))

from .my_quam import Quam

__all__ = ["Quam"]
