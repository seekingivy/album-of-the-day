#!/usr/bin/env python3
"""
picker.py — daily album selection (Phase 1: plain-text RSS only)

Runs in the GitHub Action. Reads catalog.json, picks one album (respecting
a cooldown window so the same album doesn't repeat too soon), writes/updates
feed.xml and today.json, and records the pick back into catalog.json.

No external API calls — everything it needs is already in catalog.json.
"""
import json
import random
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

# --- Config (Phase 1: hardcoded; moves to config.yaml in Phase 4) ---
COOLDOWN_DAYS = 60
FEED_ITEMS_TO_KEEP = 30
FEED_TITLE = "Album of the Day"
FEED_LINK = "https://YOUR-USERNAME.github.io/daily-album-prompt/"  # update after repo is created
FEED_DESCRIPTION = "A daily prompt for intentional listening."

CATALOG_PATH = Path("catalog.json")
FEED_PATH = Path("feed.xml")
TODAY_JSON_PATH = Path("today.json")


def load_catalog(path: Path) -> list:
    if not path.exists():
        print(f"ERROR: catalog not found at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("ERROR: catalog.json must contain a JSON array at the top level.", file=sys.stderr)
        sys.exit(1)
    return data


def is_valid_entry(e) -> bool:
    return isinstance(e, dict) and bool(e.get("artist")) and bool(e.get("album"))


def select_album(catalog: list) -> dict:
    valid = []
    for i, e in enumerate(catalog):
        if not is_valid_entry(e):
            print(f"WARNING: skipping malformed catalog entry at index {i}: {e!r}", file=sys.stderr)
            continue
        valid.append(e)

    if not valid:
        print("ERROR: catalog has no valid entries (need at least 'artist' and 'album').", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    cooldown_cutoff = today - timedelta(days=COOLDOWN_DAYS)

    def in_cooldown(e: dict) -> bool:
        lp = e.get("last_prompted")
        if not lp:
            return False
        try:
            return date.fromisoformat(lp) > cooldown_cutoff
        except ValueError:
            return False  # malformed date — treat as not in cooldown rather than crash

    pool = [e for e in valid if not in_cooldown(e)]

    if not pool:
        # Every album has been prompted recently. Never crash — reset the
        # oldest quarter of entries and pick from those instead.
        print("WARNING: all albums in cooldown — resetting oldest entries.", file=sys.stderr)
        valid_sorted = sorted(valid, key=lambda e: e.get("last_prompted") or "")
        reset_count = max(1, len(valid_sorted) // 4)
        for e in valid_sorted[:reset_count]:
            e["last_prompted"] = None
        pool = valid_sorted[:reset_count]

    return random.choice(pool)


def load_existing_items(feed_path: Path) -> list:
    if not feed_path.exists():
        return []
    try:
        tree = ET.parse(feed_path)
    except ET.ParseError as e:
        print(f"WARNING: existing {feed_path} is malformed ({e}) — starting a fresh feed.", file=sys.stderr)
        return []
    channel = tree.getroot().find("channel")
    if channel is None:
        return []
    items = []
    for item_el in channel.findall("item"):
        items.append({
            "title": item_el.findtext("title", default=""),
            "pubDate": item_el.findtext("pubDate", default=""),
            "guid": item_el.findtext("guid", default=""),
            "description": item_el.findtext("description", default=""),
        })
    return items


def write_feed(items: list, feed_path: Path):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = FEED_TITLE
    ET.SubElement(channel, "link").text = FEED_LINK
    ET.SubElement(channel, "description").text = FEED_DESCRIPTION

    for item in items:
        item_el = ET.SubElement(channel, "item")
        ET.SubElement(item_el, "title").text = item["title"]
        ET.SubElement(item_el, "pubDate").text = item["pubDate"]
        ET.SubElement(item_el, "guid").text = item["guid"]
        ET.SubElement(item_el, "description").text = item["description"]

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(feed_path, encoding="utf-8", xml_declaration=True)


def main():
    catalog = load_catalog(CATALOG_PATH)
    selected = select_album(catalog)

    today = date.today()
    pub_date = format_datetime(datetime.now(timezone.utc))
    guid = f"album-prompt-{today.isoformat()}"
    year = selected.get("year")

    title = f"Album of the Day — {selected['album']} · {selected['artist']}"
    description = f"{selected['album']} — {selected['artist']}" + (f" ({year})" if year else "")

    new_item = {"title": title, "pubDate": pub_date, "guid": guid, "description": description}

    existing_items = load_existing_items(FEED_PATH)
    all_items = ([new_item] + existing_items)[:FEED_ITEMS_TO_KEEP]
    write_feed(all_items, FEED_PATH)

    today_payload = {
        "artist": selected["artist"],
        "album": selected["album"],
        "year": year,
        "tracklist": selected.get("tracklist"),
        "plex_id": selected.get("plex_id"),
        "date": today.isoformat(),
    }
    with open(TODAY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(today_payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    selected["last_prompted"] = today.isoformat()
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Picked: {selected['artist']} — {selected['album']}")


if __name__ == "__main__":
    main()
