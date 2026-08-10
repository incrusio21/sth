import frappe
from frappe.utils import cint, flt


def execute():
	"""Isi Persentase Discrap untuk pengajuan scrap yang dibuat waktu inputnya
	masih qty. Rasionya diambil dari qty supaya nilai yang sudah disetujui tidak
	berubah; pengajuan tanpa qty berarti scrap penuh."""
	if not frappe.db.has_column("Asset Scrap Request", "persentase_scrap"):
		return

	pengajuan = frappe.get_all(
		"Asset Scrap Request",
		filters={"persentase_scrap": ["in", [0, None]]},
		fields=["name", "qty_scrap", "asset_quantity"],
	)

	for baris in pengajuan:
		total = cint(baris.asset_quantity) or 1
		qty = cint(baris.qty_scrap)

		persentase = 100 if not qty or qty >= total else flt(qty * 100 / total, 2)

		frappe.db.set_value(
			"Asset Scrap Request",
			baris.name,
			"persentase_scrap",
			persentase,
			update_modified=False,
		)
