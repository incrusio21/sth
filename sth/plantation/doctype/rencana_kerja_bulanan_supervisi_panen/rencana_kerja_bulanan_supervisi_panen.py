# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import flt
from frappe.query_builder.custom import ConstantColumn
from frappe.model.document import Document

from sth.controllers.rencana_kerja_controller import get_tonase

class RencanaKerjaBulananSupervisiPanen(Document):
	def validate(self):
		self.get_tonase_divisi()

	def get_tonase_divisi(self):
		for d in self.details:
			d.tonase = get_tonase(self.rencana_kerja_bulanan, {"divisi": d.divisi})

			if not d.tonase:
				frappe.throw("Please add RKB Panen for Divisi {} first.".format(d.divisi))
			
	def on_submit(self):
		self.update_rkb_panen()

	def on_cancel(self):
		self.update_rkb_panen()

	@frappe.whitelist()	
	def update_rkb_panen(self):
		rkb_panen = frappe.qb.DocType("Rencana Kerja Bulanan Panen")
		
		panen_list = (
			frappe.qb.from_(rkb_panen)
			.select(
				ConstantColumn("Rencana Kerja Bulanan Panen").as_("doctype"),
				rkb_panen.name,
				rkb_panen.divisi
			)
			.where(
				(rkb_panen.docstatus == 1) &
				(rkb_panen.rencana_kerja_bulanan == self.rencana_kerja_bulanan) &
				(rkb_panen.divisi.isin([d.divisi for d in self.details]))
			)
		).run(as_dict=1)

		self.db_set({
			"rkb_to_be_repost": json.dumps(panen_list, default=str),
			"status": "Queued",
			"current_index": 0
		})

		if len(panen_list) < 50:
			repost_rkb_panen(self)

		frappe.get_doc("Scheduled Job Type", "rencana_kerja_bulanan_supervisi_panen.repost_entries").enqueue(force=True)

	def set_status(self, status=None, write=True):
		status = status or self.status
		if not status:
			self.status = "Queued"
		else:
			self.status = status
			
		if write:
			self.db_set("status", self.status)

def repost_entries(rkb_entries=[]):
	"""
	Reposts 'Repost Item Valuation' entries in queue.
	Called hourly via hooks.py.
	"""
	if not rkb_entries:
		rkb_entries = frappe.db.sql(
			""" SELECT name from `tabRencana Kerja Bulanan Supervisi Panen`
			WHERE status in ('Queued', 'In Progress') and docstatus = 1
			ORDER BY posting_date asc, creation asc, status asc
		""",
			as_dict=1,
		)

	for row in rkb_entries:
		doc = frappe.get_doc("Rencana Kerja Bulanan Supervisi Panen", row.name)
		if doc.status in ("Queued", "In Progress"):
			repost_rkb_panen(doc)

def repost_rkb_panen(doc):
	args = json.loads(doc.rkb_to_be_repost) or []

	divisi = {d.divisi: d for d in doc.details}

	i = doc.get("current_index") or 0
	try:
		while i < len(args):
			rkb_doc = frappe.get_doc(args[i].get("doctype"), args[i].get("name"))
			
			upah_panen = divisi.get(rkb_doc.divisi)

			rkb_doc.upah_supervisi = flt(upah_panen.upah * rkb_doc.tonase / upah_panen.tonase)
			rkb_doc.premi_supervisi = flt(upah_panen.premi * rkb_doc.tonase / upah_panen.tonase)

			rkb_doc.calculate()
			rkb_doc.db_update()
			
			i += 1
			
			doc.db_set("current_index", i)

		doc.set_status("Completed")

	except Exception as e:
		if frappe.flags.in_test:
			# Don't silently fail in tests,
			# there is no reason for reposts to fail in CI
			raise

		frappe.db.rollback()
		traceback = frappe.get_traceback(with_context=True)

		message = frappe.message_log.pop() if frappe.message_log else ""
		if isinstance(message, dict):
			message = message.get("message")

		status = "Failed"
		# If failed because of timeout, set status to In Progress
		if traceback and ("timeout" in traceback.lower() or "Deadlock found" in traceback):
			status = "In Progress"

		if traceback:
			message += "<br><br>" + "<b>Traceback:</b> <br>" + traceback

		doc.db_set({
			"error_log": message,
			"status": status,
		})
	finally:
		if not frappe.flags.in_test:
			frappe.db.commit()