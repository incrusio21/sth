import frappe
from frappe import _
from frappe.model import no_value_fields, table_fields
from frappe.model.workflow import get_workflow
from frappe.utils import cint, cstr, flt, get_datetime, getdate, strip_html_tags

STATE_APPROVED = "Approved"
STATE_PERSETUJUAN_1 = "Butuh Persetujuan 1"

FIELD_TEKS_HTML = ("Text Editor", "HTML Editor")


def kembali_ke_persetujuan_1(doc, method=None):
	"""Data master yang sudah Approved lalu diubah harus disetujui ulang.

	Dipasang di validate Item dan Supplier. Kalau dokumennya tersimpan berstate
	Approved dan isinya berubah, state-nya kembali ke Butuh Persetujuan 1, dan
	field yang diisi workflow untuk state itu ikut diisi - di Item artinya status
	jadi Non Aktif, sama seperti transisi Disable. Frappe tidak mengisinya sendiri
	karena update_field cuma dijalankan apply_workflow, bukan save biasa.

	Perpindahan dari Approved ke Butuh Persetujuan 1 tetap diperiksa
	validate_workflow sesudah ini, jadi workflow-nya harus punya transisi itu
	untuk role penggunanya (di Item: Disable, role All).

	Save yang mengubah state-nya sendiri adalah aksi workflow, bukan suntingan
	data, dan dibiarkan. Doctype yang workflow-nya tidak punya state Butuh
	Persetujuan 1 juga dilewati.
	"""
	if doc.is_new() or frappe.flags.in_patch or frappe.flags.in_migrate or frappe.flags.in_install:
		return

	if not doc.meta.get_workflow():
		return

	workflow = get_workflow(doc.doctype)
	field_state = workflow.workflow_state_field

	sebelum = doc.get_doc_before_save()
	if not sebelum or sebelum.get(field_state) != STATE_APPROVED:
		return

	if doc.get(field_state) != STATE_APPROVED:
		return

	state = next((s for s in workflow.states if s.state == STATE_PERSETUJUAN_1), None)
	if not state:
		return

	berubah = field_berubah(doc, sebelum, abaikan={field_state})
	if not berubah:
		return

	doc.set(field_state, STATE_PERSETUJUAN_1)
	if state.update_field:
		doc.set(state.update_field, state.update_value)

	frappe.msgprint(
		_("Data {0} yang sudah Approved berubah ({1}), jadi state-nya kembali ke {2}.").format(
			_(doc.doctype), ", ".join(berubah[:5]) + (", ..." if len(berubah) > 5 else ""), STATE_PERSETUJUAN_1
		),
		alert=True,
		indicator="orange",
	)


def field_berubah(doc, sebelum, abaikan=()):
	"""Label field yang nilainya berbeda dari versi tersimpan, termasuk isi tabel anak.

	Field read only dan hidden tidak dihitung: nilainya diisi kode (fetch_from,
	perhitungan, update_field workflow), bukan suntingan pengguna, dan bisa
	bergeser sendiri tiap save.
	"""
	berubah = []

	for df in doc.meta.fields:
		if df.fieldname in abaikan or not dibandingkan(df):
			continue

		if df.fieldtype in table_fields:
			lama = [isi_baris(row) for row in sebelum.get(df.fieldname) or []]
			baru = [isi_baris(row) for row in doc.get(df.fieldname) or []]
		else:
			lama = nilai(df, sebelum.get(df.fieldname))
			baru = nilai(df, doc.get(df.fieldname))

		if lama != baru:
			berubah.append(_(df.label or df.fieldname))

	return berubah


def dibandingkan(df):
	if df.read_only or df.hidden:
		return False

	return df.fieldtype in table_fields or df.fieldtype not in no_value_fields


def isi_baris(row):
	return tuple(
		nilai(df, row.get(df.fieldname))
		for df in row.meta.fields
		if dibandingkan(df) and df.fieldtype not in table_fields
	)


def nilai(df, value):
	"""Nilai yang bisa dibandingkan antara versi database dan kiriman form.

	Dari database tanggal datang sebagai date dan angka sebagai float, dari form
	sebagai string; kosong bisa None, "" atau 0. Text Editor dibandingkan teksnya
	saja, karena editornya membungkus ulang HTML waktu form dibuka.
	"""
	if df.fieldtype in ("Float", "Currency", "Percent"):
		return flt(value)

	if df.fieldtype in ("Int", "Check"):
		return cint(value)

	if value in (None, ""):
		return None

	if df.fieldtype == "Date":
		return getdate(value)

	if df.fieldtype == "Datetime":
		return get_datetime(value)

	if df.fieldtype in FIELD_TEKS_HTML:
		return " ".join(strip_html_tags(cstr(value)).split()) or None

	return cstr(value)
