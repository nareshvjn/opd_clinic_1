# Server Script: ph_meta
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_meta
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

company = frappe.db.get_single_value("Global Defaults", "default_company")
whs = []
for w in frappe.get_all("Warehouse", filters={"is_group": 0, "disabled": 0, "company": company},
        fields=["name"], order_by="name"):
    whs.append(w.name)
default_wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
if not default_wh and whs:
    default_wh = whs[0]
sup = []
for s in frappe.get_all("Supplier", filters={"disabled": 0}, fields=["name"], order_by="name", limit=500):
    sup.append(s.name)
modes = []
for m in frappe.get_all("Mode of Payment", filters={"enabled": 1}, fields=["name"], order_by="name"):
    modes.append(m.name)
token = ""
try:
    token = frappe.session.get("csrf_token") or ""
except:
    token = ""
frappe.response["message"] = {"company": company, "warehouses": whs, "warehouse": default_wh,
    "suppliers": sup, "modes": modes, "csrf": token}
