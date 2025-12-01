# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def create_task_by_order(self, method):
    # jika bukan untuk proposal. hapus purchase order
    if not self.for_proposal:
        self.purchase_order = None
    
    before_save = self.get_latest()
    # pastikan purchase order pada project tidak boleh berubah
    if (
        before_save and 
        before_save.purchase_order and 
        before_save.purchase_order != self.purchase_order
    ):
        frappe.throw(_("No changes allowed to Purchase Order"))

    # skip create task jika tidak terdapat data po atau task sudah ada
    if not self.purchase_order or frappe.db.exists("Task", {"purchase_order": self.purchase_order}):
        return
    
    po = frappe.get_doc("Purchase Order", self.purchase_order)
    # run hanya untuk ambil key onload
    po.run_method("onload")

    # jika po bukan submit atau bukan merupakan check progress
    if po.docstatus != 1 or not po.get_onload("check_progress"):
        frappe.throw(f"Unable to create project from Purchase Order {self.purchase_order}")

    subject = po.get_onload("progress_benchmark")
    for item in po.items:
        task = frappe.new_doc("Task")

        task.update({
            "subject": item.get(subject),
            "project": self.name,
            "purchase_order": self.purchase_order,
            "purchase_order_item": item.name,
            "progress": item.progress_received
        })

        task.save()

