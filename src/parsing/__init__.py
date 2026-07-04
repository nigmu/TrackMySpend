"""Pure parsers: text -> structured dict.

This package never touches the database or FastAPI. Import the parser
as `from src.parsing import parse_text`.
"""

from .advanced_hdfc import parse_text, parse_texts

__all__ = ["parse_text", "parse_texts"]
