# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from hrms.hr.utils import update_employee_work_history
from sth.utils.tablelock_manager import TableLockManager

fieldname_table = {
	"Employee Promotion": "promotion_details",
	"Employee Transfer": "transfer_details"
}

class EmployeeUpdateLog(Document):
	def get_history(self):
		if not getattr(self, "_history", None):
			self.load_history()

		return self._history
	
	def load_history(self):
		self._history = frappe.get_all("Employee Property History", filters={"parent": self.voucher_no, "parenttype": self.voucher_type}, fields=["*"])
	
	def validate(self):
		self.validate_table_lock()
		self.validate_future_update()
		# self.validate_create_new_employee_id()

	# def validate_create_new_employee_id(self):
	# 	if not self.create_new_employee_id:
	# 		return
		
	# 	if frappe.db.exists("Employee Property Entries", {
	# 		"employee": [">", self.employee],
	# 		"posting_date": [">", self.posting_date],
	# 		"status": ["in", ["In Progress", "Completed"]]
	# 	}):
	# 		frappe.throw(f"can't create new Employee ID because employee have update after {self.posting_date}")

	def validate_table_lock(self):
		if not TableLockManager.is_table_locked("Employee Update Log"):
			return
		
		frappe.throw("Please wait scheduled update data employee to finish first")

	def validate_future_update(self, cancel=0):
		# check apakah ada update setelah tanggal yang di pilih (race condition sangat tidak mungkin terjadi)
		date = frappe.get_value("Employee Update Log", {
			"employee": self.employee, 
			"posting_date": [">", self.posting_date],
		}, "posting_date")

		if not date:
			return

		msg = f"Employee {self.employee} has a scheduled update on {date}. Updates should be made after this date."
		if cancel:
			msg = f"Please cancel latest update for employee {self.employee} first"

		frappe.throw(msg)
	
	def set_status(self, status=None, write=True):
		status = status or self.status
		if not status:
			self.status = "Queued"
		else:
			self.status = status
		if write:
			self.db_set("status", self.status)

	def on_trash(self):
		self.validate_table_lock()
		self.validate_future_update(cancel=1)
		if self.status == "Completed":
			self.repost_cancelled_doc()

	def repost_cancelled_doc(self):
		employee = frappe.get_doc("Employee", self.employee)
		if self.create_new_employee_id:
			if self.new_employee_id:
				frappe.throw(
					_("Please delete the Employee {0} to cancel this document").format(
						f"<a href='/app/Form/Employee/{self.new_employee_id}'>{self.new_employee_id}</a>"
					)
				)
			# mark the employee as active
			employee.status = "Active"
			employee.relieving_date = ""
		else:
			employee = update_employee_work_history(
				employee, self.get_history(), date=self.posting_date, cancel=True
			)

		if self.new_company and self.new_company != self.company:
			employee.company = self.company
			
		employee.save()

	def deduplicate_similar_employee(self):
		"""Deduplicate similar reposts based on item-warehouse-posting combination."""

		future_doc = frappe.get_all("Employee Update Log", {"employee": self.employee, "posting_date": [">", self.posting_date]}, pluck="voucher_no")
		if not future_doc:
			return
		
		for item in self.get("_history"):
			frappe.db.sql(
				"""
				update `tabEmployee Property History`
				set current = %(new)s
				WHERE parent in %(voucher_no)s
					""",
				{"new": item.new, "voucher_no": future_doc},
			)

		if self.new_employee:
			filters = {
				"employee": self.employee,
				"new_employee": self.new_employee,
				"name": self.name,
				"posting_date": self.posting_date,
			}

			frappe.db.sql(
				"""
				update `tabEmployee Update Log`
				set employee = %(new_employee)s
				WHERE employee = %(employee)s
					and name != %(name)s
					and posting_date > %(posting_date)s
					and status = 'Queued'
					""",
				filters,
			)

	@frappe.whitelist()
	def restart_reposting(self):
		self.set_status("Queued", write=False)
		self.error_log = ""
		self.db_update()

def on_doctype_update():
	frappe.db.add_unique("Employee Update Log", ["employee", "posting_date"], constraint_name="unique_employee_date") 

def repost_entries():
	"""
	Reposts 'Repost Employee Update Log' entries in queue.
	Called hourly via hooks.py.
	"""
	# if not in_configured_timeslot():
	# 	return
	import time

	try:
		TableLockManager.lock_table(
			doctype="Employee Update Log",
			duration_minutes=120,  # Safety margin
			reason=f"Employee Update in Progress"
		)

		riv_entries = get_repost_employee_property_entries()
		print(riv_entries)

		for row in riv_entries:
			doc = frappe.get_doc("Employee Update Log", row.name)
			if doc.status in ("Queued", "In Progress"):
				repost(doc)
	finally:
		# Always unlock tables
		TableLockManager.unlock_table("Employee Update Log")
	
