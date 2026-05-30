#!/usr/bin/env python3
"""Query the local Azure icon index.

Usage:
  icon_index.py search <keyword>     # list canonical names matching keyword
  icon_index.py resolve <name>       # print the SVG path for a name (canonical or synonym)
  icon_index.py list                 # list every canonical name

Importable: `from icon_index import resolve, search, IconIndex`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_INDEX_PATH = Path.home() / ".cache" / "azure-icons" / "index.json"


@dataclass
class IconHit:
    canonical: str
    display: str
    path: str


class IconIndex:
    def __init__(self, path: Path = DEFAULT_INDEX_PATH):
        self.path = path
        if not path.exists():
            raise FileNotFoundError(
                f"icon index not found at {path}. Run bootstrap_icons.py first."
            )
        data = json.loads(path.read_text())
        self.icons: dict[str, dict] = data["icons"]
        self.synonyms: dict[str, str] = data.get("synonyms", {})

    def resolve(self, name: str) -> IconHit | None:
        n = name.strip().lower().replace("_", "-")
        canonical = self.synonyms.get(n, n if n in self.icons else None)
        if canonical is None:
            # Fuzzy: try trimming trailing 's', adding 'azure-' prefix.
            for candidate in (n.rstrip("s"), f"azure-{n}", n + "s"):
                if candidate in self.icons:
                    canonical = candidate
                    break
                if candidate in self.synonyms:
                    canonical = self.synonyms[candidate]
                    break
        if canonical is None or canonical not in self.icons:
            return None
        entry = self.icons[canonical]
        return IconHit(canonical=canonical, display=entry["display"], path=entry["path"])

    def search(self, keyword: str, limit: int = 25) -> list[IconHit]:
        kw = keyword.strip().lower()
        hits: list[IconHit] = []
        for canonical, entry in self.icons.items():
            haystack = canonical + " " + entry["display"].lower()
            if kw in haystack:
                hits.append(IconHit(canonical=canonical, display=entry["display"], path=entry["path"]))
        hits.sort(key=lambda h: (len(h.canonical), h.canonical))
        return hits[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("search")
    sp.add_argument("keyword")
    sp.add_argument("--limit", type=int, default=25)
    sr = sub.add_parser("resolve")
    sr.add_argument("name")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    idx = IconIndex()
    if args.cmd == "search":
        hits = idx.search(args.keyword, limit=args.limit)
        if not hits:
            print(f"no match for {args.keyword!r}", file=sys.stderr)
            return 1
        for h in hits:
            print(f"{h.canonical:45s}  {h.display}")
        return 0
    if args.cmd == "resolve":
        hit = idx.resolve(args.name)
        if not hit:
            print(f"unknown: {args.name}", file=sys.stderr)
            return 1
        print(hit.path)
        return 0
    if args.cmd == "list":
        for canonical, entry in sorted(idx.icons.items()):
            print(f"{canonical:45s}  {entry['display']}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
