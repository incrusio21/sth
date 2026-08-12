# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import json

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

			if (row.unit, row.lapis, row.role) in terpakai:
				frappe.throw(
					_("Role {0} ditulis dua kali di lapis {1} {2}").format(
						row.role, row.lapis, keterangan_unit(row.unit)
					)
				)

			terpakai.add((row.unit, row.lapis, row.role))

		self.validate_ada_jalur_default()
		self.validate_label_unik()

	def validate_ada_jalur_default(self):
		"""Unit yang tidak ditulis di sini ikut jalur default. Tanpa jalur default
		pengajuannya nyangkut di Draft karena tidak ada transisi yang cocok."""
		if any(not row.unit for row in self.lapis_approval):
			return

		frappe.throw(
			_("Harus ada minimal satu baris tanpa Unit sebagai jalur default untuk unit yang tidak diatur khusus")
		)

	def validate_label_unik(self):
		"""Satu label jadi satu state. Kalau dalam satu unit ada label yang sama
		di dua lapis, alurnya berputar balik ke lapis sebelumnya."""
		for unit, lapis in get_lapis_per_unit(self).items():
			terpakai = {}

			for nomor, label, _roles in lapis:
				if label in terpakai:
					frappe.throw(
						_("Nama Lapis {0} dipakai di lapis {1} dan {2} {3}. Bedakan namanya.").format(
							label, terpakai[label], nomor, keterangan_unit(unit)
						)
					)

				terpakai[label] = nomor

	def validate_state_masih_dipakai(self):
		"""Kalau ada pengajuan yang sedang berhenti di sebuah state lalu state itu
		dihapus dari setting, dokumennya nyangkut tanpa tombol apa pun."""
		if not frappe.get_meta(DOCTYPE).has_field("workflow_state"):
			return

		state_baru = {STATE_DRAFT, STATE_APPROVED, STATE_REJECTED}
		state_baru.update(semua_state(get_lapis_per_unit(self)))

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


def keterangan_unit(unit):
	return "di unit {0}".format(unit) if unit else "di jalur default"


def get_lapis_per_unit(settings=None):
	"""{unit atau None: [(nomor lapis, label, [role, ...]), ...]}

	Kunci None adalah jalur default, dipakai unit yang tidak diatur khusus.
	Tiap daftar sudah urut dari lapis terkecil."""
	settings = settings or frappe.get_single("Asset Scrap Settings")

	per_unit = {}
	for row in settings.lapis_approval:
		kelompok = per_unit.setdefault(row.unit or None, {})
		data = kelompok.setdefault(row.lapis, {"label": None, "roles": []})

		if row.label and not data["label"]:
			data["label"] = row.label

		if row.role not in data["roles"]:
			data["roles"].append(row.role)

	return {
		unit: [
			(nomor, kelompok[nomor]["label"] or "Lapis {0}".format(nomor), kelompok[nomor]["roles"])
			for nomor in sorted(kelompok)
		]
		for unit, kelompok in per_unit.items()
	}


def get_lapis(settings=None, unit=None):
	"""Lapis yang berlaku untuk sebuah unit, jatuh ke jalur default kalau
	unitnya tidak diatur khusus."""
	per_unit = get_lapis_per_unit(settings)

	return per_unit.get(unit) or per_unit.get(None) or []


def urutan_unit(per_unit):
	"""Jalur default duluan supaya urutan state di workflow tetap stabil."""
	return ([None] if None in per_unit else []) + sorted(unit for unit in per_unit if unit)


def semua_state(per_unit):
	"""State approval dari semua jalur, tanpa duplikat, urut kemunculan."""
	hasil = []

	for unit in urutan_unit(per_unit):
		for _nomor, label, _roles in per_unit[unit]:
			state = nama_state(label)
			if state not in hasil:
				hasil.append(state)

	return hasil


def kondisi_unit(unit, unit_khusus):
	"""Kondisi transisi supaya satu workflow bisa memuat banyak jalur sekaligus."""
	if unit:
		return "doc.unit == {0}".format(json.dumps(unit))

	if not unit_khusus:
		# semua unit lewat jalur default, tidak perlu disaring
		return None

	return "doc.unit not in {0}".format(json.dumps(unit_khusus))


def build_workflow():
	"""Bangun ulang Workflow dari isi Asset Scrap Settings."""
	settings = frappe.get_single("Asset Scrap Settings")
	per_unit = get_lapis_per_unit(settings)

	if not per_unit:
		return

	role_pemohon = settings.role_pemohon or "Accounts User"
	unit_khusus = sorted(unit for unit in per_unit if unit)

	pastikan_workflow_state(semua_state(per_unit))
	pastikan_workflow_action()

	beri_permission(role_pemohon, boleh_buat=True)

	for lapis in per_unit.values():
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

	# state yang labelnya sama dipakai bersama lintas unit, yang membedakan
	# jalurnya adalah kondisi di tiap transisi
	pemilik_state = {}
	for unit in urutan_unit(per_unit):
		for _nomor, label, roles in per_unit[unit]:
			state = nama_state(label)
			if state in pemilik_state:
				continue

			pemilik_state[state] = roles[0]
			tambah_state(doc, state, 0, roles[0])

	tambah_state(doc, STATE_APPROVED, 1, "System Manager")
	tambah_state(doc, STATE_REJECTED, 1, "System Manager")

	for unit in urutan_unit(per_unit):
		lapis = per_unit[unit]
		kondisi = kondisi_unit(unit, unit_khusus)

		tambah_transition(
			doc, STATE_DRAFT, ACTION_AJUKAN, nama_state(lapis[0][1]), role_pemohon, kondisi
		)

		for idx, (_nomor, label, roles) in enumerate(lapis):
			berikutnya = nama_state(lapis[idx + 1][1]) if idx + 1 < len(lapis) else STATE_APPROVED

			for role in roles:
				tambah_transition(doc, nama_state(label), ACTION_APPROVE, berikutnya, role, kondisi)
				tambah_transition(doc, nama_state(label), ACTION_REJECT, STATE_REJECTED, role, kondisi)

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


def beri_permission(role, boleh_buat=False):
	# role approval harus bisa baca, mengubah state, dan submit karena state
	# Approved dan Rejected berdocstatus 1. role pemohon perlu create juga
	# karena dokumennya dibuat atas namanya dari form Asset
	add_permission(DOCTYPE, role, 0)

	ptypes = ["read", "write", "submit", "report", "email", "print", "share"]
	if boleh_buat:
		ptypes.append("create")

	for ptype in ptypes:
		update_permission_property(DOCTYPE, role, 0, ptype, 1)


def tambah_state(doc, state, doc_status, allow_edit):
	doc.append("states", {
		"state": state,
		"doc_status": str(doc_status),
		"allow_edit": allow_edit
	})


def tambah_transition(doc, state, action, next_state, allowed, condition=None):
	doc.append("transitions", {
		"state": state,
		"action": action,
		"next_state": next_state,
		"allowed": allowed,
		"condition": condition,
		"allow_self_approval": 1
	})
