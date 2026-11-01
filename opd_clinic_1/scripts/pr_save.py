# Server Script: pr_save
# type: API
# doctype: -
# event: Before Insert
# api_method: pr_save
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock User", "Stock Manager", "Accounts User", "Purchase User", "System Manager"]:
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
lines   = json.loads(f.get("lines") or "[]")
reason  = (f.get("reason") or "Wrong Item").strip()

if not invoice or not lines:
    frappe.throw("Invoice and at least one return line are required.")

if not frappe.db.exists("Purchase Invoice", invoice):
    frappe.throw("Purchase invoice not found.")

pi = frappe.get_doc("Purchase Invoice", invoice)
if pi.docstatus != 1:
    frappe.throw("Invoice is not submitted.")

company = pi.company
co = frappe.db.get_value("Company", company,
    ["default_payable_account", "stock_received_but_not_billed", "cost_center"], as_dict=True)

ret = frappe.new_doc("Purchase Invoice")
ret.supplier = pi.supplier
ret.company = company
ret.posting_date = frappe.utils.today()
ret.set_posting_time = 1
ret.update_stock = 1
ret.is_return = 1
ret.return_against = invoice

for ln in lines:
    item_code = ln.get("item_code")
    batch_no  = ln.get("batch_no") or ""
    qty       = num(ln.get("qty"))
    rate      = num(ln.get("rate"))
    wh        = ln.get("warehouse") or pi.set_warehouse or ""

    if qty <= 0:
        continue

    item_row = {
        "item_code": item_code,
        "qty": -qty,
        "rate": rate,
        "warehouse": wh,
        "expense_account": co.stock_received_but_not_billed,
        "cost_center": co.cost_center,
        "description": reason
    }
    if batch_no:
        item_row["batch_no"] = batch_no

    ret.append("items", item_row)

if not ret.items:
    frappe.throw("No valid return lines.")

ret.run_method("set_missing_values")
if not ret.credit_to:
    ret.credit_to = co.default_payable_account

ret.insert(ignore_permissions=True)
ret.submit()

frappe.response["message"] = {
    "return_invoice": ret.name,
    "total": abs(ret.rounded_total or ret.grand_total)
}
