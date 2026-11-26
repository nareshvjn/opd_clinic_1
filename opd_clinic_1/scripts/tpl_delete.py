# Server Script: tpl_delete
# type: API
# doctype: -
# event: Before Insert
# api_method: tpl_delete
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
ok = (user == "Administrator")
if not ok:
    for r in ["Healthcare Administrator", "System Manager", "Physician"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            ok = True
            break
if not ok:
    frappe.throw("Only doctors can delete treatment templates.")

name = (frappe.form_dict.get("template_name") or "").strip()
if not name:
    frappe.throw("Select a template to delete.")
if not frappe.db.exists("DocType", "Clinic Treatment Template") or not frappe.db.exists("Clinic Treatment Template", name):
    frappe.throw("Treatment template not found.")

frappe.delete_doc("Clinic Treatment Template", name, ignore_permissions=True)
frappe.db.commit()

frappe.response["message"] = {"deleted": name}
