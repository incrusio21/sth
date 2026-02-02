import frappe
from frappe.utils import getdate,cint

def validate_posting_date(self,method):
    # Note : 
    # yang di cek adalah company, bulan, dan warehouse. 
    # in future jika ada permintaan mengecek warehouse, uncomment warehouse

    # warehouse = self.items[0].warehouse if self.doctype != "Stock Entry" else [ r.s_warehouse or r.t_warehouse for r in self.items ]
    list_tutup_buku = frappe.db.sql("""
        select tb.company ,month(from_date) as bulan,group_concat(tbd.warehouse  separator ',') as `warehouse` from `tabTutup Buku Fisik` tb
        join `tabTutup Buku Detail` tbd on tb.name = tbd.parent
        where tb.docstatus = 1
        group by tb.name
    """,as_dict=True)

    for tutup_buku in list_tutup_buku:
        dateformat = getdate(self.posting_date)
        if (
          dateformat.month == cint(tutup_buku.bulan) and 
          self.company == tutup_buku.company and
        #   warehouse in tutup_buku.warehouse if isinstance(warehouse,str) else any( d for d in warehouse if d.warehouse in tutup_buku.warehouse) and
          (
            self.doctype not in ["Sales Invoice","Purchase Invoice"] 
            or (self.doctype in ["Sales Invoice","Purchase Invoice"] and getattr(self,"update_stock",False))
          )
        ) :
            frappe.throw("Transaksi pada bulan ini sudah ditutup dan tidak dapat diproses.")