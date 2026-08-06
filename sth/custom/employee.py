import frappe

def autoname_employee(self,method):
	self.finger_id = self.no_ktp[:14]
	self.name = self.no_ktp

<<<<<<< Updated upstream

def set_coa_stasiun(self, method=None):
	"""Isi COA Stasiun dari Station Procurement Settings sesuai company karyawan.

	Dipasang di server supaya data yang masuk lewat import atau API ikut terisi,
	bukan hanya yang diinput dari form.
	"""
	if not self.get("stasiun"):
		self.coa_stasiun = None
		return

	self.coa_stasiun = frappe.db.get_value(
		"Station Procurement Settings",
		{
			"parent": self.stasiun,
			"parenttype": "Station Master",
			"parentfield": "station_procurement_settings",
			"company": self.company,
		},
		"account",
	)
=======
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_stasiun_by_unit(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""
		SELECT
			sm.name,
			sm.machine_name
		FROM `tabDetail Station Master` dsm
		INNER JOIN `tabStation Master` sm
			ON sm.name = dsm.parent
		WHERE
			dsm.unit = %(unit)s
			AND sm.machine_name LIKE %(txt)s
		ORDER BY sm.machine_name
		LIMIT %(start)s, %(page_len)s
	""", {
		"unit": filters.get("unit"),
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})
 
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_account_by_station_and_company(doctype, txt, searchfield, start, page_len, filters):
	return frappe.db.sql("""
		SELECT
			ca.name
		FROM `tabStation Procurement Settings` sps
		INNER JOIN `tabStation Master` sm
			ON sm.name = sps.parent
		INNER JOIN `tabAccount` a
			ON a.name = sps.account
		INNER JOIN `tabAccount` ca
			ON ca.parent_account = a.name
		WHERE
			sm.name = %(station)s
			AND sps.company = %(company)s
			AND ca.name LIKE '%%OPERASIONAL%%'
			AND ca.name LIKE %(txt)s
		ORDER BY ca.name
		LIMIT %(start)s, %(page_len)s
	""", {
		"station": filters.get("station"),
		"company": filters.get("company"),
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})
>>>>>>> Stashed changes
