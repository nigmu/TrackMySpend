"""Pure parsers: text -> structured dict.

This package never touches the database or FastAPI. Import the basic
parser as `from src.parsing import parse_text`.
"""

from .basic import parse_text, parse_texts

__all__ = ["parse_text", "parse_texts"]
