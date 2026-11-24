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

    allowed_roles = [
        "Healthcare Administrator", "System Manager", "Physician",
        "Stock Manager", "Stock User", "Accounts Manager", "Accounts User", "Sales User"
    ]
    can_dash = (user == "Administrator")
    if not can_dash:
        for r in allowed_roles:
            if frappe.db.exists("Has Role", {"parent": user, "role": r}):
                can_dash = True
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
        "can_dashboard": can_dash
    }
