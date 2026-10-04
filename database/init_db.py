"""Create all tables.  Run from the project root:

    python -m database.init_db           # create tables
    python -m database.init_db --reset   # drop everything and recreate
"""
import sys

from .models import Base
from .session import engine, DATABASE_URL


def init_db(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
        print("Dropped all tables.")
    Base.metadata.create_all(engine)
    print(f"Database ready at {DATABASE_URL}")


if __name__ == "__main__":
    init_db(reset="--reset" in sys.argv)
