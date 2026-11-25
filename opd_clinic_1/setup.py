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
    except Exception:
        pass
