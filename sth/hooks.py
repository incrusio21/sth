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
app_include_css = ["/assets/sth/css/lib/tabulator.min.css","sth.bundle.css"]
app_include_js = [
    "/assets/sth/js/lib/tabulator.min.js",
    "sth.bundle.js"
]

# include js, css files in header of web template
# web_include_css = "/assets/sth/css/sth.css"
# web_include_js = "/assets/sth/js/sth.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "sth/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
page_js = {"print" : "public/js/override/print_override.js"}

# include js in doctype views
doctype_js = {
	"Asset": "public/js/asset.js",
	"Asset Capitalization": "public/js/asset_capitalization.js",
	"Attendance": "public/js/attendance.js",
	"Contract Template": "public/js/contract_template.js",
	"Currency Exchange": "public/js/currency_exchange.js",
	"Customer": "public/js/customer.js",
	"Delivery Note": "public/js/delivery_note.js",
	"Driver": "public/js/driver.js",
	"Employee": "public/js/employee.js",
	"Exit Interview": "public/js/exit_interview.js",
	"Expense Claim": "public/js/expense_claim.js",
	"Item": "public/js/item.js",
	"Item Group": "public/js/item_group.js",
	"Item Price": "public/js/item_price.js",
	"Loan": "hr_customize/custom/loan.js",
	"Material Request": "public/js/material_request.js",
	"Payroll Entry": "hr_customize/custom/payroll_entry.js",
	"Payment Entry": "hr_customize/custom/payment_entry.js",
	"Project": "legal/custom/project.js",
	"Purchase Invoice": ["buying_sth/custom/purchase_invoice.js", "legal/custom/purchase_invoice.js", "accounting_sth/custom/non_voucher_match.js","accounting_sth/custom/override_purchase_invoice.js","public/js/purchase_invoice.js"],
	"Purchase Order": ["buying_sth/custom/purchase_order.js","public/js/purchase_order.js"],
	"Purchase Receipt": ["buying_sth/custom/purchase_receipt.js", "legal/custom/purchase_receipt.js", "public/js/purchase_receipt.js"],
	"Quotation": "public/js/quotation.js",
	"Request for Quotation" : "public/js/request_for_quotation.js",
	"Salary Slip": "hr_customize/custom/salary_slip.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Sales Order": "public/js/sales_order.js",
	"Stock Reconciliation": "public/js/stock_reconciliation.js",
	"Supplier": "public/js/supplier.js",
	"Supplier Quotation": "public/js/supplier_quotation.js",
	"Training Event": "public/js/training_event.js",
	"Travel Request": "public/js/travel_request.js",
	
}

doctype_list_js = {
	"Attendance" : "hr_customize/custom/attendance_list.js",
	"Request for Quotation" : "public/js/request_for_quotation_list.js",
}
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
jinja = {
	"methods": [
		"sth.jinja.money_in_words_idr",
		"sth.utils.encrypt"
	],
	# "filters": "sth.utils.jinja_filters"
}

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

