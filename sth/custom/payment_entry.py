import frappe

def cek_kriteria(self,method):
	if self.references:
		doctype = self.references[0].get("reference_doctype")
		
		if self.dokumen != doctype or not self.dokumen:
			# kalau tidak sama, kosongin dulu table
			self.detail_dokumen_finance = []

		if self.dokumen != doctype:
			if doctype:
				fill_kriteria(self, doctype)
			
			self.dokumen = doctype

def fill_kriteria(self,doctype):
	# ambil dulu dari kriteria
	kriteria = frappe.db.sql(""" SELECT name FROM `tabKriteria Dokumen Finance` WHERE name = "{}" """.format(doctype))
	if len(kriteria) > 0:
		kriteria_doc = frappe.get_doc("Kriteria Dokumen Finance",kriteria[0][0])
		for row in kriteria_doc.kriteria_dokumen_finance:
			self.append("detail_dokumen_finance",{
				"rincian_dokumen_finance": row.rincian_dokumen_finance
			})