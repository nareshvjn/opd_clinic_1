# Server Script: user_profile
# type: API
# doctype: -
# event: Before Insert
# api_method: user_profile
# allow_guest: 1
# frequency: All
# disabled: 0

user = frappe.session.user
if not user or user == "Guest":
    frappe.response["message"] = {
        "logged_in": False,
        "user": "Guest"
    }
else:
    u = frappe.db.get_value("User", user, ["name", "email", "first_name", "last_name", "full_name", "user_image"], as_dict=True) or {}
    prac = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, ["name", "practitioner_name", "department"], as_dict=True) or {}

    role_rows = frappe.get_all("Has Role", filters={"parent": user}, fields=["role"])
    roles = []
    for rr in role_rows:
        if rr.role and rr.role not in roles:
            roles.append(rr.role)

    is_super = (user == "Administrator")
    has_sys = is_super or ("System Manager" in roles)
    is_admin = has_sys or ("Healthcare Administrator" in roles)

    dash_roles = [
        "Healthcare Administrator", "System Manager", "Physician",
        "Stock Manager", "Stock User", "Accounts Manager", "Accounts User", "Sales User"
    ]
    can_dash = is_super
    if not can_dash:
        for r in dash_roles:
            if r in roles:
                can_dash = True
                break

    can_registration = True
    can_doctor_desk = is_admin or ("Physician" in roles)

    # Matches ph_dash.py access rules for /pharmacy-home
    can_pharmacy = has_sys
    if not can_pharmacy:
        for r in ["Stock Manager", "Accounts Manager", "Accounts User"]:
            if r in roles:
                can_pharmacy = True
                break

    # Matches inv_meta.py / inv_save.py access rules for /create-invoice
    can_sales = is_admin
    if not can_sales:
        for r in ["Physician", "Accounts Manager", "Accounts User", "Sales User", "Stock Manager", "Stock User"]:
            if r in roles:
                can_sales = True
                break

    full_name = u.get("full_name") or u.get("first_name") or ""
    if not full_name:
        full_name = user.split("@")[0].title() if "@" in user else user

    frappe.response["message"] = {
        "logged_in": True,
        "user": user,
        "email": u.get("email") or user,
        "full_name": full_name,
        "user_image": u.get("user_image") or "",
        "practitioner": prac.get("practitioner_name") or "",
        "department": prac.get("department") or "",
        "roles": roles,
        "is_admin": is_admin,
        "can_dashboard": can_dash,
        "permissions": {
            "dashboard": can_dash,
            "registration": can_registration,
            "doctor_desk": can_doctor_desk,
            "pharmacy": can_pharmacy,
            "sales": can_sales
        }
    }
