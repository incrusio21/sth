# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.desk.reportview import get_filters_cond, get_match_cond
from erpnext.controllers.queries import get_fields

class SecurityCheckPoint(Document):

	def before_insert(self):
		self.keep_api_no_polisi()
		self.map_api_spb_trans_no()
		self.map_api_lokasi_pos()

	def validate(self):
		self.set_data_kendaraan()

	def is_from_api(self):
		"""Dokumen ini kiriman REST API, bukan input orang lewat UI."""
		return bool(self.owner and "api@sth" in self.owner)

	def keep_api_no_polisi(self):
		"""Simpan no polisi kiriman API sebelum fetch_from sempat menimpanya.

		Field no_polisi menarik nilai dari spb.no_polisi, jadi _validate_links()
		— yang jalan tepat setelah before_insert — selalu menggantinya dengan
		punya SPB. SPB kiriman API biasanya masih stub tanpa no polisi, jadi tanpa
		disimpan dulu nomornya hilang sebelum sempat dipakai mencari kendaraan.
		"""
		if not self.is_from_api():
			return

		self.flags.api_no_polisi = self.no_polisi

	def set_data_kendaraan(self):
		"""Isi data supir dan no polisi dari master Alat Berat Dan Kendaraan.

		Kiriman API cuma membawa no polisi; nama supirnya tidak ikut. Kendaraannya
		dicari lewat no_pol, operatornya dipakai sebagai driver_name, dan no_pol
		master ditulis balik ke no_polisi serta license_plate supaya formatnya ikut
		master, bukan format yang dikirim sistem luar.

		Dijalankan di validate, bukan before_insert, supaya nilainya tidak keburu
		ditimpa fetch_from spb.no_polisi di _validate_links().
		"""
		if not self.is_from_api():
			return

		no_polisi = self.flags.api_no_polisi or self.no_polisi

		if not no_polisi and not self.is_new():
			# Simpan ulang dokumen lama (mis. waktu kendaraan keluar) juga kena
			# fetch_from spb.no_polisi; pakai nilai yang sudah tersimpan supaya
			# nomornya tidak ikut terhapus.
			no_polisi = frappe.db.get_value(self.doctype, self.name, "no_polisi")

		if not no_polisi:
			return

		# No polisi yang tidak terdaftar tetap dicatat apa adanya supaya petugas pos
		# masih bisa mencocokkan kendaraannya di lapangan.
		self.no_polisi = no_polisi

		kendaraan = get_kendaraan_by_no_pol(no_polisi)
		if not kendaraan:
			return

		self.no_polisi = self.license_plate = kendaraan.no_pol

		if kendaraan.operator:
			self.driver_name = get_nama_operator(kendaraan.operator)

	def map_api_spb_trans_no(self):
		"""Field spb dari API berisi trans_no SPB, bukan nama dokumennya.

		Nilai asli disimpan di spb_trans_no, lalu spb diisi nama dokumen SPB supaya
		timbangan bisa menarik nomornya lewat Security Check Point ini
		(get_spb_available menyambung lewat scp.spb = spb.name).

		Dijalankan di before_insert, bukan validate, karena _validate_links()
		jalan lebih dulu daripada validate: selama field spb masih berisi
		trans_no di titik itu, insert ditolak "Could not find SPB".
		"""
		if not (self.owner and "api@sth" in self.owner and self.spb):
			return

		trans_no = self.spb

		self.spb_trans_no = trans_no
		self.spb = self.get_or_create_spb(trans_no)

	def map_api_lokasi_pos(self):
		"""Field lokasi_pos dari API berisi nama pos, bukan kode dokumennya.

		Security Location dinamai memakai kode (autoname field:kode), sementara
		sistem luar mengirim namanya — "POS PMKS". Tanpa diterjemahkan,
		_validate_links() menolak dokumennya "Could not find Lokasi POS".

		Nilai yang memang sudah berupa kode dibiarkan; begitu juga nama yang tidak
		terdaftar, supaya validasi Link yang menolaknya dan pesannya menyebut nama
		kiriman itu sendiri.

		Dijalankan di before_insert, bukan validate, karena _validate_links() jalan
		lebih dulu daripada validate.
		"""
		if not (self.is_from_api() and self.lokasi_pos):
			return

		if frappe.db.exists("Security Location", self.lokasi_pos):
			return

		kode = get_security_location_by_nama(self.lokasi_pos)
		if kode:
			self.lokasi_pos = kode

	def get_or_create_spb(self, trans_no):
		"""Nama dokumen SPB untuk trans_no ini, dibuatkan dulu kalau belum ada.

		SPB baru dibuat sebagai draft tanpa detail blok — cukup sebagai pegangan
		nomor buat timbangan. Data panennya menyusul lewat API SPB, yang memakai
		trans_no yang sama sehingga jatuh ke dokumen ini juga.
		"""
		spb_name = frappe.db.get_value("Surat Pengantar Buah", {"trans_no": trans_no}, "name")
		if spb_name:
			return spb_name

		from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import create_or_update

		doc = create_or_update(
			trans_no=trans_no,
			company=self.company,
			unit=self.unit,
			divisi=self.divisi,
			posting_date=self.tanggal_panen or self.posting_date,
		)

		return doc.name


