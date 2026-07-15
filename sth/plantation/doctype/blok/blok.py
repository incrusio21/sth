# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today

BULAN_MAP = {
	"Januari": 1,
	"Februari": 2,
	"Maret": 3,
	"April": 4,
	"Mei": 5,
	"Juni": 6,
	"Juli": 7,
	"Agustus": 8,
	"September": 9,
	"Oktober": 10,
	"November": 11,
	"Desember": 12,
}

class Blok(Document):
	def validate(self):
		self.set_periode_bjr()

	def before_save(self):
		self.set_periode_bjr()

	def after_insert(self):
		self.make_cost_center()

	def on_update(self):
		self.make_cost_center()

	def make_cost_center(self):
		if not self.tahun_tanam or not self.unit:
			return

		unit_doc = frappe.get_doc("Unit", self.unit)
		company = unit_doc.company
		company_doc = frappe.get_doc("Company", company)
		abbr = company_doc.abbr

		# --- Cost Center Tahun Tanam (group, parent dari blok CC) ---
		tahun_cc_existing = frappe.db.get_value(
			"Cost Center",
			{"cost_center_name": str(self.tahun_tanam), "company": company},
			["name", "is_group"],
			as_dict=True
		)

		if tahun_cc_existing:
			tahun_cc = tahun_cc_existing.name
			
		else:
			cc = frappe.new_doc("Cost Center")
			cc.cost_center_name = str(self.tahun_tanam)
			cc.parent_cost_center = f"Tahun Tanam - {abbr}"
			cc.company = company
			cc.is_group = 0
			cc.flags.ignore_permissions = True
			cc.insert()
			frappe.db.commit()
			tahun_cc = cc.name

		if self.cost_center != tahun_cc:
			self.db_set("cost_center", tahun_cc, update_modified=False)

		# --- Cost Center Blok (child dari Tahun Tanam CC) ---
		blok_cc_existing = frappe.db.get_value(
			"Cost Center",
			{"cost_center_name": self.blok, "company": company},
			"name"
		)

		if not blok_cc_existing:
			blok_cc = frappe.new_doc("Cost Center")
			blok_cc.cost_center_name = self.blok
			blok_cc.parent_cost_center = "Blok - {}".format(frappe.get_doc("Company", company).abbr)
			blok_cc.company = company
			blok_cc.is_group = 0
			blok_cc.flags.ignore_permissions = True
			blok_cc.insert()
			frappe.db.commit()

	def set_periode_bjr(self):
		if self.bulan and self.tahun:
			bulan_angka = BULAN_MAP.get(self.bulan)
			if bulan_angka:
				# Format: YYYY-MM-DD HH:MM:SS (format internal ERPNext)
				self.periode_bjr = "{}-{:02d}-01 00:00:00".format(
					int(self.tahun), bulan_angka
				)


@frappe.whitelist()
def naikkan_ke_tm(blok_name):
	blok = frappe.get_doc("Blok", blok_name)

	if blok.get("workflow_state") != "TBM":
		frappe.throw("Blok ini tidak dalam status TBM.")

	if not blok.tahun_tanam or not blok.unit:
		frappe.throw("Tahun Tanam dan Unit harus diisi.")

	blok_list = frappe.get_all("Blok", filters={
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
		"workflow_state": "TBM",
	}, fields=["name", "blok"])

	if not blok_list:
		frappe.throw("Tidak ada Blok TBM yang dapat dinaikkan.")

	unit_doc = frappe.get_doc("Unit", blok.unit)
	company = unit_doc.company
	company_abbr = frappe.db.get_value("Company", company, "abbr")

	if not blok.cost_center:
		frappe.throw("Cost Center belum diatur pada Blok ini.")

	# total = frappe.db.sql("""
	# 	SELECT COALESCE(SUM(debit) - SUM(credit), 0)
	# 	FROM `tabGL Entry`
	# 	WHERE cost_center = %s
	# 	  AND is_cancelled = 0
	# """, (blok.cost_center,))[0][0] or 0

	total = frappe.db.sql("""
		SELECT COALESCE(SUM(debit), 0)
		FROM `tabGL Entry`
		WHERE cost_center = %s
		  AND is_cancelled = 0
	""", (blok.cost_center,))[0][0] or 0

	debit_account = frappe.db.get_value("Account", {
		"account_number": "1271301",
		"company": company,
	}, "name")
	credit_account = frappe.db.get_value("Account", {
		"account_number": "1273005",
		"company": company,
	}, "name")

	if not debit_account:
		frappe.throw(f"Akun 1271301 tidak ditemukan untuk company {company}.")
	if not credit_account:
		frappe.throw(f"Akun 1273005 tidak ditemukan untuk company {company}.")

	for b in blok_list:
		frappe.db.set_value("Blok", b.name, "workflow_state", "TM", update_modified=False)

		blok_cc = frappe.db.get_value(
			"Cost Center",
			{"cost_center_name": b.blok, "company": company},
			"name"
		)
		if not blok_cc:
			new_cc = frappe.new_doc("Cost Center")
			new_cc.cost_center_name = b.blok
			new_cc.parent_cost_center = f"Blok - {company_abbr}"
			new_cc.company = company
			new_cc.is_group = 0
			new_cc.flags.ignore_permissions = True
			new_cc.insert()
			frappe.db.commit()
			blok_cc = new_cc.name

		frappe.db.set_value("Blok", b.name, "cost_center", blok_cc, update_modified=False)

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.posting_date = today()
	je.company = company
	je.user_remark = f"Naik TM - Tahun Tanam {blok.tahun_tanam} Unit {blok.unit}"

	je.append("accounts", {
		"account": debit_account,
		"debit_in_account_currency": total,
		"credit_in_account_currency": 0,
		"cost_center": blok.cost_center,
	})
	je.append("accounts", {
		"account": credit_account,
		"debit_in_account_currency": 0,
		"credit_in_account_currency": total,
		"cost_center": blok.cost_center,
	})

	je.flags.ignore_permissions = True
	je.insert()
	je.submit()

	frappe.db.commit()

	return {
		"blok_diproses": len(blok_list),
		"journal_entry": je.name,
		"total": total,
	}


