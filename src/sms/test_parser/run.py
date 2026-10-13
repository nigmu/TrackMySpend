"""Write regex vs Jev tables for the raw HDFC SMS export.

    python -m src.sms.test_parser.run
    python -m src.sms.test_parser.run --regex-only
    python -m src.sms.test_parser.run --limit 5

Regex columns are always filled. Jev columns fill when TYPESAFE_API_KEY is
set (environment or the project .env). Answers are cached under out/, so a
rerun calls Jev only for messages that are not cached yet.

out/ holds the CSVs and the cache. That folder is gitignored.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from src.sms.test_parser.rows import FIELDS, jev_mark, pct, questions_for, regex_row

_HERE = Path(__file__).resolve().parent
_OUT = _HERE / "out"
_CACHE = _OUT / "jev_cache.json"
_RAW = _HERE.parent / "samples" / "raw_sms_data-1791614970963.csv"
_CLASS_CSV = _OUT / "classification.csv"
_EXTRACT_CSV = _OUT / "extraction.csv"

_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_MODEL = "jev-latest"

_CLASS_HEADER = ["serial", "regex_class", "jev_class", "jev_class_pct", "class_match", "sms"]
_EXTRACT_HEADER = [
    "serial",
    *(name for field in FIELDS for name in (f"{field}_regex", f"{field}_jev")),
    "sms",
]


def _bodies(limit: int | None) -> list[str]:
    with _RAW.open(newline="", encoding="utf-8") as handle:
        bodies = [row["body"] for row in csv.DictReader(handle)]
    if limit is not None:
        return bodies[:limit]
    return bodies


def _load_cache() -> dict:
    if not _CACHE.is_file():
        return {}
    return json.loads(_CACHE.read_text(encoding="utf-8"))


def _save_cache(cache: dict) -> None:
    _OUT.mkdir(exist_ok=True)
    _CACHE.write_text(json.dumps(cache), encoding="utf-8")


def _cache_key(state: str, questions: dict) -> str:
    blob = json.dumps(
        {"state": state, "questions": questions, "model": _MODEL},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def _system_one(state: str, questions: dict, api_key: str) -> dict:
    payload = json.dumps(
        {"state": state, "model": _MODEL, "questions": questions},
        ensure_ascii=False,
    ).encode()
    delay = 1.0
    for attempt in range(5):
        request = urllib.request.Request(
            _ENDPOINT,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            if error.code not in (429, 529) or attempt == 4:
                raise SystemExit(f"Jev HTTP {error.code}: {detail}") from error
            time.sleep(delay)
            delay *= 2
    raise SystemExit("Jev request failed")


def _jev_cells(answer: dict) -> tuple[str, str, dict[str, str]]:
    answers = answer["answers"]
    chosen = answers["class"]
    label = chosen["choice"]
    marks = {field: jev_mark(answers[field]["noul"]) for field in FIELDS}
    return label, pct(chosen["probabilities"][label]), marks


def _write(rows: list[dict]) -> None:
    _OUT.mkdir(exist_ok=True)
    with _CLASS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CLASS_HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    extract_rows = []
    for row in rows:
        extract = {"serial": row["serial"], "sms": row["sms"]}
        for field in FIELDS:
            extract[f"{field}_regex"] = row[f"{field}_regex"]
            extract[f"{field}_jev"] = row[f"{field}_jev"]
        extract_rows.append(extract)
    with _EXTRACT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_EXTRACT_HEADER)
        writer.writeheader()
        writer.writerows(extract_rows)


def run(limit: int | None, regex_only: bool) -> None:
    load_dotenv()
    if not _RAW.is_file():
        raise SystemExit(f"Missing SMS export: {_RAW}")
    api_key = "" if regex_only else os.environ.get("TYPESAFE_API_KEY", "").strip()
    bodies = _bodies(limit)
    cache = _load_cache()
    rows: list[dict] = []
    calls = 0
    hits = 0
    for serial, body in enumerate(bodies, start=1):
        label, fields = regex_row(body)
        row = {
            "serial": serial,
            "regex_class": label,
            "jev_class": "",
            "jev_class_pct": "",
            "class_match": "",
            "sms": body,
        }
        for field in FIELDS:
            row[f"{field}_regex"] = fields[field]
            row[f"{field}_jev"] = ""
        if api_key:
            questions = questions_for(fields)
            key = _cache_key(body, questions)
            if key not in cache:
                cache[key] = _system_one(body, questions, api_key)
                _save_cache(cache)
                calls += 1
                print(f"{serial}/{len(bodies)} {label}", flush=True)
            else:
                hits += 1
            jev_class, jev_pct, marks = _jev_cells(cache[key])
            row["jev_class"] = jev_class
            row["jev_class_pct"] = jev_pct
            for field in FIELDS:
                row[f"{field}_jev"] = marks[field]
            row["class_match"] = "TRUE" if row["regex_class"] == row["jev_class"] else "FALSE"
        rows.append(row)
        if api_key:
            _write(rows)
    if not api_key:
        _write(rows)
    if api_key:
        print(f"Jev calls {calls}, cache hits {hits}")
    elif regex_only:
        print("Skipped Jev. Jev columns are blank.")
    else:
        print("TYPESAFE_API_KEY is not set. Jev columns are blank.")
    print(f"Wrote {_CLASS_CSV}")
    print(f"Wrote {_EXTRACT_CSV}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare the regex SMS parser with Jev.")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N messages.")
    parser.add_argument(
        "--regex-only",
        action="store_true",
        help="Skip Jev even when TYPESAFE_API_KEY is set.",
    )
    args = parser.parse_args()
    run(args.limit, args.regex_only)


if __name__ == "__main__":
    main()
