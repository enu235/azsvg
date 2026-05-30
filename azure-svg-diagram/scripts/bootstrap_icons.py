#!/usr/bin/env python3
"""Bootstrap the local Azure icon cache.

Downloads the official Microsoft Azure architecture icon ZIP to
~/.cache/azure-icons/, extracts it, and builds an index.json mapping
canonical service names to icon file paths.

Usage:
  bootstrap_icons.py            # download + extract + build index (no-op if cached)
  bootstrap_icons.py --check    # exit 0 if cache is healthy, 1 otherwise
  bootstrap_icons.py --refresh  # force re-download
  bootstrap_icons.py --root <dir>  # use a non-default cache root

The script is safe to run repeatedly. It only downloads when the cache is
absent or --refresh is passed.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable

ICON_ZIP_URL = "https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V23.zip"
ICON_ZIP_VERSION = "V23"
DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "azure-icons"

# A handful of hand-curated synonyms for services with awkward filenames.
# Most names are derived automatically; this dict patches the common edge
# cases so users don't have to know the exact MS filename convention.
EXTRA_SYNONYMS: dict[str, str] = {
    "aks": "kubernetes-services",
    "azure-aks": "kubernetes-services",
    "kubernetes": "kubernetes-services",
    "k8s": "kubernetes-services",
    "function": "function-apps",
    "functions": "function-apps",
    "azure-functions": "function-apps",
    "function-app": "function-apps",
    "app-service": "app-services",
    "azure-app-service": "app-services",
    "webapp": "app-services",
    "web-app": "app-services",
    "sql": "sql-database",
    "azuresql": "sql-database",
    "azure-sql": "sql-database",
    "sqldb": "sql-database",
    "cosmos": "azure-cosmos-db",
    "cosmosdb": "azure-cosmos-db",
    "cosmos-db": "azure-cosmos-db",
    "storage": "storage-accounts",
    "blob": "storage-accounts",
    "blob-storage": "storage-accounts",
    "kv": "key-vaults",
    "key-vault": "key-vaults",
    "keyvault": "key-vaults",
    "appins": "application-insights",
    "app-insights": "application-insights",
    "log-analytics": "log-analytics-workspaces",
    "vnet": "virtual-networks",
    "virtual-network": "virtual-networks",
    "subnet": "subnet",
    "nsg": "network-security-groups",
    "firewall": "firewalls",
    "azure-firewall": "firewalls",
    "front-door": "front-door-and-cdn-profiles",
    "frontdoor": "front-door-and-cdn-profiles",
    "afd": "front-door-and-cdn-profiles",
    "app-gateway": "application-gateways",
    "agw": "application-gateways",
    "application-gateway": "application-gateways",
    "service-bus": "azure-service-bus",
    "sb": "azure-service-bus",
    "azuresb": "azure-service-bus",
    "event-hub": "event-hubs",
    "eventhub": "event-hubs",
    "event-grid": "event-grid-domains",
    "eventgrid": "event-grid-domains",
    "redis": "cache-redis",
    "azure-cache-redis": "cache-redis",
    "private-endpoint": "private-endpoints",
    "pe": "private-endpoints",
    "bastion": "bastions",
    "entra": "microsoft-entra-id",
    "aad": "microsoft-entra-id",
    "azure-ad": "microsoft-entra-id",
    "openai": "azure-openai",
    "ai-foundry": "ai-studio",
    "azure-ai-foundry": "ai-studio",
    "foundry": "ai-studio",
    "azure-ai-studio": "ai-studio",
    "container-app": "container-apps-environments",
    "container-apps": "container-apps-environments",
    "aci": "container-instances",
    "container-instance": "container-instances",
    "container-registry": "container-registries",
    "acr": "container-registries",
}


def cache_root_for(args: argparse.Namespace) -> Path:
    return Path(args.root).expanduser() if args.root else DEFAULT_CACHE_ROOT


def check(cache_root: Path) -> int:
    index = cache_root / "index.json"
    if not index.exists():
        print(f"missing: {index}", file=sys.stderr)
        return 1
    try:
        data = json.loads(index.read_text())
    except Exception as e:
        print(f"corrupt index: {e}", file=sys.stderr)
        return 1
    icons = data.get("icons") or {}
    if len(icons) < 100:
        print(f"index has only {len(icons)} icons; expected ~1500+", file=sys.stderr)
        return 1
    sample_path = next(iter(icons.values()))["path"]
    if not Path(sample_path).exists():
        print(f"index references missing file: {sample_path}", file=sys.stderr)
        return 1
    print(f"ok: {len(icons)} icons indexed at {cache_root}")
    return 0


def download_zip(url: str) -> bytes:
    print(f"downloading {url} ...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "azure-svg-diagram-skill/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def extract_zip(blob: bytes, dest: Path) -> None:
    print(f"extracting to {dest} ...", file=sys.stderr)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        # Only extract SVG files; avoid stray macOS/Windows metadata.
        members = [m for m in zf.namelist() if m.lower().endswith(".svg") and not m.startswith("__MACOSX")]
        for m in members:
            zf.extract(m, dest)
    print(f"extracted {len(members)} SVG files", file=sys.stderr)


def derive_canonical(filename: str) -> tuple[str, str]:
    """Return (canonical_key, display_name) for a Microsoft icon filename.

    MS filenames look like '10035-icon-service-App-Services.svg' or
    '03335-icon-service-Subnet.svg'. Strip the numeric prefix and
    'icon-service-' bit, then kebab-case the rest.
    """
    stem = Path(filename).stem
    stem = re.sub(r"^\d+-", "", stem)
    stem = re.sub(r"^icon-(service-)?", "", stem, flags=re.IGNORECASE)
    display = stem.replace("-", " ").replace("_", " ").strip()
    display = re.sub(r"\s+", " ", display)
    canonical = display.lower().replace(" ", "-")
    canonical = re.sub(r"[^a-z0-9-]", "", canonical)
    return canonical, display


def build_index(extracted_root: Path) -> dict:
    icons: dict[str, dict] = {}
    synonyms: dict[str, str] = {}

    svg_files = list(extracted_root.rglob("*.svg"))
    # Microsoft sometimes ships color and mono variants in nearby paths;
    # prefer paths that contain "Service-Icons" (the main service icon dir).
    svg_files.sort(key=lambda p: (0 if "Service-Icons" in p.as_posix() else 1, p.as_posix()))

    for path in svg_files:
        canonical, display = derive_canonical(path.name)
        if not canonical or canonical in icons:
            continue
        icons[canonical] = {
            "path": str(path),
            "display": display,
        }
        # Auto-synonyms: drop trailing 's', add 'azure-' prefix variant.
        if canonical.endswith("s"):
            synonyms.setdefault(canonical[:-1], canonical)
        if not canonical.startswith("azure-"):
            synonyms.setdefault(f"azure-{canonical}", canonical)

    for alias, target in EXTRA_SYNONYMS.items():
        if target in icons:
            synonyms[alias] = target

    return {
        "version": ICON_ZIP_VERSION,
        "source": ICON_ZIP_URL,
        "icons": icons,
        "synonyms": synonyms,
    }


def write_index(cache_root: Path, index: dict) -> None:
    out = cache_root / "index.json"
    out.write_text(json.dumps(index, indent=2, sort_keys=True))
    print(f"wrote {out} ({len(index['icons'])} icons, {len(index['synonyms'])} synonyms)", file=sys.stderr)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report cache health and exit")
    parser.add_argument("--refresh", action="store_true", help="re-download even if cached")
    parser.add_argument("--root", help=f"cache root (default {DEFAULT_CACHE_ROOT})")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cache_root = cache_root_for(args)
    icons_dir = cache_root / "icons"
    zip_path = cache_root / f"Azure_Public_Service_Icons_{ICON_ZIP_VERSION}.zip"

    if args.check:
        return check(cache_root)

    cache_root.mkdir(parents=True, exist_ok=True)

    need_download = args.refresh or not zip_path.exists()
    if need_download:
        blob = download_zip(ICON_ZIP_URL)
        zip_path.write_bytes(blob)
    else:
        blob = zip_path.read_bytes()
        print(f"using cached zip at {zip_path}", file=sys.stderr)

    # Always re-extract on refresh; otherwise extract only if missing.
    if args.refresh or not any(icons_dir.rglob("*.svg") if icons_dir.exists() else []):
        if icons_dir.exists() and args.refresh:
            # Wipe extracted files but keep the dir.
            for p in icons_dir.rglob("*"):
                if p.is_file():
                    p.unlink()
        extract_zip(blob, icons_dir)

    index = build_index(icons_dir)
    if len(index["icons"]) < 100:
        print(
            f"WARNING: built only {len(index['icons'])} icons from {icons_dir}. "
            "ZIP layout may have changed; re-check Microsoft's icons page.",
            file=sys.stderr,
        )
    write_index(cache_root, index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
