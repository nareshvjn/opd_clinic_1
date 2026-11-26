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
labs = clean_list(json.loads(f.get("labs") or "[]"))
raw_drugs = json.loads(f.get("drugs") or "[]")
notes = (f.get("notes") or "").strip()

drugs = []
seen_drugs = set()
for dr in (raw_drugs or []):
    if not isinstance(dr, dict):
        continue
    dname = (dr.get("drug") or "").strip()
    if not dname:
        continue
    dk = dname.lower()
    if dk in seen_drugs:
        continue
    seen_drugs.add(dk)
    drugs.append({
        "drug": dname,
        "form": (dr.get("form") or "").strip(),
        "mclass": (dr.get("mclass") or "").strip(),
        "strength": str(dr.get("strength") or "").strip(),
        "unit": (dr.get("unit") or "").strip(),
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
