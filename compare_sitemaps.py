#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compare URL path structures between two websites by crawling their sitemaps.

Features
- Recursively resolves <sitemapindex> → child sitemaps
- Handles .xml and .xml.gz
- Extracts all <loc> URLs and converts to normalized pathnames
- Compares sets and writes an Excel report

Usage:
  python compare_sitemaps.py https://old.com/sitemap.xml https://new.com/sitemap.xml -o out.xlsx
"""

import argparse
import gzip
import io
import sys
from typing import Iterable, Set, Tuple, List
from urllib.parse import urlparse, urlunparse

import requests
import xml.etree.ElementTree as ET
import pandas as pd

DEFAULT_TIMEOUT = 30
HEADERS = {
    "User-Agent": "SitemapPathComparator/1.0 (+https://example.com)"
}


def fetch_bytes(url: str) -> bytes:
    """Fetch bytes from URL, auto-decompress if .gz or gzip content."""
    resp = requests.get(url, headers=HEADERS, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    content = resp.content

    # If URL ends with .gz or server returns gzip content, try decompress
    is_gz = url.lower().endswith(".gz") or resp.headers.get("Content-Encoding", "").lower() == "gzip"
    if is_gz:
        try:
            return gzip.decompress(content)
        except OSError:
            # Not actually gzipped; fall through
            pass
    return content


def strip_ns(tag: str) -> str:
    """Strip XML namespace from tag like '{ns}tag' -> 'tag'."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_sitemap_xml(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)


def iter_loc_values(root: ET.Element) -> Iterable[str]:
    """Yield all text values from <loc> elements anywhere in the tree."""
    for el in root.iter():
        if strip_ns(el.tag).lower() == "loc" and el.text:
            yield el.text.strip()


def is_sitemap_index(root: ET.Element) -> bool:
    return strip_ns(root.tag).lower() == "sitemapindex"


def is_urlset(root: ET.Element) -> bool:
    return strip_ns(root.tag).lower() == "urlset"


def normalize_path(
    url: str,
    keep_trailing_slash: bool = False,
    respect_case: bool = False,
    include_query: bool = False,
) -> str:
    """
    Convert URL to a comparison key:
      - ignore scheme/host (and fragment)
      - optionally ignore query (default)
      - normalize case (default lower)
      - trim trailing slash (default)
      - treat empty path as "/"
    """
    parsed = urlparse(url)

    # Path component
    path = parsed.path or "/"

    # Optionally include query as part of the key (less common for structural checks)
    if include_query and parsed.query:
        # Rebuild with only path+query
        path = urlunparse(("", "", path, "", parsed.query, ""))

    # Normalize trailing slash (default: remove unless root '/')
    if not keep_trailing_slash and path != "/":
        path = path.rstrip("/")

    # Normalize case (default: lowercase)
    if not respect_case:
        path = path.lower()

    return path or "/"


def is_media_url(url: str) -> bool:
    """Check if the URL points to a media file based on its extension."""
    media_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
                        '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.mkv',
                        '.ogg', '.wav', '.flac', '.aac', '.webm'}
    parsed = urlparse(url)
    return any(parsed.path.lower().endswith(ext) for ext in media_extensions)


def gather_all_urls_from_sitemap(
    sitemap_url: str,
    visited: Set[str] = None,
) -> Set[str]:
    """
    Recursively gather all <loc> URLs from a sitemap or sitemap index,
    excluding media URLs.
    """
    if visited is None:
        visited = set()

    if sitemap_url in visited:
        return set()
    visited.add(sitemap_url)

    try:
        xml_bytes = fetch_bytes(sitemap_url)
    except Exception as e:
        print(f"[WARN] Failed to fetch {sitemap_url}: {e}", file=sys.stderr)
        return set()

    try:
        root = parse_sitemap_xml(xml_bytes)
    except Exception as e:
        print(f"[WARN] Failed to parse XML from {sitemap_url}: {e}", file=sys.stderr)
        return set()

    urls = set()

    if is_sitemap_index(root):
        # Recurse into child sitemaps
        for loc in iter_loc_values(root):
            urls |= gather_all_urls_from_sitemap(loc, visited)
    elif is_urlset(root):
        # Collect URLs
        urls |= {url for url in iter_loc_values(root) if not is_media_url(url)}
    else:
        # Unknown root — try to collect any <loc> anyway
        locs = {url for url in iter_loc_values(root) if not is_media_url(url)}
        if locs:
            urls |= locs
        else:
            print(f"[WARN] Unknown sitemap type at {sitemap_url}; no <loc> found.", file=sys.stderr)

    return urls


