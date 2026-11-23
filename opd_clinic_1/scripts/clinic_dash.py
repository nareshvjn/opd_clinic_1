# Server Script: clinic_dash
# type: API
# doctype: -
# event: Before Insert
# api_method: clinic_dash
# allow_guest: 0
# frequency: All
# disabled: 0

user = frappe.session.user
ok = False
allowed_roles = [
    "Healthcare Administrator", "System Manager", "Physician",
    "Stock Manager", "Stock User", "Accounts Manager", "Accounts User", "Sales User"
]
for r in allowed_roles:
    if frappe.db.exists("Has Role", {"parent": user, "role": r}):
        ok = True
        break
if not ok:
    frappe.throw("You do not have permission to view the clinic dashboard.")

def one(q, vals=None):
    try:
        rows = frappe.db.sql(q, vals or ())
        if rows and rows[0] and rows[0][0] is not None:
            return float(rows[0][0])
    except Exception:
        pass
    return 0.0

def count_query(q, vals=None):
    try:
        rows = frappe.db.sql(q, vals or ())
        if rows and rows[0] and rows[0][0] is not None:
            return int(rows[0][0])
    except Exception:
        pass
    return 0

f = frappe.form_dict
today = frappe.utils.today()
d1 = (f.get("from") or today).strip()
d2 = (f.get("to") or today).strip()
p = (d1, d2)

# 1. Patient Metrics
total_patients = count_query("""
    select count(*) from `tabPatient`
    where (status is null or status = '' or status != 'Disabled')
""")

new_patients = count_query("""
    select count(*) from `tabPatient`
    where date(creation) between %s and %s
      and (status is null or status = '' or status != 'Disabled')
""", p)

total_appts = count_query("""
    select count(*) from `tabPatient Appointment`
    where appointment_date between %s and %s
      and status != 'Cancelled'
""", p)

completed_appts = count_query("""
    select count(*) from `tabPatient Appointment`
    where appointment_date between %s and %s
      and status in ('Closed', 'Checked Out')
""", p)

# 2. Consultation Revenue
inv_val = "sum(if(ifnull(si.rounded_total, 0) = 0, si.grand_total, si.rounded_total))"

consult_total = one("""
    select """ + inv_val + """
    from `tabSales Invoice` si
    where si.docstatus = 1 and si.is_return = 0
      and si.posting_date between %s and %s
      and (
          si.update_stock = 0
          or exists (
              select 1 from `tabSales Invoice Item` sii
              where sii.parent = si.name
                and (sii.reference_dt = 'Patient Appointment' or sii.item_code like 'CONSULT%')
          )
      )
""", p)

consult_count = count_query("""
    select count(*)
    from `tabSales Invoice` si
    where si.docstatus = 1 and si.is_return = 0
      and si.posting_date between %s and %s
      and (
          si.update_stock = 0
          or exists (
              select 1 from `tabSales Invoice Item` sii
              where sii.parent = si.name
                and (sii.reference_dt = 'Patient Appointment' or sii.item_code like 'CONSULT%')
          )
      )
""", p)

# 3. Pharmacy Sales
pharmacy_sales_gross = one("""
    select """ + inv_val + """
    from `tabSales Invoice` si
    where si.docstatus = 1 and si.is_return = 0
      and si.posting_date between %s and %s
      and si.update_stock = 1
""", p)

pharmacy_sales_count = count_query("""
    select count(*)
    from `tabSales Invoice` si
    where si.docstatus = 1 and si.is_return = 0
      and si.posting_date between %s and %s
      and si.update_stock = 1
""", p)

pharmacy_returns = one("""
    select """ + inv_val + """
    from `tabSales Invoice` si
    where si.docstatus = 1 and si.is_return = 1
      and si.posting_date between %s and %s
""", p)

pharmacy_sales_net = max(0.0, pharmacy_sales_gross - pharmacy_returns)

# Pharmacy sales without GST
pharmacy_sales_excl_gst = one("""
    select sum(sii.amount / (1 + ifnull(b.gst_rate, 0) / 100))
    from `tabSales Invoice Item` sii
    join `tabSales Invoice` si on si.name = sii.parent
    left join `tabBatch` b on b.name = sii.batch_no
    where si.docstatus = 1 and si.is_return = 0 and si.update_stock = 1
      and si.posting_date between %s and %s
""", p)

# 4. Purchases
purchases_gross = one("""
    select sum(if(ifnull(pi.rounded_total, 0) = 0, pi.grand_total, pi.rounded_total))
    from `tabPurchase Invoice` pi
    where pi.docstatus = 1 and pi.is_return = 0
      and pi.posting_date between %s and %s
""", p)

