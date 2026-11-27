# Server Script: ph_batch_detail
# type: API
# doctype: -
# event: Before Insert
# api_method: ph_batch_detail
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
    except Exception:
        return 0.0


def parse_upp_from_name(name):
    if not name:
        return 1
    clean = str(name).lower().replace("'", " ").replace("(", " ").replace(")", " ").replace("/", " ")
    words = clean.split()
    for w in words:
        if w.endswith("s") and len(w) > 1 and w[:-1].isdigit():
            val = int(w[:-1])
            if 1 < val <= 500:
                return val
    for i in range(len(words) - 1):
        if (
            words[i].isdigit()
            and words[i + 1] in ("tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules", "strip", "strips")
            and int(words[i]) <= 500
        ):
            return int(words[i])
    return 1


def wh_qty(b, w):
    try:
        r = frappe.call("erpnext.stock.doctype.batch.batch.get_batch_qty", batch_no=b, warehouse=w)
        if isinstance(r, (int, float)):
            return float(r)
        if isinstance(r, list):
            return sum(float(x.get("qty") or 0) for x in r)
    except Exception:
        pass
    try:
        res = frappe.db.sql(
            """select sum(actual_qty) from `tabStock Ledger Entry`
            where batch_no = %s and warehouse = %s and is_cancelled = 0""",
            (b, w),
        )
        if res and res[0] and res[0][0] is not None:
            return float(res[0][0])
    except Exception:
        pass
    return None


def all_wh_qty(b):
    wh_map = {}
    try:
        r = frappe.call("erpnext.stock.doctype.batch.batch.get_batch_qty", batch_no=b)
        if isinstance(r, list):
            for x in r:
                wname = x.get("warehouse")
                qval = num(x.get("qty"))
                if wname and qval != 0:
                    wh_map[wname] = wh_map.get(wname, 0.0) + qval
    except Exception:
        pass
    if not wh_map:
        try:
            rows = frappe.db.sql(
                """select warehouse, sum(actual_qty) as qty
                from `tabStock Ledger Entry`
                where batch_no = %s and is_cancelled = 0
                group by warehouse""",
                (b,),
                as_dict=True,
            )
            for row in rows:
                wname = row.get("warehouse")
                qval = num(row.get("qty"))
                if wname and qval != 0:
                    wh_map[wname] = qval
        except Exception:
            pass
    return wh_map


f = frappe.form_dict
bname = (f.get("batch") or "").strip()
wh = (f.get("warehouse") or "").strip()
from_date = (f.get("from_date") or "").strip()
to_date = (f.get("to_date") or "").strip()

if not bname or not frappe.db.exists("Batch", bname):
    frappe.throw("Batch not found: " + bname)

b = frappe.get_doc("Batch", bname)
bmeta = frappe.get_meta("Batch")


def bval(fn):
    v = b.get(fn) if bmeta.has_field(fn) else None
    if (v is None or v == "" or v == 0) and bmeta.has_field("custom_" + fn):
        v = b.get("custom_" + fn)
    return v


item_code = (b.get("item") or b.get("item_code") or "").strip()
item_name = (bval("item_name") or "").strip()
if not item_name and item_code:
    item_name = frappe.db.get_value("Item", item_code, "item_name") or item_code
if not item_name:
    item_name = bname

upp = int(num(bval("units_per_pack")) or 1)
if upp <= 1:
    name_upp = parse_upp_from_name(item_name or item_code)
    if name_upp > 1:
        upp = name_upp
if upp < 1:
    upp = 1

pur = num(bval("purchase_rate"))
net = num(bval("net_rate"))
if net <= 0 and pur > 0:
    net = pur
gst = num(bval("gst_rate"))
hsn = str(bval("hsn_code") or "")
mrp = num(bval("mrp"))
if mrp <= 0 and pur > 0:
    mrp = round(pur * (1.0 + gst / 100.0), 2)
exp = str(b.get("expiry_date") or "")
batch_id = str(b.get("batch_id") or bname)

wh_map = all_wh_qty(bname)
total_qty = sum(q for q in wh_map.values() if q > 0)
qty = wh_qty(bname, wh) if wh else total_qty
if qty is None:
    qty = wh_map.get(wh, 0.0) if wh else num(b.get("batch_qty"))