@frappe.whitelist()
def preview_naikkan_ke_tm(blok_name):
	blok = frappe.get_doc("Blok", blok_name)

	blok_list = frappe.get_all("Blok", filters={
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
		"workflow_state": "TBM",
	}, fields=["name"])

	# total = frappe.db.sql("""
	# 	SELECT COALESCE(SUM(debit) - SUM(credit), 0)
	# 	FROM `tabGL Entry`
	# 	WHERE cost_center = %s
	# 	  AND is_cancelled = 0
	# """, (blok.cost_center,))[0][0] or 0

	total = frappe.db.sql("""
		SELECT COALESCE(SUM(debit), 0)
		FROM `tabGL Entry`
		WHERE cost_center = %s
		  AND is_cancelled = 0
	""", (blok.cost_center,))[0][0] or 0

	unit_doc = frappe.get_doc("Unit", blok.unit)
	company = unit_doc.company

	debit_account = frappe.db.get_value("Account", {"account_number": "1271301", "company": company}, "name") or "1271301 - TANAMAN MENGHASILKAN"
	credit_account = frappe.db.get_value("Account", {"account_number": "1273005", "company": company}, "name") or "1273005 - ASET DALAM PENYELESAIAN - LAINNYA"

	return {
		"jumlah_blok": len(blok_list),
		"total": total,
		"debit_account": debit_account,
		"credit_account": credit_account,
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
	}


@frappe.whitelist()
def kembalikan_ke_tbm(blok_name):
	blok = frappe.get_doc("Blok", blok_name)

	if blok.get("workflow_state") != "TM":
		frappe.throw("Blok ini tidak dalam status TM.")

	if not blok.tahun_tanam or not blok.unit:
		frappe.throw("Tahun Tanam dan Unit harus diisi.")

	# Cari JE yang dibuat saat naik TM (ambil yang terbaru)
	result = frappe.db.sql("""
		SELECT name FROM `tabJournal Entry`
		WHERE user_remark = %s AND docstatus = 1
		ORDER BY creation DESC LIMIT 1
	""", (f"Naik TM - Tahun Tanam {blok.tahun_tanam} Unit {blok.unit}",))

	if not result:
		frappe.throw("Journal Entry terkait tidak ditemukan. Pastikan Journal Entry Naik TM belum dibatalkan.")

	je_name = result[0][0]

	je = frappe.get_doc("Journal Entry", je_name)
	je.flags.ignore_permissions = True
	je.cancel()

	blok_list = frappe.get_all("Blok", filters={
		"tahun_tanam": blok.tahun_tanam,
		"unit": blok.unit,
		"workflow_state": "TM",
	}, fields=["name"])

	for b in blok_list:
		frappe.db.set_value("Blok", b.name, "workflow_state", "TBM", update_modified=False)

	frappe.db.commit()

	return {
		"blok_diproses": len(blok_list),
		"journal_entry": je_name,
	}