standard_queries = {

	"Bank": "sth.controllers.queries.get_bank_query",
	"Customer": "sth.controllers.queries.customer_query",
	# "Expense Claim Type": "sth.controllers.queries.get_expense_claim_type",
	"Item Group": "sth.controllers.queries.item_group_query",
	"Kegiatan": "sth.controllers.queries.kegiatan_query",
	"Months": "sth.controllers.queries.month_query",
	# "Unit": "sth.controllers.queries.unit_query",
}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	# "Loan Application": "sth.overrides.loan_application.LoanApplication",
	"Asset": "sth.overrides.asset.Asset",
	"Asset Capitalization": "sth.overrides.asset_capitalization.AssetCapitalization",
	"Asset Depreciation Schedule": "sth.overrides.asset_depreciation_schedule.AssetDepreciationSchedule",
	"Asset Movement": "sth.overrides.asset_movement.AssetMovement",
	"Attendance": "sth.overrides.attendance.Attendance",
	"Bank Account": "sth.overrides.bank_account.BankAccount",
	"Contract Template": "sth.overrides.contract_template.ContractTemplate",
	"Currency Exchange": "sth.overrides.currency_exchange.CurrencyExchange",
	"Customer": "sth.overrides.customer.Customer",
	"Employee Promotion": "sth.overrides.employee_promotion.STHEmployeePromotion",
	"Employee Transfer": "sth.overrides.employee_transfer.STHEmployeeTransfer",
	"Event": "sth.overrides.event.Event",
	"Exit Interview": "sth.overrides.exit_interview.ExitInterview",
	"Expense Claim": "sth.overrides.expense_claim.ExpenseClaim",
	"Item": "sth.overrides.item.Item",
	"Loan Disbursement": "sth.overrides.loan_disbursement.STHLoanDisbursement",
	"Loan Repayment Schedule": "sth.overrides.loan_repayment_schedule.STHLoanRepaymentSchedule",
	"Payroll Entry": "sth.overrides.payroll_entry.PayrollEntry",
	"Purchase Invoice": "sth.overrides.purchase_invoice.SthPurchaseInvoice",
	"Purchase Receipt": "sth.overrides.purchase_receipt.SthPurchaseReceipt",
	"Salary Slip": "sth.overrides.salary_slip.SalarySlip",
	"Stock Entry": "sth.overrides.stock_entry.StockEntry",
	"Supplier": "sth.overrides.supplier.Supplier",
    "Supplier Quotation": "sth.overrides.supplier_quotation.STHSupplierQuotation",
	"Payment Entry": "sth.overrides.payment_entry.PaymentEntry",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# untuk kriteria upload
	"*": {
		"on_update": "sth.finance_sth.doctype.kriteria_dokumen_finance.kriteria_dokumen_finance.create_kriteria_upload_document",
		"before_submit": "sth.finance_sth.doctype.kriteria_dokumen_finance.kriteria_dokumen_finance.validate_mandatory_document",
        "on_trash": "sth.finance_sth.doctype.kriteria_dokumen_finance.kriteria_dokumen_finance.delete_kriteria_upload_document"
	},

	"Asset": {
		"validate": ["sth.accounting_sth.custom.asset.cek_prec_untuk_asset","sth.overrides.asset.validate_company","sth.utils.qr_generator.validate_create_qr","sth.finance_sth.custom.asset.calculate_penyusutan_fiscal"],
		"on_update_after_submit":"sth.sales_sth.custom.asset.track_insurance_changes"
	},
	"Attendance": {
		"validate": "sth.hr_customize.custom.attendance.Attendance",
		"on_submit": "sth.hr_customize.custom.attendance.Attendance",
		"on_cancel": "sth.hr_customize.custom.attendance.Attendance",
		"repair_employee_payment_log": "sth.hr_customize.custom.attendance.Attendance"
	},
	"Delivery Note": {
		"validate": ["sth.sales_sth.custom.quotation.calculate_ongkos_angkut","sth.sales_sth.custom.sales_order.validate_price_list"],
	},
	"Driver": {
		"validate": "sth.utils.qr_generator.validate_create_qr",
	},
	"Employee": {
		"after_insert": "sth.hr_customize.custom.leave_policy.create_allocations_for_new_employee"
	},
	"Employee Potongan": {
		"validate": "sth.procurement_sth.custom.item.check_persetujuan",
	},
	"Event": {
		"validate": ["sth.overrides.event.before_save"],
		"on_update": "sth.overrides.event.on_update"
	},
	"Item": {
		"validate": ["sth.procurement_sth.custom.item.check_persetujuan","sth.overrides.item.validate_item_name","sth.overrides.item.cek_status"],
		"after_insert": "sth.procurement_sth.custom.item.cek_status_awal"
	},
	"Item Group": {
		"validate": "sth.procurement_sth.custom.item.check_persetujuan",
	},
	"Leave Type": {
		"on_change": "sth.hr_customize.custom.leave_type.clear_cache"
	},
	"Leave Policy": {
		"on_submit": "sth.hr_customize.custom.leave_policy.create_annual_leave_allocations"
	},
	"Loan": {
		"validate": "sth.hr_customize.custom.loan.Loan",
	},
	"Loan Product": {
		"validate": "sth.hr_customize.custom.loan_product.LoanProduct",
	},
	"Loan Repayment": {
		"on_cancel": "sth.hr_customize.custom.loan_repayment.LoanRepayment",
	},
	"Loan Disbursement": {
		"on_submit": "sth.hr_customize.custom.loan_disbursement.LoanDisbursement",
		"on_cancel": "sth.hr_customize.custom.loan_disbursement.LoanDisbursement",
	},
	"Material Request": {
		"on_submit": "sth.custom.material_request.update_ba_reference",
		"on_cancel": "sth.custom.material_request.update_ba_reference",
	},
	"Payment Entry":{
		"validate": [
			"sth.custom.payment_entry.cek_kriteria", "sth.custom.payment_entry.update_check_book", "sth.finance_sth.custom.cek_kriteria_upload_pe.generate_kriteria_upload_payment"
		],
		"on_submit": ["sth.custom.payment_entry.update_check_book", "sth.custom.payment_entry.update_status_deposito", "sth.custom.payment_entry.update_status_loan_bank", "sth.custom.payment_entry.update_status_dividen", "sth.overrides.payment_entry.on_submit_pdo"],
		"on_cancel": ["sth.custom.payment_entry.update_check_book", "sth.custom.payment_entry.update_status_deposito", "sth.custom.payment_entry.update_status_loan_bank", "sth.custom.payment_entry.update_status_dividen", "sth.overrides.payment_entry.on_cancel_pdo"],
		"on_trash": "sth.custom.payment_entry.update_check_book",
		"after_insert": "sth.finance_sth.custom.cek_kriteria_upload_pe.generate_kriteria_upload_payment"
	},
	"Permintaan Pengeluaran Barang": {
		"validate": ["sth.procurement_sth.custom.item.check_persetujuan"],
	},
	"Project": {
		"validate": "sth.legal.custom.project.Project",
		"on_update": "sth.legal.custom.project.Project",
		"on_trash": "sth.legal.custom.project.Project",
	},
    "Purchase Order": {
		"before_save": "sth.buying_sth.custom.purchase_order.set_accept_day"
	},
	"Purchase Receipt": {
		"validate": "sth.custom.purchase_receipt.set_purchase_order_if_exist"
	},
	"Purchase Invoice": {
		"validate": ["sth.custom.purchase_invoice.check_tanggal_kirim"],
		"on_submit": "sth.custom.purchase_invoice.set_training_event_purchase_invoice"
	},
	"Quotation": {
		"validate": ["sth.sales_sth.custom.sales_order.validate_price_list","sth.procurement_sth.custom.item.check_persetujuan"],
	},
	"Sales Order": {
		"validate": ["sth.sales_sth.custom.sales_order.check_dn_pending","sth.sales_sth.custom.sales_order.validate_price_list"],
		"onload": "sth.sales_sth.custom.sales_order.check_dn_pending",
	},
	"Sales Invoice": {
		"validate": ["sth.sales_sth.custom.sales_order.validate_price_list"],
	},
	"Supplier": {
		"validate": ["sth.overrides.supplier.cek_upload","sth.overrides.supplier.validate_ktp_name","sth.overrides.supplier.validate_supplier_name","sth.overrides.supplier.validate_sppkp_name","sth.overrides.supplier.non_aktifkan_table","sth.overrides.supplier.validate_no_rekening"],
		"before_save": "sth.overrides.supplier.update_supplier_email",
	},
	"Stock Reconciliation": {
		"validate": ["sth.custom.stock_reconciliation.validate_retain_amount"],
	},
	"Supplier Quotation": {
		# "before_submit": "sth.custom.supplier_quotation.update_status_rfq",
		"on_submit": "sth.custom.supplier_quotation.create_po_draft"
	},
	
	# "Training Event": {
	# 	"on_submit": "sth.custom.training_event.create_journal_entry",
	# 	"on_cancel": "sth.custom.training_event.delete_journal_entry",
	# },
	"Travel Request": {
		"on_submit": "sth.custom.travel_request.create_employee_advance",
		"on_cancel": "sth.custom.travel_request.cancel_employee_advance"
	},
	
	"Request for Quotation": {
		"before_save": "sth.custom.request_for_quotation.update_unit_in_table"
	},
    ("Proposal", "BAPP"): {
        "before_validate": "sth.legal.custom.tax_validation.validate_custom_tax",
        "validate": "sth.legal.custom.tax_validation.validate_custom_tax"
	},
    ("Delivery Note","Sales Invoice","Purchase Receipt","Purchase Invoice","Stock Entry"): {
        "validate": "sth.custom.stock_ledger.validate_posting_date"
	}
}


# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"sth.tasks.all"
# 	],
	"daily": [
		"sth.finance_sth.doctype.deposito.deposito.deposito_roll_over",
		"sth.overrides.event.custom_send_email_digest"
	],
    "daily_long": [
		"sth.hr_customize.doctype.employee_update_log.employee_update_log.repost_entries",
	],
# 	"hourly": [
# 		"sth.tasks.hourly"
# 	],
# 	"weekly": [
# 		"sth.tasks.weekly"
# 	],
	"monthly": [
		"sth.tasks.employee.update_employee_employment_tenure"
	],
	"cron": {
		"0 0 * * *": [
			"sth.hr_customize.custom.leave_policy.create_daily_leave_allocations"
		]
	}
}

# Testing
# -------

# before_tests = "sth.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"lending.loan_management.doctype.loan.loan.make_loan_disbursement": "sth.hr_customize.custom.loan.make_loan_disbursement",
	"hrms.overrides.employee_payment_entry.get_payment_reference_details": "sth.overrides.payment_entry.get_payment_reference_details",
    "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry": "sth.legal.custom.payment_entry.get_payment_entry",
	"erpnext.buying.doctype.supplier_quotation.supplier_quotation.make_purchase_order": "sth.overrides.supplier_quotation.make_purchase_order",
	"erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice": "sth.buying_sth.custom.purchase_receipt.make_purchase_invoice",
	"erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt": "sth.buying_sth.custom.purchase_order.make_purchase_receipt",
	"erpnext.buying.doctype.request_for_quotation.request_for_quotation.make_supplier_quotation_from_rfq": "sth.overrides.request_for_quotation.make_supplier_quotation_from_rfq",
	"erpnext.stock.doctype.material_request.material_request.make_supplier_quotation": "sth.overrides.material_request.make_supplier_quotation",
	"erpnext.assets.doctype.asset.asset.get_values_from_purchase_doc": "sth.overrides.asset.get_values_from_purchase_doc",
	"frappe.model.mapper.map_docs": "sth.model.mapper.map_docs",
	"hrms.overrides.employee_payment_entry.get_payment_entry_for_employee": "sth.overrides.employee_advance.get_payment_entry_for_employee",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Project": "sth.legal.custom.project_dashboard.get_dashboard_data"
}

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

