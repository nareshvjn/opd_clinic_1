import os
import shutil
import frappe

def after_migrate():
    """Ensure logo and static assets exist in the site's public files folder on new systems."""
    try:
        site_files = frappe.get_site_path("public", "files")
        target = os.path.join(site_files, "logo.png")
        if not os.path.exists(target):
            src = frappe.get_app_path("opd_clinic_1", "public", "images", "logo.png")
            if os.path.exists(src):
                os.makedirs(site_files, exist_ok=True)
                shutil.copyfile(src, target)
    except Exception as e:
        pass
