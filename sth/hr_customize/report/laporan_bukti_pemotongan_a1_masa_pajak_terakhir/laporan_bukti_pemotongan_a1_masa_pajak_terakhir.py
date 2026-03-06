# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	conditions = get_condition(filters)
	columns = get_columns(filters)
	data = [
		{
			"pemberi_kerja_selanjutnya": "test"
		}
	]

	return columns, data

def get_condition(filters):
	conditions = ""

	if filters.get("company"):
		conditions += " AND pi.company = %(company)s"

	return conditions

def get_columns(filters):
	columns = [
		{
			"label": _("Pemberi Kerja Selanjutnya"),
			"fieldtype": "Data",
			"fieldname": "pemberi_kerja_selanjutnya",
		},
		{
			"label": _("Masa Pajak Awal"),
			"fieldtype": "Data",
			"fieldname": "masa_pajak_awal",
		},
		{
			"label": _("Masa Pajak Akhir"),
			"fieldtype": "Data",
			"fieldname": "masa_pajak_akhir",
		},
		{
			"label": _("Tahun Pajak"),
			"fieldtype": "Data",
			"fieldname": "tahun_pajak",
		},
		{
			"label": _("WNI/WNA"),
			"fieldtype": "Data",
			"fieldname": "wni_wna",
		},
		{
			"label": _("No. Paspor"),
			"fieldtype": "Data",
			"fieldname": "no_paspor",
		},
		{
			"label": _("NPWP"),
			"fieldtype": "Data",
			"fieldname": "npwp",
		},
		{
			"label": _("Status PTKP"),
			"fieldtype": "Data",
			"fieldname": "status_ptkp",
		},
		{
			"label": _("Posisi"),
			"fieldtype": "Data",
			"fieldname": "posisi",
		},
		{
			"label": _("Kode Objek Pajak"),
			"fieldtype": "Data",
			"fieldname": "kode_objek_pajak",
		},
		{
			"label": _("Status Bukti Potong"),
			"fieldtype": "Data",
			"fieldname": "status_bukti_potong",
		},
		{
			"label": _("Jumlah Bulan Bekerja"),
			"fieldtype": "Data",
			"fieldname": "jumlah_bulan_bekerja",
		},
		{
			"label": _("Gaji"),
			"fieldtype": "Currency",
			"fieldname": "gaji",
		},
		{
			"label": _("Opsi Gross Up"),
			"fieldtype": "Data",
			"fieldname": "Opsi_gross_up",
		},
		{
			"label": _("Tunjangan PPh"),
			"fieldtype": "Data",
			"fieldname": "tunjangan_pph",
		},
		{
			"label": _("Tunjangan Lainnya / Lembur"),
			"fieldtype": "Data",
			"fieldname": "tunjangan_lainnya_lembur",
		},
		{
			"label": _("Honorarium"),
			"fieldtype": "Data",
			"fieldname": "honarorium",
		},
		{
			"label": _("Asuransi"),
			"fieldtype": "Data",
			"fieldname": "asuransi",
		},
		{
			"label": _("Natura"),
			"fieldtype": "Data",
			"fieldname": "natura",
		},
		{
			"label": _("Tantiem, Bonus, Gratifikasi, THR"),
			"fieldtype": "Data",
			"fieldname": "tantiem_bonus_gratifikasi_thr",
		},
		{
			"label": _("Iuran Pensiun atau Biaya THT/JHT"),
			"fieldtype": "Data",
			"fieldname": "iuran_pensiun_atau_biaya_tht_jht",
		},
		{
			"label": _("Zakat"),
			"fieldtype": "Data",
			"fieldname": "zakat",
		},
		{
			"label": _("Nomor Bukti Potong Sebelumnya"),
			"fieldtype": "Data",
			"fieldname": "nomor_bukti_potong_sebelumnya",
		},
		{
			"label": _("Fasilitas Pajak"),
			"fieldtype": "Data",
			"fieldname": "fasilitas_pajak",
		},
		{
			"label": _("PPh Pasal 21*"),
			"fieldtype": "Data",
			"fieldname": "pph_pasal_21",
		},
		{
			"label": _("ID TKU Pemotong"),
			"fieldtype": "Data",
			"fieldname": "id_tku_pemotong",
		},
		{
			"label": _("Tanggal Pemotongan"),
			"fieldtype": "Data",
			"fieldname": "tanggal_pemotongan",
		},
	]

	return columns
