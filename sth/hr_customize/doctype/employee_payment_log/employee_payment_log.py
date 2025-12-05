# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EmployeePaymentLog(Document):
    
    def validate(self):
        self.set_status()
        self.document_already_paid()

    def set_status(self):
        if not self.status:
            self.status = "Approved"

    def on_trash(self):
        # self.remove_document()
        self.document_already_paid()
    
    def remove_document(self):
        # skip jika berasal dari transaksi
        if self.flags.transaction_employee:
            return
        
        msg = _("Individual Employee Payment Ledger Entry cannot be cancelled.")
        msg += "<br>" + _("Please cancel related transaction.")
        frappe.throw(msg)

    def document_already_paid(self):
        if self.is_paid:
            frappe.throw("Payment for Employee {} has been made.".format(self.employee))
    
doctype_map = {
    "Buku Kerja Mandor Panen": [
        {
            "target_link": "employee_payment_log",
            "component_type": "Upah",
        },
        {
            "target_link": "kontanan_epl",
            "component_type": "Kontanan",
        },
        {
            "target_link": "denda_epl",
            "component_type": "Denda",
        },
        {
            "target_link": "brondolan_epl",
            "component_type": "Brondolan",
        }
    ],
    "Buku Kerja Mandor Perawatan": [
        {
            "target_link": "employee_payment_log",
            "component_type": "Upah",
        },
        {
            "target_link": "premi_epl",
            "component_type": "Premi",
        },
    ],
    "Lembur List": [
        {
            "target_link": "employee_payment_log",
            "component_type": "Lembur",
        }
    ],
    "Perhitungan Kompensasi PHK": [
        {
            "target_link": "employee_payment_log",
            "component_type": "Kompensasi",
        }
    ],
    "Transaksi Bonus": [
        {
            "target_link": "employee_payment_log",
            "component_type": "Bonus",
        },
        {
            "target_link": "employee_payment_log_earning_bonus",
            "component_type": "Bonus",
        },
        {
            "target_link": "employee_payment_log_deduction_bonus",
            "component_type": "Bonus",
        }
    ],
    "Transaksi THR": [
        {
            "target_link": "employee_payment_log",
            "component_type": "THR",
        },
        {
            "target_link": "employee_payment_log_earning_thr",
            "component_type": "THR",
        },
        {
            "target_link": "employee_payment_log_deduction_thr",
            "component_type": "THR",
        }
    ],
    "Pengajuan Panen Kontanan": [
        {
            "target_link": "mandor_epl",
            "component_type": "Kontanan",
        },
        {
            "target_link": "mandor1_epl",
            "component_type": "Kontanan",
        },
        {
            "target_link": "kerani_epl",
            "component_type": "Kontanan",
        }
    ],
}

def patch_every_emp():
    # BKM Perawatan
    for dm, epl_log in doctype_map.items():
        doc_list = frappe.get_all(dm, filters={"docstatus": 1}, pluck="name")
        for d in doc_list:
            doc = frappe.get_doc(dm, d)
            if doc.get("hasil_kerja"):
                for hk in doc.hasil_kerja:
                    for log_updater in epl_log:
                        epl = hk.get(log_updater["target_link"])
                        if not epl:
                            continue

                        if frappe.db.exists("Employee Payment Log", epl):
                            frappe.set_value("Employee Payment Log", epl, {
                                "voucher_type": doc.doctype,
                                "voucher_no": doc.name,
                                "voucher_detail_no": hk.name,
                                "component_type": log_updater["component_type"],
                            })

                            hk.db_set(log_updater["target_link"], None)
            elif doc.get("table_employee"):
                for hk in doc.table_employee:
                    for log_updater in epl_log:
                        epl = hk.get(log_updater["target_link"])
                        if not epl:
                            continue

                        if frappe.db.exists("Employee Payment Log", epl):
                            frappe.db.set_value("Employee Payment Log", epl, {
                                "voucher_type": doc.doctype,
                                "voucher_no": doc.name,
                                "voucher_detail_no": hk.name,
                                "component_type": log_updater["component_type"],
                            })

                            hk.db_set(log_updater["target_link"], None)
            else:
                for log_updater in epl_log:
                    epl = doc.get(log_updater["target_link"])
                    if not epl:
                        continue

                    if frappe.db.exists("Employee Payment Log", epl):
                        frappe.set_value("Employee Payment Log", epl, {
                            "voucher_type": doc.doctype,
                            "voucher_no": doc.name,
                            "component_type": log_updater["component_type"],
                        })
                    
                        doc.db_set(log_updater["target_link"], None)
