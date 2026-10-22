"""The Home row: the most recently launched games and apps."""

import time

from .util import data_dir, load_json, save_json

HOME_LIMIT = 15
_KEEP = 50


def _path():
    return data_dir() / "recents.json"


def load():
    return load_json(_path(), [])


def touch(item):
    """Move an item to the front of the recents list."""
    entries = [e for e in load() if e.get("id") != item["id"]]
    entries.insert(0, {
        "id": item["id"],
        "title": item.get("title"),
        "source": item.get("source"),
        "kind": item.get("kind"),
        "art": item.get("art", {}),
        "last_played": time.time(),
    })
    save_json(_path(), entries[:_KEEP])


def forget(item_id):
    save_json(_path(), [e for e in load() if e.get("id") != item_id])


def home_items(library_items):
    """Up to 15 items for Home, most recent first.

    Recents come from our own log. Items played before Lumen knew about them
    (e.g. through Steam directly) are merged in by their last_played time, so a
    fresh install still shows a full row.
    """
    by_id = {i["id"]: i for i in library_items}
    seen, out = set(), []
    for entry in load():
        item = by_id.get(entry["id"])
        if item is None or not item.get("installed", True):
            continue
        out.append({**item, "last_played": max(entry.get("last_played") or 0, item.get("last_played") or 0)})
        seen.add(item["id"])
    extra = [i for i in library_items if i["id"] not in seen and i.get("installed") and i.get("last_played")]
    out.extend(extra)
    out.sort(key=lambda i: i.get("last_played") or 0, reverse=True)
    return out[:HOME_LIMIT]
