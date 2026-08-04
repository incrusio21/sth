# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.permissions import add_permission, update_permission_property

DOCTYPE = "Asset Scrap Request"
WORKFLOW = "Asset Scrap Request Approval"

STATE_DRAFT = "Draft"
STATE_APPROVED = "Approved"
STATE_REJECTED = "Rejected"

ACTION_AJUKAN = "Ajukan"
ACTION_APPROVE = "Approve"
ACTION_REJECT = "Reject"


class AssetScrapSettings(Document):

	def validate(self):
		self.validate_lapis()
		self.validate_state_masih_dipakai()

	def on_update(self):
		build_workflow()

	def validate_lapis(self):
		if not self.lapis_approval:
			frappe.throw(_("Lapis Approval tidak boleh kosong"))

		terpakai = set()

		for row in self.lapis_approval:
			if row.lapis < 1:
				frappe.throw(_("Baris {0}: Lapis harus diisi minimal 1").format(row.idx))

			if (row.lapis, row.role) in terpakai:
				frappe.throw(_("Role {0} ditulis dua kali di lapis {1}").format(row.role, row.lapis))

			terpakai.add((row.lapis, row.role))

	def validate_state_masih_dipakai(self):
		"""Kalau ada pengajuan yang sedang berhenti di sebuah state lalu state itu
		dihapus dari setting, dokumennya nyangkut tanpa tombol apa pun."""
		if not frappe.get_meta(DOCTYPE).has_field("workflow_state"):
			return

		state_baru = {STATE_DRAFT, STATE_APPROVED, STATE_REJECTED}
		state_baru.update(nama_state(lapis[1]) for lapis in get_lapis(self))

		dipakai = frappe.get_all(
			DOCTYPE,
			filters={"docstatus": 0},
			pluck="workflow_state",
			distinct=True
		)

		nyangkut = sorted({state for state in dipakai if state and state not in state_baru})

		if nyangkut:
			frappe.throw(
				_("Masih ada pengajuan yang berhenti di state: {0}. Selesaikan dulu sebelum lapisnya diubah.").format(
					", ".join(nyangkut)
				)
			)


def nama_state(label):
	return "Menunggu Approval {0}".format(label)


def get_lapis(settings=None):
	"""[(nomor lapis, label, [role, ...]), ...] urut dari lapis terkecil."""
	settings = settings or frappe.get_single("Asset Scrap Settings")

	kelompok = {}
	for row in settings.lapis_approval:
		data = kelompok.setdefault(row.lapis, {"label": None, "roles": []})

		if row.label and not data["label"]:
			data["label"] = row.label

		if row.role not in data["roles"]:
			data["roles"].append(row.role)

	return [
		(nomor, kelompok[nomor]["label"] or "Lapis {0}".format(nomor), kelompok[nomor]["roles"])
		for nomor in sorted(kelompok)
	]


def build_workflow():
	"""Bangun ulang Workflow dari isi Asset Scrap Settings."""
	settings = frappe.get_single("Asset Scrap Settings")
	lapis = get_lapis(settings)

	if not lapis:
		return

	role_pemohon = settings.role_pemohon or "Accounts User"

	pastikan_workflow_state([nama_state(baris[1]) for baris in lapis])
	pastikan_workflow_action()

	for _nomor, _label, roles in lapis:
		for role in roles:
			beri_permission(role)

	if frappe.db.exists("Workflow", WORKFLOW):
		doc = frappe.get_doc("Workflow", WORKFLOW)
	else:
		doc = frappe.new_doc("Workflow")
		doc.workflow_name = WORKFLOW

	doc.document_type = DOCTYPE
	doc.workflow_state_field = "workflow_state"
	doc.is_active = 1
	doc.send_email_alert = 1
	doc.states = []
	doc.transitions = []

	tambah_state(doc, STATE_DRAFT, 0, role_pemohon)
	for _nomor, label, roles in lapis:
		tambah_state(doc, nama_state(label), 0, roles[0])
	tambah_state(doc, STATE_APPROVED, 1, "System Manager")
	tambah_state(doc, STATE_REJECTED, 1, "System Manager")

	tambah_transition(doc, STATE_DRAFT, ACTION_AJUKAN, nama_state(lapis[0][1]), role_pemohon)

	for idx, (_nomor, label, roles) in enumerate(lapis):
		berikutnya = nama_state(lapis[idx + 1][1]) if idx + 1 < len(lapis) else STATE_APPROVED

		for role in roles:
			tambah_transition(doc, nama_state(label), ACTION_APPROVE, berikutnya, role)
			tambah_transition(doc, nama_state(label), ACTION_REJECT, STATE_REJECTED, role)

	doc.flags.ignore_permissions = True
	doc.save()


def pastikan_workflow_state(states):
	semua = [(STATE_DRAFT, "Danger"), (STATE_APPROVED, "Success"), (STATE_REJECTED, "Danger")]
	semua += [(state, "Warning") for state in states]

	for nama, style in semua:
		if frappe.db.exists("Workflow State", nama):
			continue

		frappe.get_doc({
			"doctype": "Workflow State",
			"workflow_state_name": nama,
			"style": style
		}).insert(ignore_permissions=True)


def pastikan_workflow_action():
	for nama in (ACTION_AJUKAN, ACTION_APPROVE, ACTION_REJECT):
		if frappe.db.exists("Workflow Action Master", nama):
			continue

		frappe.get_doc({
			"doctype": "Workflow Action Master",
			"workflow_action_name": nama
		}).insert(ignore_permissions=True)


def beri_permission(role):
	# role approval harus bisa baca, mengubah state, dan submit karena state
	# Approved dan Rejected berdocstatus 1
	add_permission(DOCTYPE, role, 0)

	for ptype in ("read", "write", "submit", "report", "email", "print", "share"):
		update_permission_property(DOCTYPE, role, 0, ptype, 1)


def tambah_state(doc, state, doc_status, allow_edit):
	doc.append("states", {
		"state": state,
		"doc_status": str(doc_status),
		"allow_edit": allow_edit
	})


def tambah_transition(doc, state, action, next_state, allowed):
	doc.append("transitions", {
		"state": state,
		"action": action,
		"next_state": next_state,
		"allowed": allowed,
		"allow_self_approval": 1
	})
