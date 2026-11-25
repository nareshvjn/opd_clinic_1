import json
import os
import shutil
import frappe

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

        # 4. Ensure Web Page rows match fixtures/web_page.json (even if DB modified timestamp was newer)
        try:
            wp_path = frappe.get_app_path("opd_clinic_1", "fixtures", "web_page.json")
            if os.path.exists(wp_path):
                with open(wp_path, "r", encoding="utf-8") as fp:
                    wps = json.load(fp)
                updated_wp = False
                for wp in wps:
                    name = wp.get("name")
                    if not name or not frappe.db.exists("Web Page", name):
                        continue
                    cur = frappe.db.get_value(
                        "Web Page",
                        name,
                        ["main_section", "main_section_html", "css"],
                        as_dict=True,
                    ) or {}
                    target_main = wp.get("main_section") or ""
                    target_html = wp.get("main_section_html") or target_main
                    target_css = wp.get("css") or ""
                    if (
                        (cur.get("main_section") or "") != target_main
                        or (cur.get("main_section_html") or "") != target_html
                        or (cur.get("css") or "") != target_css
                    ):
                        frappe.db.set_value(
                            "Web Page",
                            name,
                            {
                                "main_section": target_main,
                                "main_section_html": target_html,
                                "css": target_css,
                            },
                            update_modified=False,
                        )
                        updated_wp = True
                if updated_wp:
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
