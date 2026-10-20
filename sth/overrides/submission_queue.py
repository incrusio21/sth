import frappe
from frappe import _
from frappe.core.doctype.submission_queue.submission_queue import SubmissionQueue

# Doctype yang submit-nya terlalu berat untuk antrean bawaan Submission Queue
# (queue default, timeout 600 detik). Accounting Period memosting seluruh BKM
# Panen dan Perawatan satu unit sebulan lalu membangun empat costing, semuanya
# dalam satu transaksi; di request web itu habis dibunuh gunicorn. Doctype-nya
# dipindah ke antrean lewat property setter queue_in_background, dan di sini
# diberi antrean long dengan waktu yang cukup.
ANTREAN_PANJANG = {
	"Accounting Period": 3600,
}


class SthSubmissionQueue(SubmissionQueue):
	# Submit dobel tidak perlu dijaga di sini. Sampai job-nya mulai, queue_action
	# mengunci dokumen sumbernya (SubmissionQueue.lock menunjuk queued_doc), jadi
	# antrean kedua ditolak DocumentLockedError. Yang lolos sesudah job mulai
	# tertahan row lock check_if_latest lalu gagal sendiri karena dokumennya sudah
	# berubah.

	def after_insert(self):
		timeout = ANTREAN_PANJANG.get(self.ref_doctype)
		if not timeout:
			return super().after_insert()

		self.queue_action(
			"background_submission",
			to_be_queued_doc=self.queued_doc,
			action_for_queuing=self.action_for_queuing,
			queue="long",
			timeout=timeout,
			enqueue_after_commit=True,
		)

	def background_submission(self, to_be_queued_doc, action_for_queuing):
		super().background_submission(to_be_queued_doc, action_for_queuing)

		if self.ref_doctype in ANTREAN_PANJANG:
			self.sampaikan_kegagalan(to_be_queued_doc)

	def sampaikan_kegagalan(self, doc):
		"""Teruskan pesan penolakan aslinya ke user dan ke timeline dokumennya.

		Bawaannya cuma mengabarkan "Action Submit failed" dan menyimpan traceback
		di Submission Queue. Penolakan closing — BKM draft, upah belum masuk gaji,
		costing gagal — berupa tabel HTML yang justru perlu dibaca utuh, dan di
		traceback cuma tersisa sebagai satu baris mentah. Komentarnya ditulis
		sesudah rollback, jadi ikut tersimpan walau submit-nya batal.
		"""
		if frappe.db.get_value(self.doctype, self.name, "status") != "Failed":
			return

		pesan = next(
			(m for m in reversed(frappe.message_log or []) if isinstance(m, dict) and m.get("message")),
			None,
		)
		if not pesan:
			return

		judul = pesan.get("title") or _("Submit Gagal")

		doc.add_comment("Comment", "<b>{0}</b><br><br>{1}".format(judul, pesan.get("message")))

		frappe.publish_realtime(
			"msgprint",
			{"title": judul, "message": pesan.get("message"), "indicator": "red"},
			user=self.enqueued_by,
		)
