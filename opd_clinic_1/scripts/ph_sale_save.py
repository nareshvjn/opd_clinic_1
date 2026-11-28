# Server Script: ph_sale_save
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_sale_save
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
is_admin = (user == "Administrator")
if not is_admin:
    for r in ["Healthcare Administrator", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            is_admin = True
            break
ok = is_admin
if not ok:
    for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "Purchase User", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            ok = True
            break
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
today_str = str(frappe.utils.today())
today_date = frappe.utils.getdate(today_str)
raw_posting_date = (f.get("posting_date") or "").strip()
amend_invoice = (f.get("amend_invoice") or "").strip()
if amend_invoice and not raw_posting_date:
    frappe.throw("Sale date is required when updating an invoice.")
posting_date = raw_posting_date or today_str

try:
    p_date = frappe.utils.getdate(posting_date)
except Exception:
    frappe.throw("Invalid sale date.")

if p_date < today_date and not is_admin:
    frappe.throw("Only admin accounts can create backdated sales entries. Use today's date.")

if not wh or not lines:
    frappe.throw("Select a store and at least one drug.")

# If amending an invoice, validate and cancel the original submitted invoice now so stock is returned
if amend_invoice:
    if not frappe.db.exists("Sales Invoice", amend_invoice):
        frappe.throw("Original sales invoice not found: " + amend_invoice)
    old_si = frappe.get_doc("Sales Invoice", amend_invoice)
    if old_si.posting_date and frappe.utils.getdate(old_si.posting_date) < today_date and not is_admin:
        frappe.throw("Only admin accounts can edit past-dated sales invoices.")
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
si.ignore_pricing_rule = 1

if patient and frappe.db.exists("Patient", patient):
    si.patient = patient

batch_ids = [ln.get("batch") for ln in lines if ln.get("batch")]
batch_map = {}
if batch_ids:
    b_fields = ["name", "item"]
    try:
        b_meta = frappe.get_meta("Batch")
        for bf in ("units_per_pack", "custom_units_per_pack"):
            if b_meta.has_field(bf):
                b_fields.append(bf)
    except Exception:
        pass
    for br in frappe.get_all("Batch", filters={"name": ["in", batch_ids]}, fields=b_fields, limit=500):
        batch_map[br.name] = br

line_pricing = []
for ln in lines:
    batch_doc = ln.get("batch")
    b = batch_map.get(batch_doc)
    if not b:
        frappe.throw("Batch not found: " + str(batch_doc or ""))
    upp = b.get("units_per_pack") or b.get("custom_units_per_pack")
    if not upp or int(upp) <= 1:
        clean = str(b.item).lower().replace("'", " ").replace("(", " ").replace(")", " ")
        for w in clean.split():
            if w.endswith("s") and len(w) > 1 and w[:-1].isdigit():
                val = int(w[:-1])
                if 1 < val <= 500:
                    upp = val
                    break
    upp = int(upp or 1)
    if upp < 1:
        upp = 1
    qty = num(ln.get("packs")) * upp + num(ln.get("units"))
    rate_incl = num(ln.get("rate"))
    rate_unit = rate_incl / upp
    disc = num(ln.get("disc"))
    if disc < 0:
        disc = 0.0
    elif disc > 100:
        disc = 100.0
    disc_unit = rate_unit * (disc / 100.0)
    net_unit = rate_unit - disc_unit

    pricing = {
        "price_list_rate": rate_unit,
        "discount_percentage": disc,
        "discount_amount": disc_unit,
        "rate": net_unit
    }
    line_pricing.append(pricing)

    item_row = {
        "item_code": b.item,
        "qty": qty,
        "price_list_rate": rate_unit,
        "margin_type": "",
        "margin_rate_or_amount": 0,
        "discount_percentage": disc,
        "discount_amount": disc_unit,
        "rate": net_unit,
        "warehouse": wh,
        "batch_no": b.name,
        "income_account": co.default_income_account,
        "cost_center": co.cost_center
    }

    si.append("items", item_row)

si.run_method("set_missing_values")
# Re-apply explicit MRP and discount after set_missing_values so Item Price or Pricing Rules do not reset rate.
si.ignore_pricing_rule = 1
for idx in range(len(line_pricing)):
    row = si.items[idx]
    lp = line_pricing[idx]
    row.price_list_rate = lp["price_list_rate"]
    row.margin_type = ""
    row.margin_rate_or_amount = 0
    row.discount_percentage = lp["discount_percentage"]
    row.discount_amount = lp["discount_amount"]
    row.rate = lp["rate"]

if not si.debit_to:
    si.debit_to = co.default_receivable_account

if charge_amt > 0:
    charge_acc = co.default_income_account
    if not charge_acc:
        charge_acc = frappe.db.get_value("Account", {"account_type": "Income Account", "company": company, "is_group": 0}, "name")
    if not charge_acc:
        charge_acc = frappe.db.get_value("Account", {"account_name": ["like", "%Income%"], "company": company, "is_group": 0}, "name")
    si.append("taxes", {
        "charge_type": "Actual",
        "account_head": charge_acc,
        "description": charge_name or "Custom Charge",
        "tax_amount": charge_amt,
        "cost_center": co.cost_center
    })

si.run_method("calculate_taxes_and_totals")

# Payment
if mode and mode != "Credit":
    pos_acc = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account")
    if pos_acc:
        si.is_pos = 1
        pay_amt = si.rounded_total or si.grand_total
        si.append("payments", {
            "mode_of_payment": mode,
            "account": pos_acc,
            "amount": pay_amt
        })

si.insert(ignore_permissions=True)
si.submit()
frappe.response["message"] = {
    "invoice": si.name,
    "posting_date": str(si.posting_date),
    "total": si.rounded_total or si.grand_total,
    "paid": bool(si.is_pos)
}
