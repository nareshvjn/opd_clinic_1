#!/usr/bin/env python3
"""
Sync Server Scripts between opd_clinic_1/scripts/ and opd_clinic_1/fixtures/server_script.json.

Usage:
    python3 opd_clinic_1/sync_server_scripts.py          # Run one-off sync from scripts/ to server_script.json
    python3 opd_clinic_1/sync_server_scripts.py --watch  # Run continuously, auto-syncing on any edit in scripts/
    python3 opd_clinic_1/sync_server_scripts.py --export # Export server_script.json to scripts/
"""

import argparse
from datetime import datetime
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SCRIPT_DIR, "scripts")
FIXTURE_PATH = os.path.join(SCRIPT_DIR, "fixtures", "server_script.json")


def parse_script_file(filepath):
    """Parse header comments and python body from a script file."""
    with open(filepath, "r", encoding="utf-8") as fp:
        content = fp.read()

    filename = os.path.basename(filepath)
    slug, _ = os.path.splitext(filename)

    meta = {
        "name": slug,
        "script_type": "API",
        "reference_doctype": None,
        "doctype_event": "Before Insert",
        "api_method": slug,
        "allow_guest": 0,
        "event_frequency": "All",
        "disabled": 0,
    }

    lines = content.splitlines()
    body_start_idx = 0

    for idx, line in enumerate(lines):
        line_s = line.strip()
        if line_s.startswith("#"):
            comment = line_s.lstrip("#").strip()
            if ":" in comment:
                k, v = comment.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if k in ["server script", "name"]:
                    meta["name"] = v
                elif k == "type":
                    meta["script_type"] = v
                elif k in ["doctype", "reference_doctype"]:
                    meta["reference_doctype"] = None if v in ["-", "", "none", "None"] else v
                elif k in ["event", "doctype_event"]:
                    meta["doctype_event"] = v
                elif k == "api_method":
                    meta["api_method"] = v
                elif k == "allow_guest":
                    meta["allow_guest"] = 1 if v in ["1", "true", "True"] else 0
                elif k == "frequency":
                    meta["event_frequency"] = v
                elif k == "disabled":
                    meta["disabled"] = 1 if v in ["1", "true", "True"] else 0
            body_start_idx = idx + 1
        elif not line_s:
            body_start_idx = idx + 1
        else:
            break

    # Body is everything after the header comments (or the full content)
    body = "\n".join(lines[body_start_idx:]).lstrip("\r\n")

    return meta, body, content


