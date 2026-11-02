# Server Script: ph_sale_save
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_sale_save
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the pharmacy.")

def num(v):
    try:
        return float(v or 0)
    except:
        return 0.0

f = frappe.form_dict
wh = f.get("warehouse")
lines = json.loads(f.get("lines") or "[]")
customer = (f.get("customer") or "").strip()
patient = (f.get("patient") or "").strip()
mode = (f.get("mode") or "").strip()
charge_name = (f.get("charge_name") or "").strip()
charge_amt = num(f.get("charge"))
posting_date = (f.get("posting_date") or "").strip() or frappe.utils.today()
amend_invoice = (f.get("amend_invoice") or "").strip()

if not wh or not lines:
    frappe.throw("Select a store and at least one drug.")

# If amending an invoice, cancel the original submitted invoice now so stock is returned
if amend_invoice:
    if not frappe.db.exists("Sales Invoice", amend_invoice):
        frappe.throw("Original sales invoice not found: " + amend_invoice)
    old_si = frappe.get_doc("Sales Invoice", amend_invoice)
    pes = frappe.db.sql("""
        select distinct parent from `tabPayment Entry Reference`
        where reference_doctype='Sales Invoice' and reference_name=%s and docstatus=1
    """, amend_invoice, as_dict=True)
    for p in pes:
        pe_doc = frappe.get_doc("Payment Entry", p.parent)
        if pe_doc.docstatus == 1:
            pe_doc.cancel()
    if old_si.docstatus == 1:
        old_si.cancel()

company = frappe.db.get_single_value("Global Defaults", "default_company")
co = frappe.db.get_value("Company", company,
    ["default_receivable_account", "default_income_account", "cost_center"], as_dict=True)

# Ensure Customer
if not customer:
    customer = frappe.db.get_single_value("Selling Settings", "customer_group") or "Walk-in"
    if not frappe.db.exists("Customer", customer):
        c = frappe.new_doc("Customer")
        c.customer_name = customer
        c.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
        c.customer_type = "Individual"
        c.insert(ignore_permissions=True)
        customer = c.name
elif not frappe.db.exists("Customer", customer):
    c = frappe.new_doc("Customer")
    c.customer_name = customer
    c.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
    c.customer_type = "Individual"
    c.insert(ignore_permissions=True)
    customer = c.name

si = frappe.new_doc("Sales Invoice")
if amend_invoice:
    si.amended_from = amend_invoice

si.customer = customer
si.company = company
si.posting_date = posting_date
si.set_posting_time = 1
si.update_stock = 1
si.set_warehouse = wh

if patient and frappe.db.exists("Patient", patient):
    si.patient = patient

for ln in lines:
    batch_doc = ln.get("batch")
    b = frappe.get_doc("Batch", batch_doc)
    upp = b.units_per_pack or 1
    qty = num(ln.get("packs")) * upp + num(ln.get("units"))
    rate_incl = num(ln.get("rate"))
    gst = num(b.gst_rate)
    rate_excl = rate_incl / (1 + gst / 100.0) if gst else rate_incl
    rate_unit = rate_excl / upp

    item_row = {
        "item_code": b.item,
        "qty": qty,
        "rate": rate_unit,
        "warehouse": wh,
        "batch_no": b.name,
        "income_account": co.default_income_account,
        "cost_center": co.cost_center
    }
    disc = num(ln.get("disc"))
    if disc > 0:
        item_row["discount_percentage"] = disc

    si.append("items", item_row)

if charge_amt > 0:
    charge_acc = co.default_income_account
    si.append("taxes", {
        "category": "Total",
        "charge_type": "Actual",
        "account_head": charge_acc,
        "description": charge_name or "Custom Charge",
        "tax_amount": charge_amt,
        "cost_center": co.cost_center
    })

# Payment
if mode and mode != "Credit":
    pos_acc = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account")
    if pos_acc:
        si.is_pos = 1
        si.append("payments", {
            "mode_of_payment": mode,
            "account": pos_acc,
            "amount": 0  # set_missing_values fills grand_total
        })

si.run_method("set_missing_values")
if not si.debit_to:
    si.debit_to = co.default_receivable_account

if si.is_pos and si.payments:
    si.payments[0].amount = si.rounded_total or si.grand_total

si.insert(ignore_permissions=True)
si.submit()
frappe.response["message"] = {
    "invoice": si.name,
    "total": si.rounded_total or si.grand_total,
    "paid": bool(si.is_pos)
}
