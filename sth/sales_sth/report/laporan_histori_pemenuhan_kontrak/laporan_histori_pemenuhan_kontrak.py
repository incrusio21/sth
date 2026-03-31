import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
  return [
		{
			"fieldname": "kode_pt",
			"label": _("Kode PT"),
			"fieldtype": "Data",
			"width": 200
		},
		{
			"fieldname": "no_transaksi",
			"label": _("No Transaksi"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "tanggal",
			"label": _("Tanggal"),
			"fieldtype": "Date",
			"width": 150
		},
		{
			"fieldname": "no_kontrak",
			"label": _("No.Kontrak"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "no_sipb",
			"label": _("No. SIPB"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "no_sipb",
			"label": _("No. SIPB"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "no_do",
			"label": _("No. DO"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "kendaraan",
			"label": _("Kendaraan"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "nama_supir",
			"label": _("Nama Sopir"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "berat_bersih_pabrik",
			"label": _("Berat Bersih Pabrik"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "berat_bersih_pembeli",
			"label": _("Berat Bersih Pembeli"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "kontrak_nama_customer",
			"label": _("Kontrak Nama Customer"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "kontrak_harga_satuan",
			"label": _("Kontrak Harga Satuan"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "kontrak_nilai_per_truck",
			"label": _("Kontrak Nilai Per Truk"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "transportir_nama_customer",
			"label": _("Transportir Nama Customer"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "transportir_harga_satuan",
			"label": _("Transportir Harga Satuan"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "transportir_nilai_per_truck",
			"label": _("Transportir Nilai Per Truk"),
			"fieldtype": "Data",
			"width": 150
		},
		{
			"fieldname": "no_invoice",
			"label": _("No. Invoice"),
			"fieldtype": "Data",
			"width": 150
		},
	]

def get_data(filters):
  data = []
  conditions = get_condition(filters)
  
  query = frappe.db.sql("""
	SELECT 
	so.unit as kode_pt,
	t.name as no_transaksi,
	t.posting_date as tanggal,
	CASE
		WHEN so.no_kontrak_external IS NOT NULL THEN so.no_kontrak_external
		ELSE so.name
	END as no_kontrak,
	t.ticket_number as no_sipb,
	do.name as no_do,
	t.no_polisi as kendaraan,
	t.driver_name as nama_supir,
	t.netto_2 as berat_bersih_pabrik,
	0 as berat_bersih_pembeli,
	do.customer_name as kontrak_nama_customer,
	soi.rate as kontrak_harga_satuan,
	(t.netto_2 * soi.rate) as kontrak_nilai_per_truck,
	t.transportir as transportir_nama_customer,
	do.ongkos_angkut as transportir_harga_satuan,
	(t.netto_2 * do.ongkos_angkut) as transportir_nilai_per_truck,
	'' as no_invoice
	FROM `tabSales Order` as so
	JOIN `tabSales Order Item` as soi ON soi.parent = so.name
	JOIN `tabDelivery Order` as do ON do.sales_order = so.name
	JOIN `tabTimbangan` as t ON t.do_no = do.name
	WHERE so.docstatus = 1 {};
  """.format(conditions), filters, as_dict=True)
  
  for row in query:
    data.append(row)
  
  return data

def get_condition(filters):
	conditions = ""

	if filters.get("no_kontrak"):
		conditions += " AND so.name = %(no_kontrak)s"

	return conditions