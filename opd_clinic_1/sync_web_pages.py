#!/usr/bin/env python3
"""
Sync Web Pages between opd_clinic_1/www/ and opd_clinic_1/fixtures/web_page.json.

Usage:
    python3 opd_clinic_1/sync_web_pages.py          # Run one-off sync from www/ to web_page.json
    python3 opd_clinic_1/sync_web_pages.py --watch  # Run continuously in background, syncing on any change
"""

import argparse
from datetime import datetime
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
WWW_DIR = os.path.join(SCRIPT_DIR, "www")
FIXTURE_PATH = os.path.join(SCRIPT_DIR, "fixtures", "web_page.json")


def parse_frontmatter(content):
    """Parse optional YAML-style frontmatter from html/md content."""
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1]
            body = parts[2].lstrip("\r\n")
            for line in raw_meta.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if val.isdigit():
                        val = int(val)
                    elif val.lower() == "true":
                        val = 1
                    elif val.lower() == "false":
                        val = 0
                    meta[key] = val
    return meta, body


def sync():
    """Sync files in www/ into fixtures/web_page.json."""
    if not os.path.isdir(WWW_DIR):
        print(f"[sync_web_pages] Directory not found: {WWW_DIR}")
        return False

    # Load existing fixtures if present
    pages = []
    if os.path.isfile(FIXTURE_PATH):
        try:
            with open(FIXTURE_PATH, "r", encoding="utf-8") as fp:
                pages = json.load(fp)
        except Exception as e:
            print(f"[sync_web_pages] Warning: could not parse {FIXTURE_PATH}: {e}")
            pages = []

    pages_by_name = {p.get("name"): p for p in pages if isinstance(p, dict) and p.get("name")}
    updated_count = 0
    added_count = 0

    # Scan for HTML / MD files in www/
    for filename in sorted(os.listdir(WWW_DIR)):
        if filename.startswith(".") or not (filename.endswith(".html") or filename.endswith(".md")):
            continue

        slug, ext = os.path.splitext(filename)
        filepath = os.path.join(WWW_DIR, filename)

        with open(filepath, "r", encoding="utf-8") as fp:
            content = fp.read()

        meta, body = parse_frontmatter(content)

        # Check for matching css file
        css_file = os.path.join(WWW_DIR, f"{slug}.css")
        css_content = ""
        if os.path.isfile(css_file):
            with open(css_file, "r", encoding="utf-8") as fp:
                css_content = fp.read()
        else:
            # Check for inline <style>...</style>
            styles = re.findall(r"<style[^>]*>(.*?)</style>", body, flags=re.DOTALL | re.IGNORECASE)
            if styles:
                css_content = "\n".join(s.strip() for s in styles)

        target_name = meta.get("name", slug)
        title = meta.get("title", slug.replace("-", " ").replace("_", " ").title())
        route = meta.get("route", slug)

        is_html = ext == ".html"

        if target_name in pages_by_name:
            page = pages_by_name[target_name]
            changed = False

            if is_html:
                if page.get("main_section_html") != body:
                    page["main_section_html"] = body
                    changed = True
                if page.get("content_type") != "HTML":
                    page["content_type"] = "HTML"
                    changed = True
            else:
                if page.get("main_section_md") != body:
                    page["main_section_md"] = body
                    changed = True
                if page.get("content_type") != "Markdown":
                    page["content_type"] = "Markdown"
                    changed = True

            if css_content and page.get("css") != css_content:
                page["css"] = css_content
                changed = True

            for k, v in meta.items():
                if page.get(k) != v:
                    page[k] = v
                    changed = True

            if changed:
                page["modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                updated_count += 1
        else:
            new_page = {
                "breadcrumbs": None,
                "content_type": "HTML" if is_html else "Markdown",
                "context_script": None,
                "css": css_content if css_content else None,
                "docstatus": 0,
                "doctype": "Web Page",
                "dynamic_route": 0,
                "dynamic_template": 0,
                "enable_comments": 0,
                "end_date": None,
                "full_width": meta.get("full_width", 1),
                "header": None,
                "insert_style": 0,
                "javascript": None,
                "main_section": None,
                "main_section_html": body if is_html else None,
                "main_section_md": body if not is_html else None,
                "meta_description": meta.get("meta_description"),
                "meta_image": meta.get("meta_image"),
                "meta_title": meta.get("meta_title"),
                "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "module": None,
                "name": target_name,
                "page_blocks": [],
                "published": meta.get("published", 1),
                "route": route,
                "show_sidebar": meta.get("show_sidebar", 0),
                "show_title": meta.get("show_title", 1),
                "slideshow": None,
                "start_date": None,
                "text_align": "Left",
                "title": title,
                "website_sidebar": None,
            }
            pages.append(new_page)
            pages_by_name[target_name] = new_page
            added_count += 1

    if updated_count > 0 or added_count > 0:
        os.makedirs(os.path.dirname(FIXTURE_PATH), exist_ok=True)
        with open(FIXTURE_PATH, "w", encoding="utf-8") as fp:
            json.dump(pages, fp, indent=1, ensure_ascii=False)
            fp.write("\n")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Synced www/ -> web_page.json (Updated: {updated_count}, Added: {added_count})")
        return True

    return False


def watch():
    """Watch www/ directory and sync whenever any file changes."""
    print(f"Watching {WWW_DIR} for changes (Press Ctrl+C to stop)...")
    mtimes = {}

    def get_mtimes():
        current = {}
        if os.path.isdir(WWW_DIR):
            for fname in os.listdir(WWW_DIR):
                fpath = os.path.join(WWW_DIR, fname)
                if os.path.isfile(fpath):
                    try:
                        current[fname] = os.path.getmtime(fpath)
                    except OSError:
                        pass
        return current

    mtimes = get_mtimes()
    sync()

    while True:
        time.sleep(1.0)
        new_mtimes = get_mtimes()
        if new_mtimes != mtimes:
            mtimes = new_mtimes
            sync()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync www/ web pages into fixtures/web_page.json")
    parser.add_argument("--watch", action="store_true", help="Continuously watch www/ and auto-sync on edits")
    args = parser.parse_args()

    if args.watch:
        try:
            watch()
        except KeyboardInterrupt:
            print("\nStopped watcher.")
            sys.exit(0)
    else:
        changed = sync()
        if not changed:
            print("web_page.json is already up to date with www/.")
