from __future__ import annotations

from importlib.resources import files
from pathlib import Path

DEFAULT_PAPER_APP = "pigeon_origami"

PAPER_APPS = {
    "conversion_charts": "conversion_charts.png",
    "knots": "knots.png",
    "italian_phrasebook": "italian_phrasebook.png",
    "sign_language": "sign_language.png",
    "multiplication_table": "multiplication_table.png",
    "recipe": "recipe.png",
    "pigeon_origami": "pigeon_origami.png",
    "sudoku": "sudoku.png",
    "maze": "maze.png",
    "word_of_the_day": "word_of_the_day.png",
    "anagram": "anagram.png",
    "riddle": "riddle.png",
    "typography": "typography.png",
}

PAPER_APP_NAMES = {
    "conversion_charts": "Conversion Charts",
    "knots": "Knots",
    "italian_phrasebook": "Italian Phrasebook",
    "sign_language": "Sign Language",
    "multiplication_table": "Multiplication Table",
    "recipe": "Recipe",
    "pigeon_origami": "Origami Pigeon",
    "sudoku": "Sudoku",
    "maze": "Maze",
    "word_of_the_day": "Word of the day",
    "anagram": "Anagram",
    "riddle": "Riddle",
    "typography": "Typography",
}


def asset_root() -> Path:
    return Path(str(files("paperphone"))) / "assets"


def paper_app_path(name: str) -> Path:
    return asset_root() / "paper_apps" / PAPER_APPS[name]


def asset_url(path: Path) -> str:
    return path.resolve().as_uri()