def get_security_location_by_nama(nama):
	"""Kode Security Location yang namanya sama dengan `nama`.

	Dicocokkan persis dulu, baru tanpa beda huruf besar kecil dan tanpa spasi
	berlebih: sistem luar mengirim "POS PMKS" sementara di master bisa tertulis
	"Pos PMKS", padahal posnya sama.
	"""
	kode = frappe.db.get_value("Security Location", {"nama": nama}, "name")
	if kode:
		return kode

	rows = frappe.db.sql("""
		select name
		from `tabSecurity Location`
		where upper(trim(nama)) = %s
		limit 1
	""", strip_nama_pos(nama))

	return rows[0][0] if rows else None


def strip_nama_pos(nama):
	"""Bentuk ringkas nama pos: tanpa spasi berlebih, huruf besar."""
	return " ".join((nama or "").split()).upper()


def get_kendaraan_by_no_pol(no_polisi):
	"""Kendaraan di master yang no polisinya sama dengan no_polisi.

	Dicocokkan persis dulu, baru tanpa spasi dan tanda hubung: sistem luar mengirim
	"B 9165 UDB" sementara di master banyak yang ditulis "B9165UDB", padahal
	kendaraannya sama. Kendaraan yang sudah dibatalkan tidak ikut dicari.
	"""
	kendaraan = frappe.db.get_value(
		"Alat Berat Dan Kendaraan",
		{"no_pol": no_polisi, "docstatus": ["<", 2]},
		["name", "no_pol", "operator"],
		as_dict=True,
	)

	if kendaraan:
		return kendaraan

	rows = frappe.db.sql("""
		select name, no_pol, operator
		from `tabAlat Berat Dan Kendaraan`
		where docstatus < 2
			and upper(replace(replace(no_pol, ' ', ''), '-', '')) = %s
		limit 1
	""", strip_no_pol(no_polisi), as_dict=True)

	return rows[0] if rows else None


def strip_no_pol(no_polisi):
	"""Bentuk ringkas no polisi: tanpa spasi, tanpa tanda hubung, huruf besar."""
	return (no_polisi or "").replace(" ", "").replace("-", "").upper()


def get_nama_operator(operator):
	"""Nama karyawan yang jadi operator/supir kendaraan."""
	return frappe.db.get_value("Employee", operator, "employee_name")

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def delivery_order_query(doctype, txt, searchfield, start, page_len, filters):
	params = {"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len}
	fields = get_fields(doctype, ["name"])
	conditions = []
	scond = ""

	searchfields = frappe.get_meta(doctype).get_search_fields()
	searchfields = " or ".join(f"`tabDelivery Order`.{field} like %(txt)s" for field in searchfields)

	fields = [f"`tabDelivery Order`.{r}" for r in fields]
	fields = ", ".join(fields)
	
	if filters.get('driver'):
		scond += " AND dot.driver = %(driver)s"
		params["driver"] = filters.get('driver')
		filters.pop("driver")

	fcond = get_filters_cond(doctype, filters, conditions)

	
	return frappe.db.sql(f"""
		select {fields} from `tabDelivery Order`
		join `tabDelivery Order Transporter` dot on dot.parent = `tabDelivery Order`.name
		where (`tabDelivery Order`.name like %(txt)s or {searchfields}) {fcond} {scond}
		order by
			(case when locate(%(_txt)s, `tabDelivery Order`.name) > 0 then locate(%(_txt)s, `tabDelivery Order`.name) else 99999 end),
			`tabDelivery Order`.name
		limit %(page_len)s offset %(start)s
		""",params,debug=True
	)
