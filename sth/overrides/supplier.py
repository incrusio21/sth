
import frappe
from erpnext.buying.doctype.supplier.supplier import Supplier
from frappe import _

class Supplier(Supplier):    
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.accounts.doctype.allowed_to_transact_with.allowed_to_transact_with import AllowedToTransactWith
		from erpnext.accounts.doctype.party_account.party_account import PartyAccount
		from erpnext.utilities.doctype.portal_user.portal_user import PortalUser
		from frappe.types import DF

		accounts: DF.Table[PartyAccount]
		allow_purchase_invoice_creation_without_purchase_order: DF.Check
		allow_purchase_invoice_creation_without_purchase_receipt: DF.Check
		companies: DF.Table[AllowedToTransactWith]
		country: DF.Link | None
		default_bank_account: DF.Link | None
		default_currency: DF.Link | None
		default_price_list: DF.Link | None
		disabled: DF.Check
		email_id: DF.ReadOnly | None
		hold_type: DF.Literal["", "All", "Invoices", "Payments"]
		image: DF.AttachImage | None
		is_frozen: DF.Check
		is_internal_supplier: DF.Check
		is_transporter: DF.Check
		language: DF.Link | None
		mobile_no: DF.ReadOnly | None
		naming_series: DF.Literal["SUP-.YYYY.-"]
		on_hold: DF.Check
		payment_terms: DF.Link | None
		portal_users: DF.Table[PortalUser]
		prevent_pos: DF.Check
		prevent_rfqs: DF.Check
		primary_address: DF.Text | None
		release_date: DF.Date | None
		represents_company: DF.Link | None
		supplier_details: DF.Text | None
		supplier_group: DF.Link | None
		supplier_name: DF.Data
		supplier_primary_address: DF.Link | None
		supplier_primary_contact: DF.Link | None
		supplier_type: DF.Literal["Company", "Individual", "Partnership", "Aktif", "Tidak Aktif"]
		tax_category: DF.Link | None
		tax_id: DF.Data | None
		tax_withholding_category: DF.Link | None
		warn_pos: DF.Check
		warn_rfqs: DF.Check
		website: DF.Data | None
	# end: auto-generated types
	def autoname(self):
		if not self.kode_supplier:
			self.kode_supplier = self.generate_supplier_code()
			self.name = self.kode_supplier
		else:
			self.name = self.kode_supplier
	
	def generate_supplier_code(self):
		from datetime import datetime
		
		year_month = datetime.now().strftime("%Y%m")
		prefix = f"SUPP-{year_month}-"
		
		last_item = frappe.db.sql("""
			SELECT name 
			FROM `tabSupplier` 
			WHERE name LIKE %s 
			ORDER BY name DESC 
			LIMIT 1
		""", (prefix + "%",))
		
		if last_item:
			last_code = last_item[0][0]
			last_number = int(last_code.split('-')[-1])
			new_number = last_number + 1
		else:
			new_number = 1
		
		return f"{prefix}{new_number:05d}"

@frappe.whitelist()
def get_next_supplier():
	from datetime import datetime
		
	year_month = datetime.now().strftime("%Y%m")
	prefix = f"SUPP-{year_month}-"
	
	last_item = frappe.db.sql("""
		SELECT name 
		FROM `tabSupplier` 
		WHERE name LIKE %s 
		ORDER BY name DESC 
		LIMIT 1
	""", (prefix + "%",))
	
	if last_item:
		last_code = last_item[0][0]
		last_number = int(last_code.split('-')[-1])
		new_number = last_number + 1
	else:
		new_number = 1
	
	return f"{prefix}{new_number:05d}"


def validate_supplier_name(doc, method):

	if not doc.supplier_name:
		return
	
	existing_suppliers = frappe.db.sql("""
		SELECT name 
		FROM `tabSupplier` 
		WHERE LOWER(supplier_name) = LOWER(%s) 
		AND name != %s
	""", (doc.supplier_name, doc.name or ''))
	
	if existing_suppliers:
		frappe.throw(
			_("Supplier with name '{0}' already exists: {1}").format(
				doc.supplier_name, 
				existing_suppliers[0][0]
			),
			title=_("Duplicate Supplier Name")
		)

def validate_no_rekening(doc,method):
	if not doc.data_bank_supplier:
		return

	# cek yang baru - baru
	lokal_list = []
	for row in doc.data_bank_supplier:
		if row.no_rekening not in lokal_list:
			lokal_list.append(row.no_rekening)
		else:
			frappe.throw(
				_("Supplier with No Rekening '{0}' already exists: {1}").format(
					row.no_rekening, 
					doc.kode_supplier
				),
				title=_("Duplicate Rekening Name")
			)

	list_sppkp  = frappe.db.sql("""
		SELECT no_rekening, name, parent
		FROM `tabData Bank Supplier` 
		WHERE no_rekening IS NOT NULL and no_rekening != ""
	""",)		

	for row in doc.data_bank_supplier:
		if row.no_rekening:
			for satu_sppkp in list_sppkp:
				if satu_sppkp[0] == row.no_rekening and row.name != satu_sppkp[1]:
					frappe.throw(
						_("Supplier with No Rekening '{0}' already exists: {1}").format(
							row.no_rekening, 
							satu_sppkp[2]
						),
						title=_("Duplicate Rekening Name")
					)


