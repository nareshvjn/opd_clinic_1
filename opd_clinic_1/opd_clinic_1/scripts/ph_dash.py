# Server Script: ph_dash
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_dash
# allow_guest: 0
# frequency: All
# disabled: 0

ok = False
for r in ["Stock Manager", "Accounts Manager", "Accounts User", "System Manager"]:
    if frappe.db.exists("Has Role", {"parent": frappe.session.user, "role": r}):
        ok = True
if not ok:
    frappe.throw("You don't have access to the dashboard.")

def one(q, vals=None):
    rows = frappe.db.sql(q, vals or ())
    if rows and rows[0] and rows[0][0] is not None:
        return float(rows[0][0])
    return 0.0

f = frappe.form_dict
today = frappe.utils.nowdate()
d1 = (f.get("from") or today).strip()
d2 = (f.get("to") or today).strip()
p = (d1, d2)
soon = frappe.utils.add_days(today, 90)

inv_total = "sum(if(ifnull(rounded_total, 0) = 0, grand_total, rounded_total))"

sales = one("select " + inv_total + " from `tabSales Invoice` where docstatus = 1 and posting_date between %s and %s", p)
bills = one("select count(*) from `tabSales Invoice` where docstatus = 1 and is_return = 0 and posting_date between %s and %s", p)
purchase = one("select " + inv_total + " from `tabPurchase Invoice` where docstatus = 1 and posting_date between %s and %s", p)

# sales without GST (the sale rate includes GST; the GST rate is kept on the batch)
sales_ex = one("""select sum(sii.amount / (1 + ifnull(b.gst_rate, 0) / 100))
    from `tabSales Invoice Item` sii
    join `tabSales Invoice` si on si.name = sii.parent
    left join `tabBatch` b on b.name = sii.batch_no
    where si.docstatus = 1 and si.posting_date between %s and %s""", p)
# cost of goods sold, from the stock ledger
cogs = -one("""select sum(stock_value_difference) from `tabStock Ledger Entry`
    where voucher_type = 'Sales Invoice' and is_cancelled = 0 and posting_date between %s and %s""", p)
expenses = one("""select sum(gl.debit - gl.credit) from `tabGL Entry` gl
    join `tabAccount` a on a.name = gl.account
    where gl.is_cancelled = 0 and a.root_type = 'Expense'
    and ifnull(a.account_type, '') not in ('Cost of Goods Sold', 'Stock Adjustment', 'Round Off')
    and gl.posting_date between %s and %s""", p)

stock_value = one("select sum(stock_value) from `tabBin`")
batch_val = "sum(batch_qty / ifnull(nullif(units_per_pack, 0), 1) * ifnull(net_rate, 0))"
expired = one("select " + batch_val + " from `tabBatch` where disabled = 0 and batch_qty > 0 and expiry_date < %s", (today,))
expiring = one("select " + batch_val + " from `tabBatch` where disabled = 0 and batch_qty > 0 and expiry_date between %s and %s", (today, soon))

cash_bank = one("""select sum(gl.debit - gl.credit) from `tabGL Entry` gl
    join `tabAccount` a on a.name = gl.account
    where gl.is_cancelled = 0 and a.is_group = 0 and a.account_type in ('Cash', 'Bank')""")
receive = one("select sum(outstanding_amount) from `tabSales Invoice` where docstatus = 1")
pay = one("select sum(outstanding_amount) from `tabPurchase Invoice` where docstatus = 1")
if receive < 0:
    receive = 0
if pay < 0:
    pay = 0

company = frappe.db.get_single_value("Global Defaults", "default_company") or ""
frappe.response["message"] = {
    "company": company, "from": d1, "to": d2,
    "stock_value": stock_value, "expired": expired, "expiring": expiring,
    "sales": sales, "bills": bills, "purchase": purchase,
    "profit": sales_ex - cogs - expenses, "gross_profit": sales_ex - cogs, "expenses": expenses,
    "cash_bank": cash_bank, "receive": receive, "pay": pay}
    
