# Server Script: ph_rx
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_rx
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

def per_day(d):
    total = 0
    found = False
    for part in str(d or "").replace("/", "-").replace(" ", "-").split("-"):
        try:
            total += float(part)
            found = True
        except:
            pass
    if found:
        return total
    return 0

def days(p):
    parts = str(p or "").split(" ")
    try:
        num = float(parts[0])
    except:
        return 0
    unit = "day"
    if len(parts) > 1:
        unit = parts[1].lower()
    f = 1.0
    if unit.startswith("week"):
        f = 7.0
    elif unit.startswith("month"):
        f = 30.0
    elif unit.startswith("year"):
        f = 365.0
    elif unit.startswith("hour"):
        f = 1.0 / 24
    return num * f

def resolve_item(code):
    if frappe.db.exists("Item", code):
        return code
    gn = frappe.db.get_value("Medication", code, "generic_name") or code
    found = frappe.db.get_value("Item", {"item_name": gn}, "name")
    if found:
        return found
    try:
        it = frappe.db.get_value("Medication", code, "item")
        if it and frappe.db.exists("Item", it):
            return it
    except:
        pass
    try:
        med = frappe.get_doc("Medication", code)
        for r in med.linked_items:
            if r.item:
                return r.item
    except:
        pass
    return ""

patient = frappe.form_dict.get("patient")
if not patient:
    frappe.throw("Choose a patient first.")

out = []
encs = frappe.get_all("Patient Encounter", filters={"patient": patient, "docstatus": 1},
    fields=["name", "encounter_date", "practitioner"],
    order_by="encounter_date desc, creation desc", limit=5)
for e in encs:
    doc = frappe.get_doc("Patient Encounter", e.name)
    drugs = []
    for x in doc.drug_prescription:
        item = resolve_item(x.drug_code)
        item_name = ""
        if item:
            item_name = frappe.db.get_value("Item", item, "item_name") or item
        raw = per_day(x.dosage) * days(x.period)
        units = int(raw)
        if raw > units:
            units += 1
        drugs.append({"drug": x.drug_code, "item": item, "item_name": item_name,
            "dosage": x.dosage or "", "period": x.period or "", "comment": x.comment or "",
            "units": units})
    if not drugs:
        continue
    dx = []
    for x in doc.diagnosis:
        dx.append(x.diagnosis)
    out.append({"id": e.name, "date": str(e.encounter_date),
        "doctor": frappe.db.get_value("Healthcare Practitioner", e.practitioner, "practitioner_name") or "",
        "diagnosis": ", ".join(dx), "drugs": drugs})
frappe.response["message"] = {"encounters": out}