def compare_paths(
    urls_a: Set[str],
    urls_b: Set[str],
    *,
    keep_trailing_slash: bool = False,
    respect_case: bool = False,
    include_query: bool = False,
) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Return (matches, only_in_a, only_in_b) on normalized path keys.
    """
    paths_a = {normalize_path(u, keep_trailing_slash, respect_case, include_query) for u in urls_a}
    paths_b = {normalize_path(u, keep_trailing_slash, respect_case, include_query) for u in urls_b}

    matches = paths_a & paths_b
    only_in_a = paths_a - paths_b
    only_in_b = paths_b - paths_a

    return matches, only_in_a, only_in_b


def write_excel_report(
    matches: Set[str],
    only_in_a: Set[str],
    only_in_b: Set[str],
    out_path: str,
    label_a: str,
    label_b: str,
):
    """
    Save results into an Excel workbook with helpful sheets.
    """
    def sorted_list(s: Set[str]) -> List[str]:
        return sorted(s, key=lambda x: (x.count("/"), x))  # group shallow paths first

    matches_list = sorted_list(matches)
    only_a_list = sorted_list(only_in_a)
    only_b_list = sorted_list(only_in_b)

    all_rows = []
    all_rows += [{"status": "MATCH", "pathname": p, "source": "both"} for p in matches_list]
    all_rows += [{"status": "ONLY_IN_A", "pathname": p, "source": label_a} for p in only_a_list]
    all_rows += [{"status": "ONLY_IN_B", "pathname": p, "source": label_b} for p in only_b_list]

    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        # Overview
        overview = pd.DataFrame(
            [
                {"Metric": "Total (A)", "Value": len(matches_list) + len(only_a_list)},
                {"Metric": "Total (B)", "Value": len(matches_list) + len(only_b_list)},
                {"Metric": "Matches", "Value": len(matches_list)},
                {"Metric": f"Only in A ({label_a})", "Value": len(only_a_list)},
                {"Metric": f"Only in B ({label_b})", "Value": len(only_b_list)},
            ]
        )
        overview.to_excel(writer, sheet_name="Overview", index=False)

        # Detailed sheets
        pd.DataFrame({"pathname": matches_list}).to_excel(writer, sheet_name="Matches", index=False)
        pd.DataFrame({"pathname": only_a_list}).to_excel(writer, sheet_name="Only_in_A", index=False)
        pd.DataFrame({"pathname": only_b_list}).to_excel(writer, sheet_name="Only_in_B", index=False)
        pd.DataFrame(all_rows)[["status", "pathname", "source"]].to_excel(writer, sheet_name="All", index=False)

        # Autofit columns a bit
        for sheet in ["Overview", "Matches", "Only_in_A", "Only_in_B", "All"]:
            ws = writer.sheets[sheet]
            ws.set_column(0, 0, 22)
            ws.set_column(1, 1, 80)
            ws.set_column(2, 2, 20)


def main():
    parser = argparse.ArgumentParser(description="Compare sitemap pathnames between two websites.")
    parser.add_argument("sitemap_a", help="Sitemap URL for OLD site (parent or index sitemap).")
    parser.add_argument("sitemap_b", help="Sitemap URL for NEW site (parent or index sitemap).")
    parser.add_argument("-o", "--out", default="sitemap_comparison.xlsx", help="Output Excel file path.")
    parser.add_argument("--label-a", default="OLD", help="Label for site A in the report.")
    parser.add_argument("--label-b", default="NEW", help="Label for site B in the report.")
    parser.add_argument("--keep-trailing-slash", action="store_true", help="Keep trailing slash during normalization.")
    parser.add_argument("--respect-case", action="store_true", help="Do not lowercase paths during normalization.")
    parser.add_argument("--include-query", action="store_true", help="Include querystring in comparison key.")

    args = parser.parse_args()

    print(f"[INFO] Fetching and expanding sitemap A: {args.sitemap_a}")
    urls_a = gather_all_urls_from_sitemap(args.sitemap_a)
    print(f"[INFO] Found {len(urls_a)} URLs in A")

    print(f"[INFO] Fetching and expanding sitemap B: {args.sitemap_b}")
    urls_b = gather_all_urls_from_sitemap(args.sitemap_b)
    print(f"[INFO] Found {len(urls_b)} URLs in B")

    print("[INFO] Comparing normalized pathnames...")
    matches, only_in_a, only_in_b = compare_paths(
        urls_a,
        urls_b,
        keep_trailing_slash=args.keep_trailing_slash,
        respect_case=args.respect_case,
        include_query=args.include_query,
    )

    print(f"[RESULT] Matches: {len(matches)} | Only in A: {len(only_in_a)} | Only in B: {len(only_in_b)}")

    print(f"[INFO] Writing Excel report → {args.out}")
    write_excel_report(matches, only_in_a, only_in_b, args.out, args.label_a, args.label_b)
    print("[DONE] Report generated.")


if __name__ == "__main__":
    # Fail-fast helpful message if pandas/xlsxwriter missing
    try:
        import xlsxwriter  # noqa: F401
    except Exception:
        print("[WARN] The 'xlsxwriter' engine is recommended for best Excel output. Install via: pip install xlsxwriter", file=sys.stderr)
    main()
