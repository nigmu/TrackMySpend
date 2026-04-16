from pathlib import Path
DB_PATH = Path("DB/data/trackmyspend.db")

# Parser sender keyword filters used for second staging step.
# Updated at runtime via parsing API endpoints.
PARSER_FROM_HEADER_KEYWORDS = [
    "bank.in",
    "hdfc",
]