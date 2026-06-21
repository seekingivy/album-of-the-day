#!/usr/bin/env python3
"""
build_catalog.py — merge albums.csv into catalog.json

Reads a CSV of artist,album,year and merges new entries into catalog.json.
Skips entries that already exist (matched by artist+album, case-insensitive).
Stubs null fields for future enrichment (Phase 2/3). Safe to re-run.

Usage:
    python build_catalog.py --input albums.csv
    python build_catalog.py --input albums.csv --dry-run
"""
import argparse
import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path

REQUIRED_COLUMNS = {"artist", "album"}
EMPTY_ENTRY_FIELDS = {
    "plex_id": None,
    "art_url": None,
    "tracklist": None,
    "mb_id": None,
    "last_prompted": None,
}


def load_catalog(path: Path) -> list:
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: {path} is not valid JSON ({e}). Refusing to overwrite it.", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, list):
        print(f"ERROR: {path} does not contain a JSON array at the top level.", file=sys.stderr)
        sys.exit(1)
    return data


def read_albums_csv(path: Path) -> list:
    if not path.exists():
        print(f"ERROR: input file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print(f"ERROR: {path} appears to be empty.", file=sys.stderr)
                sys.exit(1)

            header = {h.strip().lower() for h in reader.fieldnames}
            missing = REQUIRED_COLUMNS - header
            if missing:
                print(
                    f"ERROR: {path} is missing required column(s): {', '.join(sorted(missing))}. "
                    f"Found columns: {', '.join(reader.fieldnames)}",
                    file=sys.stderr,
                )
                sys.exit(1)

            rows = []
            for i, row in enumerate(reader, start=2):  # row 1 is the header
                norm = {k.strip().lower(): (v.strip() if v else v) for k, v in row.items() if k}
                artist = norm.get("artist", "")
                album = norm.get("album", "")
                if not artist or not album:
                    print(f"WARNING: skipping row {i} — missing artist or album.", file=sys.stderr)
                    continue

                year_raw = norm.get("year")
                year = None
                if year_raw:
                    try:
                        year = int(year_raw)
                    except ValueError:
                        print(f"WARNING: row {i} has a non-numeric year ({year_raw!r}) — storing as null.", file=sys.stderr)

                rows.append({"artist": artist, "album": album, "year": year})
            return rows
    except UnicodeDecodeError as e:
        print(
            f"ERROR: {path} is not valid UTF-8 ({e}). Re-save the file with UTF-8 encoding "
            f"(this matters for accented names like Sigur Rós or Björk).",
            file=sys.stderr,
        )
        sys.exit(1)


def make_key(artist: str, album: str) -> str:
    return f"{artist.strip().lower()}|{album.strip().lower()}"


def main():
    parser = argparse.ArgumentParser(description="Merge albums.csv into catalog.json")
    parser.add_argument("--input", default="albums.csv", help="Path to source CSV (default: albums.csv)")
    parser.add_argument("--catalog", default="catalog.json", help="Path to catalog JSON (default: catalog.json)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be added without writing")
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    input_path = Path(args.input)

    catalog = load_catalog(catalog_path)
    existing_keys = {make_key(e["artist"], e["album"]) for e in catalog if "artist" in e and "album" in e}

    new_rows = read_albums_csv(input_path)

    to_add = []
    skipped = 0
    for row in new_rows:
        key = make_key(row["artist"], row["album"])
        if key in existing_keys:
            skipped += 1
            continue
        entry = {
            "artist": row["artist"],
            "album": row["album"],
            "year": row["year"],
            **EMPTY_ENTRY_FIELDS,
            "added": date.today().isoformat(),
        }
        to_add.append(entry)
        existing_keys.add(key)

    print(f"Parsed {len(new_rows)} row(s) from {input_path}")
    print(f"  {len(to_add)} new album(s) to add")
    print(f"  {skipped} already in catalog (skipped)")

    if args.dry_run:
        for e in to_add:
            year_str = f" ({e['year']})" if e["year"] else ""
            print(f"  + {e['artist']} — {e['album']}{year_str}")
        print("\nDry run — nothing written.")
        return

    if not to_add:
        print("Nothing to write.")
        return

    catalog.extend(to_add)
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {len(catalog)} total album(s) to {catalog_path}")


if __name__ == "__main__":
    main()
