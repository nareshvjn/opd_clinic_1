# Server Script: enc_amend
# type: API
# doctype: -
# event: Before Insert
# api_method: enc_amend
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
admin = False
ok = False
for r in ["Physician", "Healthcare Administrator", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
for r in ["Healthcare Administrator", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        admin = True
if not ok:
    frappe.throw("Only doctors can edit a consultation.")

name = (frappe.form_dict.get("encounter") or "").strip()
if not name or not frappe.db.exists("Patient Encounter", name):
    frappe.throw("That consultation was not found.")
old = frappe.get_doc("Patient Encounter", name)
if old.docstatus != 1:
    frappe.throw("Only a completed consultation can be edited this way.")
if not old.appointment:
    frappe.throw("This consultation has no appointment, so it cannot be reopened from this page. Amend it in Desk.")
if not admin:
    mine = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name")
    if mine and old.practitioner != mine:
        frappe.throw("This consultation belongs to another doctor.")

new = frappe.new_doc("Patient Encounter")
new.patient = old.patient
new.practitioner = old.practitioner
new.appointment = old.appointment
new.company = old.company
new.encounter_comment = old.encounter_comment or ""
if old.encounter_date:
    new.encounter_date = old.encounter_date
new.amended_from = old.name
for x in old.symptoms:
    new.append("symptoms", {"complaint": x.complaint})
for x in old.diagnosis:
    new.append("diagnosis", {"diagnosis": x.diagnosis})
for x in old.drug_prescription:
    row = {"drug_code": x.drug_code, "dosage_form": x.dosage_form, "comment": x.comment or ""}
    if x.dosage:
        row["dosage"] = x.dosage
    if x.period:
        row["period"] = x.period
    new.append("drug_prescription", row)
for x in old.lab_test_prescription:
    new.append("lab_test_prescription", {"lab_test_code": x.lab_test_code})

# Marley creates a Medication Request for each medicine when an encounter is completed.
# They block the cancel, so cancel them first (completing the amended copy creates fresh ones).
reqs = []
for fld in ["order_group", "patient_encounter"]:
    try:
        for x in frappe.get_all("Medication Request", filters={fld: old.name}, fields=["name", "docstatus"]):
            seen = False
            for y in reqs:
                if y.name == x.name:
                    seen = True
            if not seen:
                reqs.append(x)
    except:
        pass
for x in reqs:
    mr = frappe.get_doc("Medication Request", x.name)
    mr.flags.ignore_permissions = True
    try:
        if mr.docstatus == 1:
            mr.cancel()
        elif mr.docstatus == 0:
            frappe.delete_doc("Medication Request", mr.name, ignore_permissions=True)
    except Exception as e:
        frappe.throw("Could not cancel Medication Request " + mr.name + ": " + str(e))

old.flags.ignore_permissions = True
try:
    old.cancel()
except Exception as e:
    frappe.throw("Could not cancel the completed consultation: " + str(e))
new.insert(ignore_permissions=True)

frappe.response["message"] = {"encounter": new.name, "appointment": new.appointment}