if qty < 0:
    qty = 0.0

wh_list = []
for wname in sorted(wh_map.keys()):
    qval = wh_map[wname]
    if qval > 0 or wname == wh:
        wh_list.append({"warehouse": wname, "qty": qval if qval > 0 else 0.0})
if wh and wh not in wh_map:
    wh_list.insert(0, {"warehouse": wh, "qty": qty})

mrp_excl = (mrp / (1.0 + gst / 100.0)) if gst > 0 else mrp
batch_margin = ((mrp_excl - net) / mrp_excl * 100.0) if (mrp_excl > 0 and net > 0) else 0.0
stock_value = (qty / upp) * net if (qty > 0 and net > 0) else 0.0

batch_info = {
    "batch": bname,
    "batch_id": batch_id,
    "item": item_code,
    "name": item_name,
    "expiry": exp,
    "qty": qty,
    "total_qty": total_qty,
    "warehouse": wh,
    "warehouses": wh_list,
    "mrp": mrp,
    "purchase_rate": pur,
    "net_rate": net,
    "gst": gst,
    "hsn": hsn,
    "upp": upp,
    "margin_pct": round(batch_margin, 2),
    "stock_value": round(stock_value, 2),
    "disabled": int(b.get("disabled") or 0),
}

# ==========================
# PURCHASE DETAILS FOR BATCH
# ==========================
has_pi_sbb = frappe.get_meta("Purchase Invoice Item").has_field("serial_and_batch_bundle")
has_sbe = frappe.db.exists("DocType", "Serial and Batch Entry")
pi_meta = frappe.get_meta("Purchase Invoice")
has_pi_gstin = pi_meta.has_field("supplier_gstin")
sup_meta = frappe.get_meta("Supplier")
sup_gstin_field = "gstin" if sup_meta.has_field("gstin") else ("tax_id" if sup_meta.has_field("tax_id") else "")

pi_date_clause = ""
pi_params = {"batch": bname}
if from_date:
    pi_date_clause += " AND ifnull(pi.bill_date, pi.posting_date) >= %(from_date)s"
    pi_params["from_date"] = from_date
if to_date:
    pi_date_clause += " AND ifnull(pi.bill_date, pi.posting_date) <= %(to_date)s"
    pi_params["to_date"] = to_date

pi_gstin_col = "pi.supplier_gstin" if has_pi_gstin else "'' AS supplier_gstin"

pi_rows = frappe.db.sql(
    """
    SELECT
        pii.name AS row_name,
        pi.name,
        pi.supplier,
        pi.supplier_name,
        """ + pi_gstin_col + """,
        pi.bill_no,
        pi.bill_date,
        pi.posting_date,
        pi.posting_time,
        pi.due_date,
        pi.is_return,
        pi.return_against,
        pi.rounded_total,
        pi.grand_total,
        pi.outstanding_amount,
        pi.remarks,
        pii.item_code,
        pii.item_name,
        pii.qty,
        pii.rate,
        pii.amount,
        pii.warehouse
    FROM `tabPurchase Invoice Item` pii
    INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
    WHERE pi.docstatus = 1
      AND pii.batch_no = %(batch)s
      """ + pi_date_clause + """
    ORDER BY ifnull(pi.bill_date, pi.posting_date) DESC, pi.posting_time DESC, pi.name DESC
    LIMIT 200
    """,
    pi_params,
    as_dict=True,
)

seen_pi_rows = set()
for r in pi_rows:
    seen_pi_rows.add(r.row_name)

if has_pi_sbb and has_sbe:
    try:
        sbb_pi_rows = frappe.db.sql(
            """
            SELECT
                pii.name AS row_name,
                pi.name,
                pi.supplier,
                pi.supplier_name,
                """ + pi_gstin_col + """,
                pi.bill_no,
                pi.bill_date,
                pi.posting_date,
                pi.posting_time,
                pi.due_date,
                pi.is_return,
                pi.return_against,
                pi.rounded_total,
                pi.grand_total,
                pi.outstanding_amount,
                pi.remarks,
                pii.item_code,
                pii.item_name,
                sbe.qty AS qty,
                pii.rate,
                (pii.rate * sbe.qty) AS amount,
                pii.warehouse
            FROM `tabSerial and Batch Entry` sbe
            INNER JOIN `tabPurchase Invoice Item` pii ON pii.serial_and_batch_bundle = sbe.parent
            INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
            WHERE pi.docstatus = 1
              AND sbe.batch_no = %(batch)s
              AND ifnull(pii.batch_no, '') != %(batch)s
              """ + pi_date_clause + """
            ORDER BY ifnull(pi.bill_date, pi.posting_date) DESC, pi.posting_time DESC, pi.name DESC
            LIMIT 200
            """,
            pi_params,
            as_dict=True,
        )
        for sr in sbb_pi_rows:
            if sr.row_name not in seen_pi_rows:
                seen_pi_rows.add(sr.row_name)
                pi_rows.append(sr)
    except Exception:
        pass