def validate_sppkp_name(doc, method):

	if not doc.npwp_dan_sppkp_supplier:
		return

	# cek yang baru - baru
	lokal_list = []
	for row in doc.npwp_dan_sppkp_supplier:
		if row.no_sppkp not in lokal_list:
			lokal_list.append(row.no_sppkp)
		else:
			frappe.throw(
				_("Supplier with SPPKP Name '{0}' already exists: {1}").format(
					row.no_sppkp, 
					doc.kode_supplier
				),
				title=_("Duplicate SPPKP Name")
			)

	list_sppkp  = frappe.db.sql("""
		SELECT no_sppkp, parent
		FROM `tabNPWP dan SPPKP Supplier` 
		WHERE no_sppkp IS NOT NULL and no_sppkp != "" and parent != %s
	""", (doc.name or ''))		

	for row in doc.npwp_dan_sppkp_supplier:
		if row.no_sppkp:
			for satu_sppkp in list_sppkp:
				if satu_sppkp[0] == row.no_sppkp:
					frappe.throw(
						_("Supplier with SPPKP '{0}' already exists: {1}").format(
							row.no_sppkp, 
							satu_sppkp[1]
						),
						title=_("Duplicate SPPKP Name")
					)

def validate_ktp_name(doc, method):
	if not doc.ktp_supplier:
		return

	# cek yang baru - baru
	lokal_list = []
	for row in doc.ktp_supplier:
		if row.nik not in lokal_list:
			lokal_list.append(row.nik)
		else:
			frappe.throw(
				_("Supplier with NIK '{0}' already exists: {1}").format(
					row.nik, 
					doc.kode_supplier
				),
				title=_("Duplicate NIK KTP")
			)

	list_ktp  = frappe.db.sql("""
		SELECT nik, name, parent
		FROM `tabKTP Supplier` 
		WHERE nik IS NOT NULL and nik != ""
	""",)		

	for row in doc.ktp_supplier:
		if row.nik:
			for satu_ktp in list_ktp:
				if satu_ktp[0] == row.nik and row.name != satu_ktp[1]:
					frappe.throw(
						_("Supplier with NIK '{0}' already exists: {1}").format(
							row.nik, 
							satu_ktp[2]
						),
						title=_("Duplicate NIK KTP")
					)


def cek_upload(self, method):
	if not self.is_new():
		old_doc = self.get_doc_before_save()
		old_state = old_doc.get("status_supplier") if old_doc else None
		new_state = self.get("status_supplier")

		if "Calon Supplier" in old_state and old_state != new_state:
			# cek upload
			doc_upload = frappe.get_doc("Kriteria Upload Document",{"voucher_type":"Supplier","voucher_no":self.name})
			for row in doc_upload.file_upload:
				if not row.upload_file:
					frappe.throw("Upload File harus lengkap untuk Calon Supplier menjadi Supplier.")

def non_aktifkan_table(doc,method):
	aktif_rows = []
	
	for idx, row in enumerate(doc.struktur_supplier):
		if row.status_supplier == "Aktif":
			aktif_rows.append(idx)
	
	if len(aktif_rows) > 1:
		for idx in aktif_rows[:-1]:
			doc.struktur_supplier[idx].status_supplier = "Non Aktif"

	# aktif_rows = []
	
	# for idx, row in enumerate(doc.data_bank_supplier):
	# 	if row.status_bank == "Aktif":
	# 		aktif_rows.append(idx)
	
	# if len(aktif_rows) > 1:
	# 	for idx in aktif_rows[:-1]:
	# 		doc.data_bank_supplier[idx].status_bank = "Tidak Aktif"

	aktif_rows = []
	
	for idx, row in enumerate(doc.data_bank_supplier):
		if row.default == "Ya":
			aktif_rows.append(idx)
	
	if len(aktif_rows) > 1:
		for idx in aktif_rows[:-1]:
			doc.data_bank_supplier[idx].default = "Tidak"

	aktif_rows = []
	
	for idx, row in enumerate(doc.npwp_dan_sppkp_supplier):
		if row.status_npwp == "Aktif":
			aktif_rows.append(idx)
	
	if len(aktif_rows) > 1:
		for idx in aktif_rows[:-1]:
			doc.npwp_dan_sppkp_supplier[idx].status_npwp = "Tidak Aktif"

	aktif_rows = []
	
	for idx, row in enumerate(doc.alamat_dan_pic_supplier):
		if row.status_pic == "Aktif":
			aktif_rows.append(idx)
	
	if len(aktif_rows) > 1:
		for idx in aktif_rows[:-1]:
			doc.alamat_dan_pic_supplier[idx].status_pic = "Tidak Aktif"

	aktif_rows = []
	
	for idx, row in enumerate(doc.ktp_supplier):
		if row.status_ktp == "Aktif":
			aktif_rows.append(idx)
	
	if len(aktif_rows) > 1:
		for idx in aktif_rows[:-1]:
			doc.ktp_supplier[idx].status_ktp = "Non Aktif"

	aktif_rows = []
	
	for idx, row in enumerate(doc.pajak_supplier):
		if row.status_pajak == "Aktif":
			aktif_rows.append(idx)
	
	if len(aktif_rows) > 1:
		for idx in aktif_rows[:-1]:
			doc.pajak_supplier[idx].status_pajak = "Tidak Aktif"

	pajak_list = []
	for row in doc.pajak_supplier:
		if row.pajak:
			if row.pajak in pajak_list:
				frappe.throw(_("Row #{0}: Pajak '{1}' already exists in the table.").format(row.idx, row.pajak))
			pajak_list.append(row.pajak)

def update_supplier_email(doc,method):
	frappe.db.delete("Supplier Email",{"supplier": doc.name})

	for row in doc.struktur_supplier:
		frappe.get_doc({
			"doctype": "Supplier Email",
			"supplier": doc.name,
			"email": row.user_email
		}).insert()
			