purchases_count = count_query("""
    select count(*)
    from `tabPurchase Invoice` pi
    where pi.docstatus = 1 and pi.is_return = 0
      and pi.posting_date between %s and %s
""", p)

purchases_returns = one("""
    select sum(if(ifnull(pi.rounded_total, 0) = 0, pi.grand_total, pi.rounded_total))
    from `tabPurchase Invoice` pi
    where pi.docstatus = 1 and pi.is_return = 1
      and pi.posting_date between %s and %s
""", p)

purchases_net = max(0.0, purchases_gross - purchases_returns)

# 5. Cost of Goods Sold (COGS) & Expenses
cogs = -one("""
    select sum(stock_value_difference)
    from `tabStock Ledger Entry`
    where voucher_type = 'Sales Invoice' and is_cancelled = 0
      and posting_date between %s and %s
""", p)

# If stock ledger has no valuation records, estimate COGS based on batch net rate or 70% of sales
if cogs <= 0 and pharmacy_sales_excl_gst > 0:
    batch_cogs = one("""
        select sum(sii.qty * ifnull(b.purchase_rate / ifnull(nullif(b.units_per_pack, 0), 1), 0))
        from `tabSales Invoice Item` sii
        join `tabSales Invoice` si on si.name = sii.parent
        left join `tabBatch` b on b.name = sii.batch_no
        where si.docstatus = 1 and si.is_return = 0 and si.update_stock = 1
          and si.posting_date between %s and %s
    """, p)
    cogs = batch_cogs if batch_cogs > 0 else (pharmacy_sales_excl_gst * 0.70)

expenses = one("""
    select sum(gl.debit - gl.credit)
    from `tabGL Entry` gl
    join `tabAccount` a on a.name = gl.account
    where gl.is_cancelled = 0 and a.root_type = 'Expense'
      and ifnull(a.account_type, '') not in ('Cost of Goods Sold', 'Stock Adjustment', 'Round Off')
      and gl.posting_date between %s and %s
""", p)

# 6. Profit Calculations
pharmacy_profit = max(0.0, pharmacy_sales_excl_gst - cogs)
pharmacy_margin_pct = (pharmacy_profit / pharmacy_sales_excl_gst * 100.0) if pharmacy_sales_excl_gst > 0 else 0.0

total_revenue = consult_total + pharmacy_sales_net
gross_profit = consult_total + pharmacy_profit
gross_profit_pct = (gross_profit / total_revenue * 100.0) if total_revenue > 0 else 0.0

net_profit = gross_profit - expenses
net_profit_pct = (net_profit / total_revenue * 100.0) if total_revenue > 0 else 0.0

# Doctor Breakdown
doctors = frappe.db.sql("""
    select pa.practitioner_name, count(pa.name) as appts
    from `tabPatient Appointment` pa
    where pa.appointment_date between %(d1)s and %(d2)s
      and pa.status != 'Cancelled'
    group by pa.practitioner_name
    order by appts desc
    limit 10
""", {"d1": d1, "d2": d2}, as_dict=True)

company = frappe.db.get_single_value("Global Defaults", "default_company") or "Jeevan Healthcare and Medicals"

frappe.response["message"] = {
    "company": company,
    "from": d1,
    "to": d2,
    "patients": {
        "total": total_patients,
        "new": new_patients,
        "appointments": total_appts,
        "completed": completed_appts
    },
    "consultation": {
        "total": round(consult_total, 2),
        "count": consult_count
    },
    "pharmacy": {
        "gross_sales": round(pharmacy_sales_gross, 2),
        "returns": round(pharmacy_returns, 2),
        "net_sales": round(pharmacy_sales_net, 2),
        "bills_count": pharmacy_sales_count,
        "excl_gst": round(pharmacy_sales_excl_gst, 2),
        "cogs": round(cogs, 2),
        "profit": round(pharmacy_profit, 2),
        "margin_pct": round(pharmacy_margin_pct, 1)
    },
    "purchases": {
        "gross": round(purchases_gross, 2),
        "returns": round(purchases_returns, 2),
        "net": round(purchases_net, 2),
        "bills_count": purchases_count
    },
    "profit": {
        "total_revenue": round(total_revenue, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(gross_profit_pct, 1),
        "expenses": round(expenses, 2),
        "net_profit": round(net_profit, 2),
        "net_margin_pct": round(net_profit_pct, 1)
    },
    "doctors": doctors or []
}
