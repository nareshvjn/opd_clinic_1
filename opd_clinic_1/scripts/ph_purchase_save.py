# Server Script: ph_purchase_save
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_purchase_save
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

def batchify(code):
    if not frappe.db.get_value("Item", code, "has_batch_no"):
        it = frappe.get_doc("Item", code)
        it.has_batch_no = 1
        it.has_expiry_date = 1
        it.create_new_batch = 0
        it.save(ignore_permissions=True)
    return code

def ensure_medication_class():
    if not frappe.db.exists("DocType", "Medication Class"):
        return None
    if not frappe.db.exists("Medication Class", "Drug"):
        try:
            mc = frappe.new_doc("Medication Class")
            mc.medication_class = "Drug"
            mc.insert(ignore_permissions=True, ignore_mandatory=True)
        except Exception:
            pass
    if frappe.db.exists("Medication Class", "Drug"):
        return "Drug"
    return frappe.db.get_value("Medication Class", {}, "name")

def ensure_medication(item_code, item_name):
    if not frappe.db.exists("DocType", "Medication"):
        return
    nm = item_name or item_code
    if frappe.db.exists("Medication", nm) or frappe.db.exists("Medication", {"item": item_code}):
        return
    try:
        med = frappe.new_doc("Medication")
        med.name = nm
        med.flags.name_set = True
        med.medication_name = nm
        med.generic_name = nm
        med.item = item_code
        
        m_class = ensure_medication_class()
        if m_class:
            med.medication_class = m_class
            
        if hasattr(med, "strength"):
            med.strength = 1
            
        med.flags.ignore_mandatory = True
        med.insert(ignore_permissions=True, ignore_mandatory=True)
    except Exception:
        pass

def ensure_item(name):
    if frappe.db.exists("Item", name):
        return batchify(name)
    found = frappe.db.get_value("Item", {"item_name": name}, "name")
    if found:
        return batchify(found)
    
    grp = "Drug"
    if not frappe.db.exists("Item Group", "Drug"):
        grp = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        
    it = frappe.new_doc("Item")
    it.item_code = name
    it.item_name = name
    it.item_group = grp
    it.stock_uom = "Nos"
    it.is_stock_item = 1
    it.has_batch_no = 1
    it.has_expiry_date = 1
    it.create_new_batch = 0
    it.insert(ignore_permissions=True)
    
    ensure_medication(it.name, it.item_name)
    return it.name

def ensure_batch(item, batch_in, expiry, hsn, gst, mrp, rate, net, upp):
    bname = (batch_in or "").strip()
    existing = frappe.db.get_value("Batch", {"batch_id": bname, "item": item}, "name")
    if not existing and frappe.db.exists("Batch", bname):
        if frappe.db.get_value("Batch", bname, "item") == item:
            existing = bname

    meta = frappe.get_meta("Batch")
    def set_batch_fields(doc):
        if expiry:
            doc.expiry_date = expiry
        for fn, val in [("hsn_code", hsn), ("gst_rate", gst), ("mrp", mrp),
                        ("purchase_rate", rate), ("net_rate", net), ("units_per_pack", upp)]:
            if meta.has_field(fn):
                doc.set(fn, val)
            if meta.has_field("custom_" + fn):
                doc.set("custom_" + fn, val)

    if existing:
        b = frappe.get_doc("Batch", existing)
        set_batch_fields(b)
        b.save(ignore_permissions=True)
        return b.name
    else:
        target_name = bname
        if frappe.db.exists("Batch", target_name):
            target_name = bname + "-" + item
            n = 1
            while frappe.db.exists("Batch", target_name):
                target_name = bname + "-" + str(n)
                n += 1
                
        b = frappe.new_doc("Batch")
        b.name = target_name
        b.flags.name_set = True
        b.batch_id = bname
        b.item = item
        set_batch_fields(b)
        b.insert(ignore_permissions=True, ignore_mandatory=True)
        return b.name

