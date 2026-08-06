import frappe

def autoname_employee(self,method):
	self.finger_id = self.no_ktp[:14]
	self.name = self.no_ktp


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