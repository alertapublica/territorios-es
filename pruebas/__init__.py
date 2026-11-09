import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "python", ROOT):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
