# Server Script: sr_save
# type: API
# doctype: -
# event: Before Insert
# api_method: sr_save
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Sales User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to this page.")

def num(v):
    try:
        return float(v or 0)
    except:
        return 0.0

f = frappe.form_dict
invoice = (f.get("invoice") or "").strip()
lines = json.loads(f.get("lines") or "[]")
reason = (f.get("reason") or "Wrong Medicine").strip()
mode = (f.get("mode") or "").strip()

if not invoice or not lines:
    frappe.throw("Invoice and at least one return line are required.")

if not frappe.db.exists("Sales Invoice", invoice):
    frappe.throw("Invoice not found.")

si = frappe.get_doc("Sales Invoice", invoice)
if si.docstatus != 1:
    frappe.throw("Invoice is not submitted.")

company = si.company
co = frappe.db.get_value("Company", company,
    ["default_receivable_account", "default_income_account", "cost_center"], as_dict=True)

ret = frappe.new_doc("Sales Invoice")
ret.customer = si.customer
ret.company = company
ret.posting_date = frappe.utils.today()
ret.set_posting_time = 1
ret.update_stock = 1
ret.is_return = 1
ret.return_against = invoice
if si.patient:
    ret.patient = si.patient

for ln in lines:
    item_code = ln.get("item_code")
    batch_no = ln.get("batch_no") or ""
    qty = num(ln.get("qty"))
    rate = num(ln.get("rate"))
    wh = ln.get("warehouse") or si.set_warehouse or ""

    if qty <= 0:
        continue

    item_row = {
        "item_code": item_code,
        "qty": -qty,
        "rate": rate,
        "warehouse": wh,
        "income_account": co.default_income_account,
        "cost_center": co.cost_center,
        "description": reason
    }
    if batch_no:
        item_row["batch_no"] = batch_no

    ret.append("items", item_row)

if not ret.items:
    frappe.throw("No valid return lines.")

if mode and mode != "Credit":
    pos_acc = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account")
    if pos_acc:
        ret.is_pos = 1
        ret.append("payments", {
            "mode_of_payment": mode,
            "account": pos_acc,
            "amount": 0
        })

ret.run_method("set_missing_values")
if not ret.debit_to:
    ret.debit_to = co.default_receivable_account

if ret.is_pos and ret.payments:
    ret.payments[0].amount = ret.rounded_total or ret.grand_total

ret.insert(ignore_permissions=True)
ret.submit()

frappe.response["message"] = {
    "return_invoice": ret.name,
    "total": abs(ret.rounded_total or ret.grand_total)
}
