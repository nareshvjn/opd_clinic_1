# Server Script: pr_save
# type: API
# doctype: -
# event: Before Insert
# api_method: pr_save
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
    for r in ["Stock User", "Stock Manager", "Accounts User", "Purchase User", "System Manager"]:
        if frappe.db.exists("Has Role", {"parent": user, "role": r}):
            ok = True
            break
if not ok:
    frappe.throw("You don't have access to this page.")

def num(v):
    try:
        return float(v or 0)
    except:
        return 0.0

f = frappe.form_dict
invoice      = (f.get("invoice") or "").strip()
amend_return = (f.get("amend_return") or "").strip()
lines        = json.loads(f.get("lines") or "[]")
reason       = (f.get("reason") or "Wrong Item").strip()

today_str = str(frappe.utils.today())
today_date = frappe.utils.getdate(today_str)
posting_date = (f.get("posting_date") or "").strip() or today_str
try:
    p_date = frappe.utils.getdate(posting_date)
except Exception:
    frappe.throw("Invalid return date.")

if p_date < today_date and not is_admin:
    frappe.throw("Only admin accounts can create backdated purchase returns. Use today's date.")

if amend_return:
    if not frappe.db.exists("Purchase Invoice", amend_return):
        frappe.throw("Original return note not found: " + amend_return)
    old_ret = frappe.get_doc("Purchase Invoice", amend_return)
    if old_ret.posting_date and frappe.utils.getdate(old_ret.posting_date) < today_date and not is_admin:
        frappe.throw("Only admin accounts can modify past-dated purchase return notes.")
    # Cancel linked payment entries if any to prevent TimestampMismatchError
    pes = frappe.db.sql("""
        select distinct parent from `tabPayment Entry Reference`
        where reference_doctype='Purchase Invoice' and reference_name=%s and docstatus=1
    """, amend_return, as_dict=True)
    for p in pes:
        pe_doc = frappe.get_doc("Payment Entry", p.parent)
        if pe_doc.docstatus == 1:
            pe_doc.cancel()
    if not invoice:
        invoice = old_ret.return_against
    if old_ret.docstatus == 1:
        old_ret.cancel()

if not invoice or not lines:
    frappe.throw("Invoice and at least one return line are required.")

if not frappe.db.exists("Purchase Invoice", invoice):
    frappe.throw("Purchase invoice not found: " + invoice)

pi = frappe.get_doc("Purchase Invoice", invoice)
if pi.docstatus != 1:
    frappe.throw("Invoice is not submitted.")

company = pi.company
co = frappe.db.get_value("Company", company,
    ["default_payable_account", "stock_received_but_not_billed", "cost_center"], as_dict=True)

ret = frappe.new_doc("Purchase Invoice")
ret.supplier = pi.supplier
ret.company = company
ret.posting_date = posting_date
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
    "total": abs(ret.rounded_total or ret.grand_total),
    "amended": bool(amend_return)
}
