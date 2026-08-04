import frappe
from frappe.model.delete_doc import check_if_doc_is_dynamically_linked, check_if_doc_is_linked
from frappe.utils import flt

DOCTYPE = "Surat Pengantar Buah"
CHILD = "SPB Timbangan Pabrik"


def execute():
	"""Panggilan API barengan pernah bikin SPB kembar untuk trans_no yang sama.
	Gabungkan detailnya ke satu SPB supaya trans_no bisa dijadikan unique."""
	trans_nos = frappe.db.sql(
		"""
		SELECT trans_no
		FROM `tabSurat Pengantar Buah`
		WHERE IFNULL(trans_no, '') != ''
		GROUP BY trans_no
		HAVING COUNT(*) > 1
		""",
		pluck=True,
	)

	if not trans_nos:
		return

	merged, manual = [], []

	for trans_no in trans_nos:
		try:
			ok = _merge_group(trans_no)
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title=f"SPB kembar {trans_no}: gagal digabung",
				message=frappe.get_traceback(),
			)
			# tetap lepas trans_no yang bentrok, kalau tidak unique index gagal dibuat
			_keep_trans_no_on_oldest(trans_no)
			ok = False

		frappe.db.commit()
		(merged if ok else manual).append(trans_no)

	print(f"SPB kembar: {len(merged)} trans_no digabung, {len(manual)} perlu dicek manual")
	if manual:
		print("  perlu dicek manual: " + ", ".join(manual))


def _merge_group(trans_no):
	rows = frappe.get_all(
		DOCTYPE,
		filters={"trans_no": trans_no},
		fields=["name", "docstatus"],
		order_by="creation asc",
	)

	# dokumen batal tidak ikut digabung, tapi trans_no-nya tetap harus dilepas
	for row in rows:
		if row.docstatus == 2:
			_clear_trans_no(row.name)

	active = [row.name for row in rows if row.docstatus != 2]
	if len(active) < 2:
		return True

	linked = [name for name in active if _has_references(name)]

	if len(linked) > 1:
		# dua-duanya sudah dipakai dokumen turunan (WB/Timbangan/Sortasi/SCP),
		# menggabungkan otomatis bisa merusak angka timbangan
		_keep_trans_no_on_oldest(trans_no)
		return False

	keeper = linked[0] if linked else active[0]
	_merge_into(keeper, [name for name in active if name != keeper])

	return True


def _merge_into(keeper, losers):
	keeper_doc = frappe.get_doc(DOCTYPE, keeper)
	seen = {_row_key(row) for row in keeper_doc.details}
	idx = len(keeper_doc.details)
	recaps = set(_recap_names(keeper_doc.details))

	for loser in losers:
		loser_doc = frappe.get_doc(DOCTYPE, loser)
		recaps.update(_recap_names(loser_doc.details))

		for row in loser_doc.details:
			key = _row_key(row)
			if key in seen:
				# baris yang sama sudah ada di keeper, ikut terhapus bersama losernya
				continue

			seen.add(key)
			idx += 1
			frappe.db.set_value(
				CHILD,
				row.name,
				{
					"parent": keeper,
					"parenttype": DOCTYPE,
					"parentfield": "details",
					"docstatus": keeper_doc.docstatus,
					"idx": idx,
				},
				update_modified=False,
			)

		_empty_loser(loser_doc)

	_recalculate(keeper)

	for recap in recaps:
		try:
			frappe.get_doc("Recap Panen by Blok", recap).calculate_transfered_weight()
		except Exception:
			frappe.log_error(
				title=f"Recap Panen {recap}: gagal hitung ulang",
				message=frappe.get_traceback(),
			)


def _empty_loser(doc):
	_clear_trans_no(doc.name)
	frappe.db.set_value(
		DOCTYPE,
		doc.name,
		{"total_janjang": 0, "total_brondolan": 0, "total_weight": 0, "bjr": 0},
		update_modified=False,
	)

	# draft cuma dokumen hantu hasil bug, buang saja (masuk ke Deleted Document).
	# yang sudah submit dibiarkan kosong supaya jejaknya bisa ditinjau.
	if doc.docstatus == 0:
		frappe.delete_doc(DOCTYPE, doc.name, ignore_permissions=True)


def _recalculate(name):
	doc = frappe.get_doc(DOCTYPE, name)
	doc.total_janjang = sum(flt(d.total_janjang) for d in doc.details)
	doc.total_brondolan = sum(flt(d.brondolan_terkirim) for d in doc.details)

	values = {"total_janjang": doc.total_janjang, "total_brondolan": doc.total_brondolan}

	# janjang berubah, jadi bjr dan pembagian berat per blok ikut basi
	if doc.total_janjang and (doc.in_weight or doc.in_weight_internal):
		try:
			doc._calculate_weight()
		except Exception:
			frappe.log_error(
				title=f"SPB {name}: gagal hitung ulang berat",
				message=frappe.get_traceback(),
			)
		else:
			values.update({
				"total_weight": doc.total_weight,
				"bjr": doc.bjr,
				"total_weight_internal": doc.total_weight_internal,
				"bjr_internal": doc.bjr_internal,
			})
			for d in doc.details:
				frappe.db.set_value(CHILD, d.name, "total_weight", d.total_weight, update_modified=False)

	frappe.db.set_value(DOCTYPE, name, values, update_modified=False)


def _has_references(name):
	doc = frappe.get_doc(DOCTYPE, name)

	for check in (check_if_doc_is_linked, check_if_doc_is_dynamically_linked):
		try:
			check(doc)
		except frappe.LinkExistsError:
			return True

	return False


def _keep_trans_no_on_oldest(trans_no):
	names = frappe.get_all(DOCTYPE, filters={"trans_no": trans_no}, pluck="name", order_by="creation asc")
	for name in names[1:]:
		_clear_trans_no(name)


def _clear_trans_no(name):
	frappe.db.set_value(DOCTYPE, name, "trans_no", None, update_modified=False)


def _row_key(row):
	if row.harvest_no:
		return ("harvest_no", row.harvest_no)

	return ("blok", row.blok, str(row.panen_date), row.blok_restan, str(row.panen_date_restan))


def _recap_names(rows):
	for row in rows:
		for field in ("recap_panen", "recap_panen_restan"):
			if row.get(field):
				yield row.get(field)
