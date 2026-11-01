app_name = "opd_clinic_1"
app_title = "opd_clinic_1"
app_publisher = "Naresh"
app_description = "opd"
app_email = "naresh@nkhub.in"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "opd_clinic_1",
# 		"logo": "/assets/opd_clinic_1/logo.png",
# 		"title": "ood_clinic_1",
# 		"route": "/opd_clinic_1",
# 		"has_permission": "opd_clinic_1.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/opd_clinic_1/css/opd_clinic_1.css"
# app_include_js = "/assets/opd_clinic_1/js/opd_clinic_1.js"

# include js, css files in header of web template
# web_include_css = "/assets/opd_clinic_1/css/opd_clinic_1.css"
# web_include_js = "/assets/opd_clinic_1/js/opd_clinic_1.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "opd_clinic_1/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "opd_clinic_1/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "opd_clinic_1.utils.jinja_methods",
# 	"filters": "opd_clinic_1.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "opd_clinic_1.install.before_install"
# after_install = "opd_clinic_1.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "opd_clinic_1.uninstall.before_uninstall"
# after_uninstall = "opd_clinic_1.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "opd_clinic_1.utils.before_app_install"
# after_app_install = "opd_clinic_1.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "opd_clinic_1.utils.before_app_uninstall"
# after_app_uninstall = "opd_clinic_1.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "opd_clinic_1.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["opd_clinic_1.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"opd_clinic_1.tasks.all"
# 	],
# 	"daily": [
# 		"opd_clinic_1.tasks.daily"
# 	],
# 	"hourly": [
# 		"opd_clinic_1.tasks.hourly"
# 	],
# 	"weekly": [
# 		"opd_clinic_1.tasks.weekly"
# 	],
# 	"monthly": [
# 		"opd_clinic_1.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "opd_clinic_1.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "opd_clinic_1.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "opd_clinic_1.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["opd_clinic_1.utils.before_request"]
# after_request = ["opd_clinic_1.utils.after_request"]

# Job Events
# ----------
# before_job = ["opd_clinic_1.utils.before_job"]
# after_job = ["opd_clinic_1.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"opd_clinic_1.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
fixtures = [
    {"dt": "Role", "filters": [["name", "in", ["My Role"]]]},
    {"dt": "Custom Field", "filters": [["module", "=", "My Customizations"]]},
    "Property Setter",
    "Custom DocPerm",
    {"dt": "Workflow State", "filters": [["name", "in", ["..."]]]},
    {"dt": "Workflow", "filters": [["name", "in", ["..."]]]},
    {"dt": "Client Script", "filters": [["module", "=", "My Customizations"]]},
    {"dt": "Server Script", "filters": [["module", "=", "My Customizations"]]},
    {"dt": "Web Page", "filters": [["name", "in", ["home", "about-us"]]]},
    "Web Template",
    "Notification",
    "Email Template",
    "Print Format",
]