f = frappe.form_dict
amend_invoice = (f.get("amend_invoice") or "").strip()
supplier_in = (f.get("supplier") or "").strip()
wh = f.get("warehouse")
lines = json.loads(f.get("lines") or "[]")
if not supplier_in or not wh or not lines:
    frappe.throw("Enter the supplier, the store and at least one line.")

# If amending, verify and cancel the old invoice and linked payment entries FIRST
if amend_invoice:
    if not frappe.db.exists("Purchase Invoice", amend_invoice):
        frappe.throw("Original purchase invoice not found: " + amend_invoice)
    old_pi = frappe.get_doc("Purchase Invoice", amend_invoice)
    pes = frappe.db.sql("""
        select distinct parent from `tabPayment Entry Reference`
        where reference_doctype='Purchase Invoice' and reference_name=%s and docstatus=1
    """, amend_invoice, as_dict=True)
    for p in pes:
        pe_doc = frappe.get_doc("Payment Entry", p.parent)
        if pe_doc.docstatus == 1:
            pe_doc.cancel()
    if old_pi.docstatus == 1:
        old_pi.cancel()

company = frappe.db.get_single_value("Global Defaults", "default_company")
co = frappe.db.get_value("Company", company,
    ["default_payable_account", "stock_received_but_not_billed", "cost_center"], as_dict=True)

supplier = supplier_in
if not frappe.db.exists("Supplier", supplier_in):
    s = frappe.new_doc("Supplier")
    s.supplier_name = supplier_in
    s.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
    s.supplier_type = "Company"
    s.insert(ignore_permissions=True)
    supplier = s.name

payment_status = f.get("payment_status") or "Paid"
due_date = (f.get("due_date") or "").strip()
paid_date = (f.get("paid_date") or "").strip() or frappe.utils.today()
pay_mode = (f.get("payment_mode") or "").strip() or "Cash"
paid_amt = num(f.get("paid_amount"))

pi = frappe.new_doc("Purchase Invoice")
if amend_invoice:
    pi.amended_from = amend_invoice
pi.supplier = supplier
pi.company = company
pi.posting_date = f.get("bill_date") or frappe.utils.today()
pi.bill_no = (f.get("bill_no") or "").strip()
pi.bill_date = f.get("bill_date") or frappe.utils.today()
if payment_status == "Due" and due_date:
    pi.due_date = due_date
pi.update_stock = 1
pi.set_warehouse = wh

tot_gst = 0.0

for ln in lines:
    upp = int(num(ln.get("upp")))
    if upp < 1:
        upp = 1
    gst = num(ln.get("gst"))
    rate = num(ln.get("rate"))
    if ln.get("basis") == "incl":
        rate = rate / (1 + gst / 100)
    net = rate * (1 - num(ln.get("disc")) / 100)
    qty = num(ln.get("packs")) * upp + num(ln.get("units"))
    if qty <= 0:
        frappe.throw("Enter a quantity for " + (ln.get("product") or "every line") + ".")
        
    item = ensure_item((ln.get("product") or "").strip())
    raw_batch = (ln.get("batch") or "").strip()
    exp = (ln.get("expiry") or "").strip()
    hsn = (ln.get("hsn") or "").strip()
    mrp = num(ln.get("mrp"))
    
    batch_name = ensure_batch(item, raw_batch, exp, hsn, gst, mrp, rate, net, upp)
    
    item_row = {
        "item_code": item,
        "qty": qty,
        "rate": net / upp,
        "warehouse": wh,
        "batch_no": batch_name,
        "expense_account": co.stock_received_but_not_billed,
        "cost_center": co.cost_center
    }
    pi.append("items", item_row)
    
    line_subtotal = (qty / upp) * net
    tot_gst += line_subtotal * (gst / 100.0)

