import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    """
    Load a JSON test fixture from the fixtures directory.

    Args:
        name (str): File name of the fixture to load.

    Returns:
        dict: Parsed JSON object from the fixture file.
    """
    with open(FIXTURE_DIR / name, encoding="utf-8") as f:
        return json.load(f)
