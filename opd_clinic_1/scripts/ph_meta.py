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

default_wh = ""
try:
    if frappe.get_meta("Stock Settings").has_field("default_warehouse"):
        default_wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
except:
    pass
if not default_wh:
    try:
        default_wh = frappe.db.get_value("Company", company, "default_warehouse")
    except:
        pass
if not default_wh and whs:
    default_wh = whs[0]

sup = []
for s in frappe.get_all("Supplier", filters={"disabled": 0}, fields=["name"], order_by="name", limit=500):
    sup.append(s.name)
modes = []
for m in frappe.get_all("Mode of Payment", filters={"enabled": 1}, fields=["name"], order_by="name"):
    modes.append(m.name)

dosage_forms = []
try:
    if frappe.db.exists("DocType", "Dosage Form"):
        for df in frappe.get_all("Dosage Form", fields=["name"], order_by="name"):
            dosage_forms.append(df.name)
except:
    pass
if not dosage_forms:
    dosage_forms = ["Tablet", "Capsule", "Syrup", "Injection", "Drops", "Ointment", "Cream", "Suspension", "Inhaler", "Gel", "Lotion", "Powder", "Spray"]

med_classes = []
try:
    if frappe.db.exists("DocType", "Medication Class"):
        for mc in frappe.get_all("Medication Class", fields=["name"], order_by="name"):
            med_classes.append(mc.name)
except:
    pass
if not med_classes:
    med_classes = ["Drug", "General"]

item_groups = []
try:
    if frappe.db.exists("DocType", "Item Group"):
        for ig in frappe.get_all("Item Group", filters={"is_group": 0}, fields=["name"], order_by="name"):
            item_groups.append(ig.name)
except:
    pass
if not item_groups:
    item_groups = ["Drug"]

token = ""
try:
    token = frappe.session.get("csrf_token") or ""
except:
    token = ""

frappe.response["message"] = {
    "company": company,
    "warehouses": whs,
    "warehouse": default_wh,
    "suppliers": sup,
    "modes": modes,
    "dosage_forms": dosage_forms,
    "medication_classes": med_classes,
    "item_groups": item_groups,
    "csrf": token
}