sup_gstin_cache = {}
purchases = []
batch_id_up = batch_id.strip().upper()
bname_up = bname.strip().upper()

for r in pi_rows:
    sup = r.supplier or ""
    gstin = (r.get("supplier_gstin") or "").strip()
    if not gstin and sup and sup_gstin_field:
        if sup not in sup_gstin_cache:
            try:
                sup_gstin_cache[sup] = (frappe.db.get_value("Supplier", sup, sup_gstin_field) or "").strip()
            except Exception:
                sup_gstin_cache[sup] = ""
        gstin = sup_gstin_cache[sup]

    line_mrp = mrp
    line_purc = pur
    line_net = net
    line_gst = gst
    line_upp = upp
    billed_packs = 0
    free_packs = 0
    loose_units = 0
    matched_remark = None

    if r.remarks and not r.is_return:
        try:
            rdata = json.loads(r.remarks)
            rlines = rdata.get("lines") if isinstance(rdata, dict) else (rdata if isinstance(rdata, list) else None)
            if isinstance(rlines, list):
                for ln in rlines:
                    lb = str(ln.get("batch") or "").strip().upper()
                    if lb and (lb == bname_up or lb == batch_id_up):
                        matched_remark = ln
                        break
        except Exception:
            matched_remark = None

    total_units = abs(num(r.qty))
    row_amt = abs(num(r.amount))

    if matched_remark:
        line_upp = int(num(matched_remark.get("upp")) or upp)
        if line_upp < 1:
            line_upp = 1
        line_gst = num(matched_remark.get("gst") if matched_remark.get("gst") is not None else gst)
        line_mrp = num(matched_remark.get("mrp") or mrp)
        raw_rate = num(matched_remark.get("rate"))
        basis = matched_remark.get("basis") or "excl"
        if basis == "incl" and line_gst > 0:
            line_purc = round(raw_rate / (1.0 + line_gst / 100.0), 2)
        else:
            line_purc = raw_rate
        if matched_remark.get("net") is not None:
            line_net = num(matched_remark.get("net"))
        else:
            line_net = line_purc
        bp_val = matched_remark.get("billed_packs") if matched_remark.get("billed_packs") is not None else matched_remark.get("packs")
        billed_packs = int(num(bp_val))
        free_packs = int(num(matched_remark.get("free_packs")))
        loose_units = int(num(matched_remark.get("units")))
        if billed_packs == 0 and free_packs == 0 and loose_units == 0 and total_units > 0:
            billed_packs = int(total_units // line_upp)
            loose_units = int(round(total_units % line_upp))
    else:
        eff_pack = (row_amt / total_units * line_upp) if total_units > 0 else (abs(num(r.rate)) * line_upp)
        line_net = net if net > 0 else round(eff_pack, 2)
        line_purc = pur if pur > 0 else round(eff_pack, 2)
        if line_net > 0 and row_amt > 0 and not r.is_return:
            calc_billed = int(round(row_amt / line_net))
            calc_billed_qty = calc_billed * line_upp
            if 0 < calc_billed_qty <= total_units:
                billed_packs = calc_billed
                free_packs = int((total_units - calc_billed_qty) // line_upp)
                loose_units = int(round((total_units - calc_billed_qty) % line_upp))
            else:
                billed_packs = int(total_units // line_upp)
                loose_units = int(round(total_units % line_upp))
        else:
            billed_packs = int(total_units // line_upp)
            loose_units = int(round(total_units % line_upp))

    lm_excl = (line_mrp / (1.0 + line_gst / 100.0)) if line_gst > 0 else line_mrp
    line_margin = ((lm_excl - line_net) / lm_excl * 100.0) if (lm_excl > 0 and line_net > 0) else 0.0

    tot = num(r.rounded_total if (r.rounded_total and num(r.rounded_total) > 0) else r.grand_total)
    out_amt = num(r.outstanding_amount)
    pay_status = "Paid"
    if r.is_return:
        pay_status = "Return"
    elif tot > 0 and out_amt >= (tot - 0.01):
        pay_status = "Unpaid"
    elif out_amt > 0.01:
        pay_status = "Partially Paid"

    purchases.append({
        "invoice": r.name,
        "supplier": sup,
        "supplier_name": r.supplier_name or sup,
        "gstin": gstin,
        "bill_no": r.bill_no or "",
        "bill_date": str(r.bill_date or r.posting_date or ""),
        "posting_date": str(r.posting_date or ""),
        "time": str(r.posting_time or "")[:5],
        "is_return": int(r.is_return or 0),
        "return_against": r.return_against or "",
        "status": pay_status,
        "invoice_total": abs(tot),
        "warehouse": r.warehouse or "",
        "mrp": round(line_mrp, 2),
        "purchase_rate": round(line_purc, 2),
        "net_rate": round(line_net, 2),
        "gst": line_gst,
        "upp": line_upp,
        "qty_units": -total_units if r.is_return else total_units,
        "billed_packs": billed_packs,
        "free_packs": free_packs,
        "loose_units": loose_units,
        "margin_pct": round(line_margin, 2),
        "expiry": exp,
    })

# Also fetch Stock Entry / Stock Reconciliation receipts/adjustments for context when opened via Add Stock
stock_entries = []
try:
    se_rows = frappe.db.sql(
        """
        SELECT
            se.name,
            se.stock_entry_type,
            se.posting_date,
            se.posting_time,
            sed.qty,
            sed.basic_rate,
            sed.t_warehouse,
            sed.s_warehouse
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.docstatus = 1
          AND sed.batch_no = %(batch)s
        ORDER BY se.posting_date DESC, se.posting_time DESC
        LIMIT 50
        """,
        {"batch": bname},
        as_dict=True,
    )
    for se in se_rows:
        stock_entries.append({
            "doctype": "Stock Entry",
            "name": se.name,
            "type": se.stock_entry_type or "Stock Entry",
            "date": str(se.posting_date or ""),
            "qty": num(se.qty),
            "rate": round(num(se.basic_rate) * upp, 2),
            "warehouse": se.t_warehouse or se.s_warehouse or "",
        })
    sr_rows = frappe.db.sql(
        """
        SELECT
            sr.name,
            sr.purpose,
            sr.posting_date,
            sri.qty,
            sri.valuation_rate,
            sri.warehouse
        FROM `tabStock Reconciliation Item` sri
        INNER JOIN `tabStock Reconciliation` sr ON sr.name = sri.parent
        WHERE sr.docstatus = 1
          AND sri.batch_no = %(batch)s
        ORDER BY sr.posting_date DESC, sr.posting_time DESC
        LIMIT 20
        """,
        {"batch": bname},
        as_dict=True,
    )
    for sr in sr_rows:
        stock_entries.append({
            "doctype": "Stock Reconciliation",
            "name": sr.name,
            "type": sr.purpose or "Stock Reconciliation",
            "date": str(sr.posting_date or ""),
            "qty": num(sr.qty),
            "rate": round(num(sr.valuation_rate) * upp, 2),
            "warehouse": sr.warehouse or "",
        })
except Exception:
    pass

# =======================
# SALES DETAILS FOR BATCH
# =======================
has_si_sbb = frappe.get_meta("Sales Invoice Item").has_field("serial_and_batch_bundle")
si_meta = frappe.get_meta("Sales Invoice")
has_si_patient = si_meta.has_field("patient")
has_si_pname = si_meta.has_field("patient_name")

si_date_clause = ""
si_params = {"batch": bname}
if from_date:
    si_date_clause += " AND si.posting_date >= %(from_date)s"
    si_params["from_date"] = from_date
if to_date:
    si_date_clause += " AND si.posting_date <= %(to_date)s"
    si_params["to_date"] = to_date

si_pt_col = "si.patient" if has_si_patient else "'' AS patient"
si_pnm_col = "si.patient_name" if has_si_pname else "'' AS patient_name"

si_rows = frappe.db.sql(
    """
    SELECT
        sii.name AS row_name,
        si.name,
        si.customer,
        si.customer_name,
        """ + si_pt_col + """,
        """ + si_pnm_col + """,
        si.posting_date,
        si.posting_time,
        si.is_return,
        si.return_against,
        si.is_pos,
        si.rounded_total,
        si.grand_total,
        si.outstanding_amount,
        sii.item_code,
        sii.item_name,
        sii.qty,
        sii.price_list_rate,
        sii.discount_percentage,
        sii.rate,
        sii.amount,
        sii.warehouse
    FROM `tabSales Invoice Item` sii
    INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
    WHERE si.docstatus = 1
      AND sii.batch_no = %(batch)s
      """ + si_date_clause + """
    ORDER BY si.posting_date DESC, si.posting_time DESC, si.name DESC
    LIMIT 200
    """,
    si_params,
    as_dict=True,
)

seen_si_rows = set()
for r in si_rows:
    seen_si_rows.add(r.row_name)

if has_si_sbb and has_sbe:
    try:
        sbb_si_rows = frappe.db.sql(
            """
            SELECT
                sii.name AS row_name,
                si.name,
                si.customer,
                si.customer_name,
                """ + si_pt_col + """,
                """ + si_pnm_col + """,
                si.posting_date,
                si.posting_time,
                si.is_return,
                si.return_against,
                si.is_pos,
                si.rounded_total,
                si.grand_total,
                si.outstanding_amount,
                sii.item_code,
                sii.item_name,
                sbe.qty AS qty,
                sii.price_list_rate,
                sii.discount_percentage,
                sii.rate,
                (sii.rate * sbe.qty) AS amount,
                sii.warehouse
            FROM `tabSerial and Batch Entry` sbe
            INNER JOIN `tabSales Invoice Item` sii ON sii.serial_and_batch_bundle = sbe.parent
            INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE si.docstatus = 1
              AND sbe.batch_no = %(batch)s
              AND ifnull(sii.batch_no, '') != %(batch)s
              """ + si_date_clause + """
            ORDER BY si.posting_date DESC, si.posting_time DESC, si.name DESC
            LIMIT 200
            """,
            si_params,
            as_dict=True,
        )
        for sr in sbb_si_rows:
            if sr.row_name not in seen_si_rows:
                seen_si_rows.add(sr.row_name)
                si_rows.append(sr)
    except Exception:
        pass

si_names = []
for r in si_rows:
    if r.name and r.name not in si_names:
        si_names.append(r.name)

pay_mode_map = {}
sle_batch_cost = {}
sle_item_cost = {}

if si_names:
    try:
        pm_rows = frappe.db.sql(
            """
            SELECT parent, mode_of_payment
            FROM `tabSales Invoice Payment`
            WHERE parent IN %(names)s AND amount != 0
            ORDER BY idx ASC
            """,
            {"names": si_names},
            as_dict=True,
        )
        for pm in pm_rows:
            if pm.parent not in pay_mode_map and pm.mode_of_payment:
                pay_mode_map[pm.parent] = pm.mode_of_payment
    except Exception:
        pass

    try:
        sle_rows = frappe.db.sql(
            """
            SELECT voucher_no, batch_no, actual_qty, stock_value_difference
            FROM `tabStock Ledger Entry`
            WHERE voucher_type = 'Sales Invoice'
              AND voucher_no IN %(names)s
              AND is_cancelled = 0
              AND item_code = %(item_code)s
            """,
            {"names": si_names, "item_code": item_code},
            as_dict=True,
        )
        for sl in sle_rows:
            vno = sl.voucher_no
            vd = -num(sl.stock_value_difference)
            aq = -num(sl.actual_qty)
            if sl.batch_no == bname:
                prev = sle_batch_cost.get(vno) or {"cost": 0.0, "qty": 0.0}
                prev["cost"] += vd
                prev["qty"] += aq
                sle_batch_cost[vno] = prev
            prev_it = sle_item_cost.get(vno) or {"cost": 0.0, "qty": 0.0}
            prev_it["cost"] += vd
            prev_it["qty"] += aq
            sle_item_cost[vno] = prev_it
    except Exception:
        pass

sales = []
for r in si_rows:
    is_ret = int(r.is_return or 0)
    qty_units = -abs(num(r.qty)) if is_ret else abs(num(r.qty))
    abs_units = abs(qty_units)
    packs = int(abs_units // upp)
    loose_units = int(round(abs_units % upp))

    pl_pack = round(num(r.price_list_rate) * upp, 2)
    sale_pack = round(num(r.rate) * upp, 2)
    mrp_pack = pl_pack if pl_pack > 0 else (mrp if mrp > 0 else sale_pack)
    disc_pct = num(r.discount_percentage)
    if disc_pct <= 0 and mrp_pack > 0 and sale_pack > 0 and sale_pack < (mrp_pack - max(0.02, 0.006 * upp)):
        disc_pct = round((1.0 - sale_pack / mrp_pack) * 100.0, 2)

    raw_amt = abs(num(r.amount))
    line_amt_incl = -raw_amt if is_ret else raw_amt
    sale_excl = (line_amt_incl / (1.0 + gst / 100.0)) if gst > 0 else line_amt_incl

    cost_excl = 0.0
    bc = sle_batch_cost.get(r.name)
    ic = sle_item_cost.get(r.name)
    if bc and abs(bc["qty"]) > 0.0001 and abs(bc["cost"]) > 0.0001:
        cost_excl = bc["cost"] * (qty_units / bc["qty"])
    elif ic and abs(ic["qty"]) > 0.0001 and abs(ic["cost"]) > 0.0001:
        cost_excl = ic["cost"] * (qty_units / ic["qty"])
    elif net > 0:
        cost_excl = (qty_units / upp) * net

    profit = sale_excl - cost_excl
    profit_pct = (profit / sale_excl * 100.0) if abs(sale_excl) > 0.001 else 0.0

    pmode = pay_mode_map.get(r.name, "")
    if r.is_return:
        sale_type = "Return Note"
    elif pmode:
        sale_type = pmode + " Sale" if "sale" not in pmode.lower() else pmode
    elif num(r.outstanding_amount) > 0.01:
        sale_type = "Credit Sale"
    else:
        sale_type = "Cash Sale"

    cust_label = (r.customer_name or r.customer or "Walk-in").strip()
    pt_name = (r.get("patient_name") or r.get("patient") or "").strip()

    sales.append({
        "invoice": r.name,
        "customer": r.customer or "",
        "customer_name": cust_label,
        "patient_name": pt_name,
        "sale_type": sale_type,
        "payment_mode": pmode or ("Credit" if num(r.outstanding_amount) > 0.01 else "Cash"),
        "posting_date": str(r.posting_date or ""),
        "time": str(r.posting_time or "")[:5],
        "is_return": int(r.is_return or 0),
        "return_against": r.return_against or "",
        "warehouse": r.warehouse or "",
        "mrp": round(mrp_pack, 2),
        "sale_rate": round(sale_pack, 2),
        "discount_percentage": round(disc_pct, 2),
        "upp": upp,
        "qty_units": qty_units,
        "packs": packs,
        "loose_units": loose_units,
        "amount": round(line_amt_incl, 2),
        "sale_excl": round(sale_excl, 2),
        "cost_excl": round(cost_excl, 2),
        "profit": round(profit, 2),
        "profit_pct": round(profit_pct, 2),
        "expiry": exp,
    })

def pi_sort_key(x):
    return (x.get("bill_date") or x.get("posting_date") or "", x.get("time") or "", x.get("invoice") or "")


def si_sort_key(x):
    return (x.get("posting_date") or "", x.get("time") or "", x.get("invoice") or "")


def se_sort_key(x):
    return (x.get("date") or "", x.get("name") or "")


purchases = sorted(purchases, key=pi_sort_key, reverse=True)
sales = sorted(sales, key=si_sort_key, reverse=True)
stock_entries = sorted(stock_entries, key=se_sort_key, reverse=True)

frappe.response["message"] = {
    "batch": batch_info,
    "purchases": purchases,
    "stock_entries": stock_entries,
    "sales": sales,
    "is_admin": is_admin,
    "today": str(frappe.utils.today()),
}
