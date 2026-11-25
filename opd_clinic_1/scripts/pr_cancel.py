# Server Script: pr_cancel
# type: API
# doctype: -
# event: Before Insert
# api_method: pr_cancel
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
    frappe.throw("You don't have access to this action.")

invoice = (frappe.form_dict.get("invoice") or "").strip()
if not invoice:
    frappe.throw("Invoice name required.")

if not frappe.db.exists("Purchase Invoice", invoice):
    frappe.throw("Invoice not found.")

doc = frappe.get_doc("Purchase Invoice", invoice)
if not doc.is_return:
    frappe.throw("Only return invoices can be cancelled here.")

if doc.docstatus != 1:
    frappe.throw("Only submitted return invoices can be cancelled.")

today_date = frappe.utils.getdate(frappe.utils.today())
if doc.posting_date and frappe.utils.getdate(doc.posting_date) < today_date and not is_admin:
    frappe.throw("Only admin accounts can cancel past-dated purchase return notes.")

original = doc.return_against
doc.cancel()

frappe.response["message"] = {
    "status": "cancelled",
    "invoice": invoice,
    "original": original
}
