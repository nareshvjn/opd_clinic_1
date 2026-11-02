#!/usr/bin/env python3
"""
Unified Auto-Syncer for opd_clinic_1:
  - opd_clinic_1/www/     <--->  opd_clinic_1/fixtures/web_page.json
  - opd_clinic_1/scripts/ <--->  opd_clinic_1/fixtures/server_script.json

Usage:
    python3 opd_clinic_1/sync_all.py          # Run one-off sync for both
    python3 opd_clinic_1/sync_all.py --watch  # Run continuously, auto-syncing both in real time
"""

import argparse
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from sync_web_pages import sync as sync_web_pages, WWW_DIR
from sync_server_scripts import sync_scripts_to_fixture, SCRIPTS_DIR


def sync_all():
    changed_w = sync_web_pages()
    changed_s = sync_scripts_to_fixture()
    return changed_w or changed_s


def watch_all():
    print(f"Watching for changes in:\n  1. {WWW_DIR}\n  2. {SCRIPTS_DIR}\n(Press Ctrl+C to stop)...")

    def get_dir_mtimes(d, ext=None):
        m = {}
        if os.path.isdir(d):
            for f in os.listdir(d):
                if ext and not f.endswith(ext):
                    continue
                if f.startswith(".") or f == "__init__.py":
                    continue
                p = os.path.join(d, f)
                if os.path.isfile(p):
                    try:
                        m[f] = os.path.getmtime(p)
                    except OSError:
                        pass
        return m

    m_www = get_dir_mtimes(WWW_DIR)
    m_scripts = get_dir_mtimes(SCRIPTS_DIR, ".py")

    sync_all()

    while True:
        time.sleep(1.0)
        new_w = get_dir_mtimes(WWW_DIR)
        new_s = get_dir_mtimes(SCRIPTS_DIR, ".py")

        if new_w != m_www:
            m_www = new_w
            sync_web_pages()

        if new_s != m_scripts:
            m_scripts = new_s
            sync_scripts_to_fixture()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified sync for www/ and scripts/")
    parser.add_argument("--watch", action="store_true", help="Continuously watch www/ and scripts/")
    args = parser.parse_args()

    if args.watch:
        try:
            watch_all()
        except KeyboardInterrupt:
            print("\nWatcher stopped.")
            sys.exit(0)
    else:
        sync_all()