def get_repost_employee_property_entries():
	return frappe.db.sql(
		""" SELECT name from `tabEmployee Update Log`
		WHERE status in ('Queued', 'In Progress') and posting_date <= %s
		ORDER BY posting_date asc, creation asc, status asc
	""",
		today(),
		as_dict=1
	)

def repost(doc):
	# Set di cache dengan expiry
	try:
		frappe.flags.through_repost_item_valuation = True
		if not frappe.db.exists("Employee Update Log", doc.name):
			return

		# This is to avoid TooManyWritesError in case of large reposts
		frappe.db.MAX_WRITES_PER_TRANSACTION *= 4

		doc.set_status("In Progress")
		if not frappe.flags.in_test:
			frappe.db.commit()

		# if doc.recreate_stock_ledgers:
		# 	doc.recreate_stock_ledger_entries()

		repost_employee_property(doc)
		# repost_sl_entries(doc)
		# repost_gl_entries(doc)

		doc.deduplicate_similar_employee()
		doc.set_status("Completed")
		# doc.db_set("reposting_data_file", None)
		# remove_attached_file(doc.name)

	except Exception as e:
		if frappe.flags.in_test:
			# Don't silently fail in tests,
			# there is no reason for reposts to fail in CI
			raise

		frappe.db.rollback()
		traceback = frappe.get_traceback(with_context=True)
		doc.log_error("Unable to repost employee")

		message = frappe.message_log.pop() if frappe.message_log else ""
		if isinstance(message, dict):
			message = message.get("message")

		status = "Failed"
		# If failed because of timeout, set status to In Progress
		if traceback and ("timeout" in traceback.lower() or "Deadlock found" in traceback):
			status = "In Progress"

		if traceback:
			message += "<br><br>" + "<b>Traceback:</b> <br>" + traceback

		frappe.db.set_value(
			doc.doctype,
			doc.name,
			{
				"error_log": message,
				"status": status,
			},
		)

		# if status == "Failed":
		# 	outgoing_email_account = frappe.get_cached_value(
		# 		"Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "name"
		# 	)

		# 	if outgoing_email_account and not isinstance(e, RecoverableErrors):
		# 		notify_error_to_stock_managers(doc, message)
		# 		doc.set_status("Failed")
	finally:
		if not frappe.flags.in_test:
			frappe.db.commit()

def repost_employee_property(doc):
	employee = frappe.get_doc("Employee", doc.new_employee_id or doc.employee)

	history = doc.get_history()
	
	def validate_user_in_details():
		for item in history:
			if item.fieldname == "user_id" and item.new != item.current:
				return True
		return False
	
	if doc.create_new_employee_id and not doc.new_employee_id:
		new_employee = frappe.copy_doc(employee)
		new_employee.name = None
		new_employee.employee_number = None

		new_employee = update_employee_work_history(
			new_employee, history, date=doc.posting_date
		)
		if doc.new_company and doc.company != doc.new_company:
			new_employee.internal_work_history = []
			new_employee.date_of_joining = doc.posting_date
			new_employee.company = doc.new_company

		if employee.user_id and not validate_user_in_details():
			new_employee.user_id = employee.user_id
			employee.db_set("user_id", "")

		new_employee.insert()

		doc.db_set("new_employee_id", new_employee.name)
		employee.db_set("relieving_date", doc.posting_date)
		employee.db_set("status", "Left")
	else:
		employee = update_employee_work_history(employee, history, date=doc.posting_date)
		if doc.new_company and doc.company != doc.new_company:
			employee.company = doc.new_company
			employee.date_of_joining = doc.transfer_date

		employee.save()
	
def create_or_update_employee_propertry(self, posting_date):
	property_entries = frappe.get_doc({
		"doctype": "Employee Update Log",
		"company": self.company,
		"new_company": self.get("new_company"),
		"create_new_employee_id": self.get("create_new_employee_id"),
		"employee": self.employee,
		"posting_date": posting_date,
		"voucher_type": self.doctype,
		"voucher_no": self.name,
		"status": "Queued"
	})
	property_entries.flags.ignore_permissions = 1
	property_entries.insert()

@frappe.whitelist()
def execute_repost_employee_log():
	"""Execute repost item valuation via scheduler."""
	frappe.get_doc("Scheduled Job Type", "employee_update_log.repost_entries").enqueue(force=True)
