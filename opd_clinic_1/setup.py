import json
import os
import shutil
import frappe

def _sync_fixture_fields(fixture_filename, doctype, fields):
    """Force-sync specific fixture fields to DB even if DB modified timestamp is newer."""
    path = frappe.get_app_path("opd_clinic_1", "fixtures", fixture_filename)
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fp:
        rows = json.load(fp)
    updated = False
    for row in rows:
        name = row.get("name")
        if not name or not frappe.db.exists(doctype, name):
            continue
        cur = frappe.db.get_value(doctype, name, fields, as_dict=True) or {}
        updates = {}
        for field in fields:
            target = row.get(field) or ""
            if field == "main_section_html" and not target:
                target = row.get("main_section") or ""
            if (cur.get(field) or "") != target:
                updates[field] = target
        if updates:
            frappe.db.set_value(doctype, name, updates, update_modified=False)
            updated = True
    if updated:
        frappe.db.commit()


def after_migrate():
    """Ensure logo, PWA icons, manifest, pwa script, service worker, and assets symlink exist on the site."""
    try:
        site_public = frappe.get_site_path("public")
        site_files = os.path.join(site_public, "files")
        os.makedirs(site_files, exist_ok=True)

        # 1. Ensure logo.png exists in site files (preserve custom override if present)
        target_logo = os.path.join(site_files, "logo.png")
        if not os.path.exists(target_logo):
            src_logo = frappe.get_app_path("opd_clinic_1", "public", "images", "logo.png")
            if os.path.exists(src_logo):
                shutil.copyfile(src_logo, target_logo)

        # 2. Sync PWA icons, manifest.json, and pwa.js to /files/ so nginx serves them directly
        file_copies = [
            (frappe.get_app_path("opd_clinic_1", "public", "images", "icon-192.png"), os.path.join(site_files, "icon-192.png")),
            (frappe.get_app_path("opd_clinic_1", "public", "images", "icon-512.png"), os.path.join(site_files, "icon-512.png")),
            (frappe.get_app_path("opd_clinic_1", "public", "images", "icon-maskable-512.png"), os.path.join(site_files, "icon-maskable-512.png")),
            (frappe.get_app_path("opd_clinic_1", "public", "manifest.json"), os.path.join(site_files, "manifest.json")),
            (frappe.get_app_path("opd_clinic_1", "public", "js", "pwa.js"), os.path.join(site_files, "pwa.js")),
            (frappe.get_app_path("opd_clinic_1", "www", "sw.js"), os.path.join(site_public, "sw.js")),
        ]
        for src_path, dst_path in file_copies:
            if os.path.exists(src_path):
                shutil.copyfile(src_path, dst_path)

        # 3. Ensure sites/assets/opd_clinic_1 symlink exists for nginx
        bench_assets = os.path.abspath(os.path.join(frappe.get_site_path(), "..", "assets"))
        if os.path.isdir(bench_assets):
            app_public = frappe.get_app_path("opd_clinic_1", "public")
            symlink_target = os.path.join(bench_assets, "opd_clinic_1")
            if not os.path.exists(symlink_target) and not os.path.islink(symlink_target):
                try:
                    os.symlink(app_public, symlink_target)
                except Exception:
                    pass

        # 4. Force-sync Web Page and Server Script rows from fixtures even if DB modified is newer
        for fixture_file, dt, sync_fields in (
            ("web_page.json", "Web Page", ["main_section", "main_section_html", "css"]),
            ("server_script.json", "Server Script", ["script"]),
        ):
            try:
                _sync_fixture_fields(fixture_file, dt, sync_fields)
            except Exception:
                pass

        # 4b. Sync global Website Settings banner_html from www/banner.html if present
        try:
            banner_path = frappe.get_app_path("opd_clinic_1", "www", "banner.html")
            if os.path.exists(banner_path):
                with open(banner_path, "r", encoding="utf-8") as fp:
                    banner_html = fp.read()
                cur_banner = frappe.db.get_single_value("Website Settings", "banner_html") or ""
                if cur_banner != banner_html:
                    frappe.db.set_single_value("Website Settings", "banner_html", banner_html, update_modified=False)
                    frappe.db.commit()
        except Exception:
            pass

        # 5. Clear Frappe & Website caches so updated Web Pages serve immediately
        try:
            from frappe.website.utils import clear_website_cache
            clear_website_cache()
        except Exception:
            pass
        try:
            frappe.clear_cache()
        except Exception:
            pass
    except Exception:
        pass
