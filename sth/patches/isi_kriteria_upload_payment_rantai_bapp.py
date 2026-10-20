import frappe

from sth.finance_sth.custom.cek_kriteria_upload_pe import (
	generate_kriteria_upload_payment,
	get_kriteria_rows_for_reference,
)

# label document_type baris yang baru ikut sejak commit da0a5755
LABEL_RANTAI_BAPP = ("Proposal", "SPK", "BAPP")


def execute(payment_entry=None, dry_run=True):
	"""Bangun ulang Kriteria Upload Payment PV lama yang membayar PINV dari BAPP.

	Sejak commit da0a5755 berkas Proposal, SPK (Project) dan BAPP di belakang
	PINV ikut ditarik ke Kriteria Upload Payment. Tabel itu cuma dibangun ulang
	waktu Payment Entry disimpan, jadi PV yang dibuat sebelumnya belum memuatnya
	sampai disimpan lagi. Patch ini menjalankan pembangun yang sama untuk PV
	tersebut tanpa menyimpan Payment Entry-nya.

	Yang diproses PV draft dan submitted yang salah satu referensinya Purchase
	Invoice dengan item ber-BAPP. PV realisasi PDO dilewati: tabelnya diisi
	generate_kriteria_upload_payment_pdo dan akan tertimpa kalau dibangun lewat
	jalur ini.

	Default-nya dry run, cuma mencetak berapa baris rantai BAPP yang akan
	masuk per PV. Tulis dengan --kwargs "{'dry_run': 0}".
	"""
	filters = ""
	if payment_entry:
		filters = "and per.parent = %(payment_entry)s"

	daftar = frappe.db.sql_list(f"""
		select distinct per.parent
		from `tabPayment Entry Reference` per
		join `tabPurchase Invoice Item` pii on pii.parent = per.reference_name
		where per.reference_doctype = 'Purchase Invoice'
			and per.docstatus < 2
			and ifnull(pii.bapp, '') != ''
			{filters}
		order by per.parent
	""", {"payment_entry": payment_entry})

	diproses = dilewati = 0

	for name in daftar:
		doc = frappe.get_doc("Payment Entry", name)

		if doc.get("payment_voucher_kas_pdo"):
			print(f"{name}: dilewati, PV realisasi PDO")
			dilewati += 1
			continue

		baru = [
			row
			for ref in doc.references
			for row in get_kriteria_rows_for_reference(ref.reference_doctype, ref.reference_name)
			if row["document_type"] in LABEL_RANTAI_BAPP
		]

		if not baru:
			print(f"{name}: dilewati, rantai BAPP belum punya berkas")
			dilewati += 1
			continue

		print(f"{name}: {len(baru)} baris Proposal/SPK/BAPP")
		diproses += 1

		if not dry_run:
			# commit sendiri per dokumen
			generate_kriteria_upload_payment(doc)

	print(f"{'Dry run: ' if dry_run else ''}{diproses} PV diproses, {dilewati} dilewati")