if tot_gst > 0:
    cgst_acc = frappe.db.get_value("Account", {
        "account_name": ["in", ["Input Tax CGST", "CGST", "Input CGST"]],
        "company": company,
        "is_group": 0
    }, "name")
    sgst_acc = frappe.db.get_value("Account", {
        "account_name": ["in", ["Input Tax SGST", "SGST", "Input SGST"]],
        "company": company,
        "is_group": 0
    }, "name")
    
    if cgst_acc and sgst_acc:
        half = round(tot_gst / 2.0, 2)
        other_half = round(tot_gst - half, 2)
        pi.append("taxes", {
            "category": "Total",
            "charge_type": "Actual",
            "account_head": cgst_acc,
            "description": "Input CGST",
            "tax_amount": half,
            "cost_center": co.cost_center
        })
        pi.append("taxes", {
            "category": "Total",
            "charge_type": "Actual",
            "account_head": sgst_acc,
            "description": "Input SGST",
            "tax_amount": other_half,
            "cost_center": co.cost_center
        })
    else:
        gst_acc = frappe.db.get_value("Account", {
            "account_name": ["like", "%GST%"],
            "company": company,
            "is_group": 0
        }, "name") or frappe.db.get_value("Account", {
            "account_type": "Tax",
            "company": company,
            "is_group": 0
        }, "name") or co.stock_received_but_not_billed

        pi.append("taxes", {
            "category": "Total",
            "charge_type": "Actual",
            "account_head": gst_acc,
            "description": "Input GST",
            "tax_amount": round(tot_gst, 2),
            "cost_center": co.cost_center
        })

disc_pct = num(f.get("discount_percentage"))
disc_amt = num(f.get("discount_amount"))
if disc_pct > 0:
    pi.apply_discount_on = "Grand Total"
    pi.additional_discount_percentage = disc_pct
elif disc_amt > 0:
    pi.apply_discount_on = "Grand Total"
    pi.discount_amount = disc_amt

courier = num(f.get("courier_charges"))
if courier > 0:
    expense_acc = frappe.db.get_value("Account", {
        "account_name": ["in", ["Freight and Forwarding Charges", "Expenses Included In Valuation", "Courier Charges"]],
        "company": company,
        "is_group": 0
    }, "name") or co.stock_received_but_not_billed

    pi.append("taxes", {
        "category": "Valuation and Total",
        "charge_type": "Actual",
        "account_head": expense_acc,
        "description": "Courier / Freight Charges",
        "tax_amount": courier,
        "cost_center": co.cost_center
    })

pi.run_method("set_missing_values")
if not pi.credit_to:
    pi.credit_to = co.default_payable_account

pi.insert(ignore_permissions=True)
pi.submit()

# Auto-record Payment Entry if Paid
if payment_status == "Paid" and paid_amt > 0:
    paid_from_acc = frappe.db.get_value("Mode of Payment Account", {"parent": pay_mode, "company": company}, "default_account")
    if not paid_from_acc:
        paid_from_acc = frappe.db.get_value("Account", {"account_type": "Cash", "company": company, "is_group": 0}, "name")
        
    if paid_from_acc:
        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Pay"
        pe.company = company
        pe.posting_date = paid_date
        pe.party_type = "Supplier"
        pe.party = supplier
        pe.mode_of_payment = pay_mode
        pe.paid_from = paid_from_acc
        pe.paid_to = pi.credit_to
        pe.paid_amount = paid_amt
        pe.received_amount = paid_amt
        pe.reference_no = pi.bill_no or pi.name
        pe.reference_date = pi.bill_date or paid_date
        pe.append("references", {
            "reference_doctype": "Purchase Invoice",
            "reference_name": pi.name,
            "total_amount": pi.rounded_total or pi.grand_total,
            "outstanding_amount": pi.rounded_total or pi.grand_total,
            "allocated_amount": paid_amt
        })
        pe.insert(ignore_permissions=True)
        pe.submit()

frappe.response["message"] = {"invoice": pi.name, "total": pi.rounded_total or pi.grand_total}
