# Server Script: tpl_save
# type: API
# doctype: -
# event: Before Insert
# api_method: tpl_save
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
    frappe.throw("Only doctors can save treatment templates.")

if not frappe.db.exists("DocType", "Clinic Treatment Template"):
    frappe.throw("Clinic Treatment Template DocType is not installed yet. Run bench migrate.")

f = frappe.form_dict
name = (f.get("template_name") or "").strip()
if not name:
    frappe.throw("Enter a template name.")
overwrite = f.get("overwrite") == "1" or f.get("overwrite") is True

def clean_list(raw):
    out = []
    seen = set()
    for item in (raw or []):
        val = str(item or "").strip()
        if not val:
            continue
        k = val.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(val)
    return out

complaints = clean_list(json.loads(f.get("symptoms") or "[]"))
diagnosis = clean_list(json.loads(f.get("diagnosis") or "[]"))
raw_labs = clean_list(json.loads(f.get("labs") or "[]"))
raw_drugs = json.loads(f.get("drugs") or "[]")
notes = (f.get("notes") or "").strip()

labs = []
has_lab_dt = frappe.db.exists("DocType", "Lab Test Template")
for lt_val in raw_labs:
    lt_name = lt_val
    if has_lab_dt:
        lt_name = frappe.db.get_value("Lab Test Template", lt_val, "name")
        if not lt_name:
            try:
                lt_name = frappe.db.get_value("Lab Test Template", {"lab_test_name": lt_val}, "name") or frappe.db.get_value("Lab Test Template", {"lab_test_code": lt_val}, "name")
            except Exception:
                lt_name = None
        if not lt_name:
            frappe.throw("Lab test '" + lt_val + "' was not found in Lab Test Template. Please select an existing lab test.")
    if lt_name not in labs:
        labs.append(lt_name)

has_med_dt = frappe.db.exists("DocType", "Medication")
meta_med = frappe.get_meta("Medication") if has_med_dt else None
has_med_name = meta_med.has_field("medication_name") if meta_med else False

drugs = []
seen_drugs = set()
for dr in (raw_drugs or []):
    if not isinstance(dr, dict):
        continue
    dname = (dr.get("drug") or "").strip()
    if not dname:
        continue
    if has_med_dt:
        med = frappe.db.get_value("Medication", dname, "name")
        if not med and has_med_name:
            med = frappe.db.get_value("Medication", {"medication_name": dname}, "name")
        if not med:
            frappe.throw("Medication '" + dname + "' is not available in the Medication list. Please select an existing medication.")
        dname = med
    dk = dname.lower()
    if dk in seen_drugs:
        continue
    seen_drugs.add(dk)
    drugs.append({
        "drug": dname,
        "form": (dr.get("form") or "").strip(),
        "dosage": (dr.get("dosage") or "").strip(),
        "period": (dr.get("period") or "").strip(),
        "comment": (dr.get("comment") or "").strip(),
    })

if not (complaints or diagnosis or drugs or labs or notes):
    frappe.throw("Add at least one complaint, diagnosis, medicine, lab test, or note before saving a template.")

exists = frappe.db.exists("Clinic Treatment Template", name)
if exists and not overwrite:
    frappe.throw("A template named '" + name + "' already exists. Confirm overwrite or choose another name.")

prac = (f.get("practitioner") or "").strip()
if prac and not frappe.db.exists("Healthcare Practitioner", prac):
    prac = ""

parts = []
if complaints:
    parts.append("Complaints: " + ", ".join(complaints[:3]) + ("..." if len(complaints) > 3 else ""))
if diagnosis:
    parts.append("Diagnosis: " + ", ".join(diagnosis[:3]) + ("..." if len(diagnosis) > 3 else ""))
if drugs:
    parts.append(str(len(drugs)) + " medicine" + ("s" if len(drugs) != 1 else ""))
if labs:
    parts.append(str(len(labs)) + " lab" + ("s" if len(labs) != 1 else ""))
if notes:
    parts.append("Notes")
summary = " | ".join(parts)

payload = {
    "complaints": complaints,
    "diagnosis": diagnosis,
    "drugs": drugs,
    "labs": labs,
    "notes": notes,
}

if exists:
    doc = frappe.get_doc("Clinic Treatment Template", name)
else:
    doc = frappe.new_doc("Clinic Treatment Template")
    doc.template_name = name

doc.practitioner = prac or ""
doc.is_active = 1
doc.notes = notes
doc.summary = summary
doc.template_json = json.dumps(payload)

if exists:
    doc.save(ignore_permissions=True)
else:
    doc.insert(ignore_permissions=True)
frappe.db.commit()

frappe.response["message"] = {
    "template": {
        "name": doc.name,
        "template_name": doc.template_name,
        "practitioner": doc.practitioner or "",
        "summary": summary,
        "complaints": complaints,
        "diagnosis": diagnosis,
        "drugs": drugs,
        "labs": labs,
        "notes": notes,
    }
}
