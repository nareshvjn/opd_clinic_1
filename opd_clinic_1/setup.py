import os
import shutil
import frappe

def after_migrate():
    """Ensure logo, pwa script, and assets symlink exist on the site."""
    try:
        site_files = frappe.get_site_path("public", "files")
        os.makedirs(site_files, exist_ok=True)

        # 1. Ensure logo.png is in site files
        target_logo = os.path.join(site_files, "logo.png")
        if not os.path.exists(target_logo):
            src_logo = frappe.get_app_path("opd_clinic_1", "public", "images", "logo.png")
            if os.path.exists(src_logo):
                shutil.copyfile(src_logo, target_logo)

        # 2. Ensure pwa.js is copied to site files (/files/pwa.js)
        src_pwa = frappe.get_app_path("opd_clinic_1", "public", "js", "pwa.js")
        if os.path.exists(src_pwa):
            target_pwa = os.path.join(site_files, "pwa.js")
            shutil.copyfile(src_pwa, target_pwa)

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
    except Exception as e:
        pass
