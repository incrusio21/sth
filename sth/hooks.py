app_name = "sth"
app_title = "STH"
app_publisher = "DAS"
app_description = "STH Module"
app_email = "digitalasiasolusindo@gmail.com"
app_license = "mit"
# required_apps = []

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/sth/css/sth.css"
app_include_js = "sth.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/sth/css/sth.css"
# web_include_js = "/assets/sth/js/sth.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "sth/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Training Event": "public/js/training_event.js",
	"Travel Request": "public/js/travel_request.js",
	"Payment Entry": "public/js/payment_entry.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "sth/public/icons.svg"

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
# 	"methods": "sth.utils.jinja_methods",
# 	"filters": "sth.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "sth.install.before_install"
# after_install = "sth.install.after_install"

boot_session = "sth.startup.boot.boot_session"

# Uninstallation
# ------------

# before_uninstall = "sth.uninstall.before_uninstall"
# after_uninstall = "sth.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "sth.utils.before_app_install"
# after_app_install = "sth.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "sth.utils.before_app_uninstall"
# after_app_uninstall = "sth.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "sth.notifications.get_notification_config"

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

standard_queries = {"Kegiatan": "sth.controllers.queries.kegiatan_query"}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	# "Loan Application": "sth.overrides.loan_application.LoanApplication",
	"Payroll Entry": "sth.overrides.payroll_entry.PayrollEntry",
	"Salary Slip": "sth.overrides.salary_slip.SalarySlip",
	"Stock Entry": "sth.overrides.stock_entry.StockEntry",
	"Payment Entry": "sth.overrides.payment_entry.PaymentEntry",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Training Event": {
		"on_submit": "sth.custom.training_event.create_journal_entry",
		"on_cancel": "sth.custom.training_event.delete_journal_entry",
	},
	"Travel Request": {
		"on_submit": "sth.custom.travel_request.create_employee_advance",
	}
}


# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"sth.tasks.all"
# 	],
# 	"daily": [
# 		"sth.tasks.daily"
# 	],
# 	"hourly": [
# 		"sth.tasks.hourly"
# 	],
# 	"weekly": [
# 		"sth.tasks.weekly"
# 	],
# 	"monthly": [
# 		"sth.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "sth.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "sth.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "sth.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["sth.utils.before_request"]
# after_request = ["sth.utils.after_request"]

# Job Events
# ----------
# before_job = ["sth.utils.before_job"]
# after_job = ["sth.utils.after_job"]

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
# 	"sth.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

