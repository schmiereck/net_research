"""Curriculum runs; see netresearch/curriculum.py.  python scripts/curriculum.py --plans ... --models ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netresearch.curriculum import main  # noqa: E402

if __name__ == "__main__":
    sys.argv.insert(1, "run")
    main()
