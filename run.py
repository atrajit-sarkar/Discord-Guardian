import os
import sys

BASE_DIR = os.path.dirname(__file__)
SRC = os.path.join(BASE_DIR, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from guardian.main import main

if __name__ == "__main__":
    main()
