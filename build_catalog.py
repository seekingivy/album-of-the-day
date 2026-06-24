#!/usr/bin/env python3
"""
build_catalog.py — merge albums.csv into catalog.json

Reads a CSV and merges new entries into catalog.json.
Skips entries that already exist (matched by artist+album, case-insensitive).
Stubs null fields for future enrichment (Phase 2/3). Safe to re-run.

Accepted column names (case-insensitive):
  Required: artist, album OR title
  Optional: year OR release date, genre, runtime, song (count) / songs / track_count

Usage:
    python build_catalog.py --input albums.csv
    python build_catalog.py --input albums.csv --dry-run
"""
import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

# Columns that map to the canonical "album" field
ALBUM_ALIASES = {"album", "title"}
# Columns that map to the canonical "year" field
YEAR_ALIASES = {"year", "release date", "release_date", "releasedate"}
# Columns that map to track count
TRACK_ALIASES = {"song", "songs", "song (count)", "song(count)", "track_count", "tracks", "track count"}

REQUIRED_COLUMNS = {"artist"}   # album checked via ALBUM_ALIASES below

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


def find_column(norm_headers: dict, aliases: set) -> str | None:
    """Return the first raw header whose normalised form is in aliases, or None."""
    for norm, raw in norm_headers.items():
        if norm in aliases:
            return raw
    return None


def parse_year(raw: str, row_num: int) -> int | None:
    """Extract a 4-digit year from a string; warn and return None on failure."""
    if not raw:
        return None
    # grab first 4-digit sequence — handles "1969", "1969-01-01", etc.
    m = re.search(r"\b(\d{4})\b", raw)
    if m:
        return int(m.group(1))
    print(f"WARNING: row {row_num} has an unrecognisable year ({raw!r}) — storing as null.", file=sys.stderr)
    return None


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

            # Build a map of normalised-header → raw-header
            norm_headers = {h.strip().lower(): h for h in reader.fieldnames if h}

            # Resolve required columns
            missing_artist = "artist" not in norm_headers
            album_col = find_column(norm_headers, ALBUM_ALIASES)
            if missing_artist or album_col is None:
                problems = []
                if missing_artist:
                    problems.append("'artist'")
                if album_col is None:
                    problems.append("'album' or 'title'")
                print(
                    f"ERROR: {path} is missing required column(s): {', '.join(problems)}. "
                    f"Found columns: {', '.join(reader.fieldnames)}",
                    file=sys.stderr,
                )
                sys.exit(1)

            # Resolve optional columns
            year_col    = find_column(norm_headers, YEAR_ALIASES)
            genre_col   = find_column(norm_headers, {"genre"})
            runtime_col = find_column(norm_headers, {"runtime"})
            track_col   = find_column(norm_headers, TRACK_ALIASES)

            print(f"Column mapping:")
            print(f"  artist       → '{norm_headers.get('artist')}'")
            print(f"  album        → '{album_col}'")
            print(f"  year         → '{year_col or '(not found — will be null)'}'")
            print(f"  genre        → '{genre_col or '(not found)'}'")
            print(f"  runtime      → '{runtime_col or '(not found)'}'")
            print(f"  track_count  → '{track_col or '(not found)'}'")
            print()

            rows = []
            for i, row in enumerate(reader, start=2):
                norm = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
                artist = norm.get("artist", "")
                album  = norm.get(album_col.strip().lower(), "") if album_col else ""
                if not artist or not album:
                    print(f"WARNING: skipping row {i} — missing artist or album.", file=sys.stderr)
                    continue

                year_raw = norm.get(year_col.strip().lower(), "") if year_col else ""
                year = parse_year(year_raw, i)

                genre   = norm.get(genre_col.strip().lower(),   "") if genre_col   else None
                runtime = norm.get(runtime_col.strip().lower(), "") if runtime_col else None
                tracks_raw = norm.get(track_col.strip().lower(), "") if track_col else ""
                track_count = None
                if tracks_raw:
                    try:
                        track_count = int(tracks_raw)
                    except ValueError:
                        pass

                rows.append({
                    "artist":      artist,
                    "album":       album,
                    "year":        year,
                    "genre":       genre or None,
                    "runtime":     runtime or None,
                    "track_count": track_count,
                })
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
            "artist":      row["artist"],
            "album":       row["album"],
            "year":        row["year"],
            "genre":       row.get("genre"),
            "runtime":     row.get("runtime"),
            "track_count": row.get("track_count"),
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
