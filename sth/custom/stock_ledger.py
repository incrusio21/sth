import frappe
from frappe.utils import getdate

def validate_posting_date(self,method):
    close_month = frappe.db.get_all("Tutup Buku Fisik",{"docstatus":1},["month(from_date) as bulan"],pluck="bulan")
    dateformat = getdate(self.posting_date)
    if dateformat.month in close_month:
        frappe.throw("Transaksi pada bulan ini sudah ditutup dan tidak dapat diproses.")