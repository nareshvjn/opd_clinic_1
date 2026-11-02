# Server Script: desk_invoice
# type: API
# doctype: -
# event: Before Insert
# api_method: desk_invoice
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = False
if frappe.db.exists("Has Role", {"parent": user, "role": "Healthcare Administrator"}):
    is_admin = True
if frappe.db.exists("Has Role", {"parent": user, "role": "System Manager"}):
    is_admin = True
is_doctor = bool(frappe.db.exists("Has Role", {"parent": user, "role": "Physician"}))
if not (is_admin or is_doctor):
    frappe.throw("You don't have access to the doctor desk.")

# The Item billed for a consultation when the doctor's record names none. Change to your Item ID.
CONSULT_ITEM = "CONSULT-GEN"

def num(v):
    try:
        return float(v or 0)
    except:
        return 0.0

def find_invoice(appt):
    try:
        for r in frappe.get_all("Sales Invoice Item",
                filters={"reference_dt": "Patient Appointment", "reference_dn": appt},
                fields=["parent"], limit=5):
            if frappe.db.get_value("Sales Invoice", r.parent, "docstatus") < 2:
                return r.parent
    except:
        pass
    found = frappe.get_all("Sales Invoice",
        filters={"remarks": ["like", "%Consultation: " + appt + "%"], "docstatus": ["<", 2]},
        fields=["name"], limit=1)
    if found:
        return found[0].name
    return ""

name = frappe.form_dict.get("appointment")
mode = (frappe.form_dict.get("mode") or "").strip()
if not name:
    frappe.throw("Choose an appointment.")

appt = frappe.get_doc("Patient Appointment", name)
if not is_admin:
    mine = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name")
    if not mine or appt.practitioner != mine:
        frappe.throw("You can only bill your own appointments.")
if appt.status not in ["Closed", "Checked Out"]:
    frappe.throw("Complete the consultation before billing it.")

existing = find_invoice(appt.name)
if existing:
    frappe.response["message"] = {"invoice": existing, "created": False, "paid": False, "note": ""}
else:
    prac = frappe.get_doc("Healthcare Practitioner", appt.practitioner)
    item = prac.get("op_consulting_charge_item")
    if not item or not frappe.db.exists("Item", item):
        item = CONSULT_ITEM
    if not frappe.db.exists("Item", item):
        frappe.throw("Item " + item + " was not found. Create it, or change CONSULT_ITEM in the desk_invoice script.")
    rate = num(prac.get("op_consulting_charge"))
    if rate <= 0:
        rate = num(frappe.db.get_value("Item", item, "standard_rate"))
    if rate <= 0:
        frappe.throw("No consultation charge found. Set OP Consulting Charge on the doctor's record, or the Standard Selling Rate of item " + item + ".")

    company = frappe.db.get_single_value("Global Defaults", "default_company")
    co = frappe.db.get_value("Company", company,
        ["default_receivable_account", "default_income_account", "cost_center", "default_currency"], as_dict=True)

    cust = ""
    try:
        cust = frappe.db.get_value("Patient", appt.patient, "customer") or ""
    except:
        cust = ""
    if not cust:
        cust = "Walk-in Customer"
        if not frappe.db.exists("Customer", cust):
            c = frappe.new_doc("Customer")
            c.customer_name = cust
            c.customer_type = "Individual"
            c.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
            c.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
            c.insert(ignore_permissions=True)
            cust = c.name

    uom = frappe.db.get_value("Item", item, "stock_uom")
    si = frappe.new_doc("Sales Invoice")
    si.customer = cust
    si.company = company
    si.posting_date = frappe.utils.today()
    si.update_stock = 0
    si.ignore_pricing_rule = 1
    si.currency = co.default_currency
    si.selling_price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
    si.price_list_currency = co.default_currency
    si.conversion_rate = 1
    si.plc_conversion_rate = 1
    si.remarks = "Consultation: " + appt.name + " " + (appt.patient_name or "")
    si.patient = appt.patient
    si.append("items", {"item_code": item, "qty": 1, "uom": uom, "stock_uom": uom, "conversion_factor": 1,
        "price_list_rate": rate, "rate": rate,
        "description": "Consultation with " + (prac.get("practitioner_name") or appt.practitioner),
        "income_account": co.default_income_account, "cost_center": co.cost_center})
    si.run_method("set_missing_values")
    if not si.debit_to:
        si.debit_to = co.default_receivable_account
    si.run_method("calculate_taxes_and_totals")
    si.insert(ignore_permissions=True)
    si.submit()

    paid = False
    note = ""
    if mode and mode != "Credit":
        try:
            pe = frappe.call("erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
                dt="Sales Invoice", dn=si.name)
            pe.mode_of_payment = mode
            pe.reference_no = si.name
            pe.reference_date = frappe.utils.today()
            pe.insert(ignore_permissions=True)
            pe.submit()
            paid = True
        except:
            note = "The invoice is saved, but the payment could not be recorded. Record it from the invoice in Desk."
    frappe.response["message"] = {"invoice": si.name, "created": True, "paid": paid, "note": note}