def sync_scripts_to_fixture():
    """Translate all .py files in scripts/ into fixtures/server_script.json."""
    if not os.path.isdir(SCRIPTS_DIR):
        print(f"[sync_server_scripts] Directory not found: {SCRIPTS_DIR}")
        return False

    existing_scripts = []
    if os.path.isfile(FIXTURE_PATH):
        try:
            with open(FIXTURE_PATH, "r", encoding="utf-8") as fp:
                existing_scripts = json.load(fp)
        except Exception as e:
            print(f"[sync_server_scripts] Warning: could not parse {FIXTURE_PATH}: {e}")
            existing_scripts = []

    scripts_by_name = {
        s.get("name"): s for s in existing_scripts if isinstance(s, dict) and s.get("name")
    }

    updated_count = 0
    added_count = 0

    for filename in sorted(os.listdir(SCRIPTS_DIR)):
        if filename.startswith(".") or filename == "__init__.py" or not filename.endswith(".py"):
            continue

        filepath = os.path.join(SCRIPTS_DIR, filename)
        meta, body, full_content = parse_script_file(filepath)
        name = meta["name"]

        # Note: In Frappe, storing the full file with comments preserves header when exported
        script_code = full_content

        if name in scripts_by_name:
            doc = scripts_by_name[name]
            changed = False

            if doc.get("script") != script_code:
                doc["script"] = script_code
                changed = True
            if doc.get("script_type") != meta["script_type"]:
                doc["script_type"] = meta["script_type"]
                changed = True
            if doc.get("api_method") != meta["api_method"]:
                doc["api_method"] = meta["api_method"]
                changed = True
            if doc.get("allow_guest") != meta["allow_guest"]:
                doc["allow_guest"] = meta["allow_guest"]
                changed = True
            if doc.get("disabled") != meta["disabled"]:
                doc["disabled"] = meta["disabled"]
                changed = True
            if doc.get("reference_doctype") != meta["reference_doctype"]:
                doc["reference_doctype"] = meta["reference_doctype"]
                changed = True
            if doc.get("doctype_event") != meta["doctype_event"]:
                doc["doctype_event"] = meta["doctype_event"]
                changed = True

            if changed:
                doc["modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                updated_count += 1
        else:
            new_doc = {
                "allow_guest": meta["allow_guest"],
                "api_method": meta["api_method"],
                "cron_format": None,
                "disabled": meta["disabled"],
                "docstatus": 0,
                "doctype": "Server Script",
                "doctype_event": meta["doctype_event"],
                "enable_rate_limit": 0,
                "event_frequency": meta["event_frequency"],
                "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "module": "opd_clinic_1",
                "name": name,
                "rate_limit_count": 5,
                "rate_limit_seconds": 86400,
                "reference_doctype": meta["reference_doctype"],
                "script": script_code,
                "script_type": meta["script_type"],
            }
            existing_scripts.append(new_doc)
            scripts_by_name[name] = new_doc
            added_count += 1

    if updated_count > 0 or added_count > 0:
        os.makedirs(os.path.dirname(FIXTURE_PATH), exist_ok=True)
        with open(FIXTURE_PATH, "w", encoding="utf-8") as fp:
            json.dump(existing_scripts, fp, indent=1, ensure_ascii=False)
            fp.write("\n")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Synced scripts/ -> server_script.json (Updated: {updated_count}, Added: {added_count})")
        return True

    return False


def export_fixture_to_scripts():
    """Translate server_script.json into individual .py files in scripts/."""
    if not os.path.isfile(FIXTURE_PATH):
        print(f"[sync_server_scripts] File not found: {FIXTURE_PATH}")
        return False

    with open(FIXTURE_PATH, "r", encoding="utf-8") as fp:
        scripts = json.load(fp)

    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    count = 0

    for doc in scripts:
        name = doc.get("name")
        if not name:
            continue

        filepath = os.path.join(SCRIPTS_DIR, f"{name}.py")
        code = doc.get("script") or ""

        # Check if code already contains header comments
        has_header = code.startswith("# Server Script:") or "# type:" in code[:200]

        if not has_header:
            header_lines = [
                f"# Server Script: {name}",
                f"# type: {doc.get('script_type', 'API')}",
                f"# doctype: {doc.get('reference_doctype') or '-'}",
                f"# event: {doc.get('doctype_event') or 'Before Insert'}",
                f"# api_method: {doc.get('api_method') or name}",
                f"# allow_guest: {doc.get('allow_guest', 0)}",
                f"# frequency: {doc.get('event_frequency', 'All')}",
                f"# disabled: {doc.get('disabled', 0)}",
                "",
            ]
            full_code = "\n".join(header_lines) + code.lstrip("\r\n")
        else:
            full_code = code

        with open(filepath, "w", encoding="utf-8") as fp:
            fp.write(full_code)
            if not full_code.endswith("\n"):
                fp.write("\n")
        count += 1

    print(f"Exported {count} server scripts from {FIXTURE_PATH} to {SCRIPTS_DIR}/")
    return True


def watch():
    """Watch scripts/ directory and auto-sync to server_script.json."""
    print(f"Watching {SCRIPTS_DIR} for changes (Press Ctrl+C to stop)...")
    mtimes = {}

    def get_mtimes():
        current = {}
        if os.path.isdir(SCRIPTS_DIR):
            for fname in os.listdir(SCRIPTS_DIR):
                if fname.endswith(".py") and fname != "__init__.py":
                    fpath = os.path.join(SCRIPTS_DIR, fname)
                    try:
                        current[fname] = os.path.getmtime(fpath)
                    except OSError:
                        pass
        return current

    mtimes = get_mtimes()
    sync_scripts_to_fixture()

    while True:
        time.sleep(1.0)
        new_mtimes = get_mtimes()
        if new_mtimes != mtimes:
            mtimes = new_mtimes
            sync_scripts_to_fixture()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync scripts/ with fixtures/server_script.json")
    parser.add_argument("--watch", action="store_true", help="Continuously watch scripts/ and auto-sync on edits")
    parser.add_argument("--export", action="store_true", help="Export server_script.json into scripts/ files")
    args = parser.parse_args()

    if args.export:
        export_fixture_to_scripts()
    elif args.watch:
        try:
            watch()
        except KeyboardInterrupt:
            print("\nStopped watcher.")
            sys.exit(0)
    else:
        changed = sync_scripts_to_fixture()
        if not changed:
            print("server_script.json is already up to date with scripts/.")
