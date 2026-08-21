import frappe


def execute():
	"""Matikan Book Advance Payments in Separate Party Account di semua Company.

	Fitur bawaan ERPNext ini tidak terpakai di sini. Uang muka Purchase Order
	dibukukan ke akun dari Procurement Settings lewat set_paid_to_uang_muka_po(),
	dan uang muka yang menempel di tagihan dijurnal di dalam Purchase Invoice
	lewat tabel advances.

	Selama flag-nya menyala, make_advance_gl_entries menambah sepasang jurnal
	rekonsiliasi uang muka di setiap pembayaran Purchase Invoice. paid_to
	pembayaran tagihan sama dengan akun hutang di baris reference, jadi pasangan
	itu jatuh di akun yang sama dan cuma saling menghapus: nettonya benar tapi
	buku besarnya jadi empat baris untuk satu pembayaran.

	Akun uang muka default sengaja tidak ikut dikosongkan supaya setelan ini bisa
	dinyalakan lagi tanpa mencarikan akunnya dari awal.

	Payment Entry yang sudah tersubmit tidak disentuh. Flag di dokumennya yang
	menentukan bentuk pembalikan jurnal waktu dibatalkan, jadi yang jurnalnya
	terlanjur empat baris harus tetap membalik empat baris juga.
	"""
	companies = frappe.get_all(
		"Company",
		filters={"book_advance_payments_in_separate_party_account": 1},
		pluck="name",
	)

	if not companies:
		return

	for company in companies:
		frappe.db.set_value(
			"Company", company, "book_advance_payments_in_separate_party_account", 0
		)

	print("Uang muka di akun terpisah dimatikan di Company: " + ", ".join(companies))
