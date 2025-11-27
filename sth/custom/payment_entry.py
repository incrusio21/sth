import frappe

def cek_kriteria(self,method):
	if self.references:
		for row in self.references:
			doctype = row.reference_doctype
			docname = row.reference_name

			check = 0
			for row in self.detail_dokumen_finance:
				if row.type == doctype and row.name1 == docname:
					check = 1
			
			if check == 0:
				fill_kriteria(self, doctype, docname)

		# bersih-bersih kalau ada yang tidak di reference
		list_type = []
		list_name = []

		for row in self.references:
			list_type.append(row.reference_doctype)
			list_name.append(row.reference_name)

		self.detail_dokumen_finance = [baris for baris in self.detail_dokumen_finance if baris.type in list_type and baris.name1 in list_name]

def fill_kriteria(self,doctype, docname):
	# ambil dulu dari kriteria
	kriteria = frappe.db.sql(""" SELECT name FROM `tabKriteria Dokumen Finance` WHERE name = "{}" """.format(doctype))
	if len(kriteria) > 0:
		kriteria_doc = frappe.get_doc("Kriteria Dokumen Finance",kriteria[0][0])
		for row in kriteria_doc.kriteria_dokumen_finance:
			if row.aktif == 1:
				self.append("detail_dokumen_finance",{
					"rincian_dokumen_finance": row.rincian_dokumen_finance,
					"type": doctype,
					"name1": docname
				})