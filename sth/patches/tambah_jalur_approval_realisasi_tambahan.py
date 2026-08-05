import frappe

from frappe.custom.doctype.custom_field.custom_field import create_custom_field

DOCTYPE = "Payment Entry"
WORKFLOW = "Approval Payment Voucher"

STATE_1 = "Butuh Persetujuan 1"
STATE_2 = "Butuh Persetujuan 2"
STATE_3 = "Butuh Persetujuan 3"
STATE_APPROVED = "Approved"
STATE_REJECTED = "Rejected"

ACTION_APPROVE = "Approve"
ACTION_REJECT = "Reject"

TAMBAHAN = "doc.realisasi_tambahan == 1"
BUKAN_TAMBAHAN = "doc.realisasi_tambahan != 1"

# state yang dipakai jalur tambahan: (state, doc_status, allow_edit)
STATE_JALUR_TAMBAHAN = [
	(STATE_2, "0", "Plantation Staff"),
	(STATE_3, "0", "HEAD PLANTATION"),
]

# (state, action, next_state, role, condition)
TRANSISI_JALUR_TAMBAHAN = [
	(STATE_1, ACTION_APPROVE, STATE_2, "ESTATE MANAGER", TAMBAHAN),
	(STATE_1, ACTION_REJECT, STATE_REJECTED, "ESTATE MANAGER", TAMBAHAN),
	(STATE_2, ACTION_APPROVE, STATE_3, "Plantation Staff", None),
	(STATE_2, ACTION_REJECT, STATE_REJECTED, "Plantation Staff", None),
	(STATE_3, ACTION_APPROVE, STATE_APPROVED, "HEAD PLANTATION", None),
	(STATE_3, ACTION_REJECT, STATE_REJECTED, "HEAD PLANTATION", None),
]


def execute():
	"""Jalur approval terpisah untuk Realisasi PDO yang ada baris di luar PDO.

	Realisasi biasa tetap Draft -> Butuh Persetujuan 1 -> Approved oleh BOD.
	Yang tambahan bercabang di Butuh Persetujuan 1 menjadi tiga lapis:
	ESTATE MANAGER -> Plantation Staff -> HEAD PLANTATION.
	"""
	buat_custom_field()
	backfill_penanda()

	if not frappe.db.exists("Workflow", WORKFLOW):
		print(
			"Workflow {0} belum ada, jalur approval realisasi tambahan dilewati.".format(WORKFLOW)
		)
		return

	pastikan_role([role for _, _, _, role, _ in TRANSISI_JALUR_TAMBAHAN])
	pastikan_workflow_state([state for state, _, _ in STATE_JALUR_TAMBAHAN])
	pastikan_workflow_action([ACTION_APPROVE, ACTION_REJECT])

	doc = frappe.get_doc("Workflow", WORKFLOW)

	pasang_state(doc)
	batasi_approve_bod(doc)
	pasang_transisi(doc)

	doc.flags.ignore_permissions = True
	doc.save()


def buat_custom_field():
	create_custom_field(DOCTYPE, {
		"fieldname": "realisasi_tambahan",
		"label": "Realisasi Tambahan (di luar PDO)",
		"fieldtype": "Check",
		"insert_after": "tipe_transfer",
		"read_only": 1,
		"no_copy": 1,
		"depends_on": "eval:doc.tipe_transfer == 'Realisasi PDO'",
		"description": "Terisi otomatis kalau ada baris realisasi yang tidak berasal dari PDO. Menentukan jalur approval.",
	}, ignore_validate=True)


def backfill_penanda():
	"""PE yang masih berjalan belum pernah lewat validate yang baru.

	Tanpa ini dokumen yang sedang berhenti di Butuh Persetujuan 1 penandanya
	masih kosong, jadi tetap dianggap realisasi biasa dan lolos satu lapis BOD.
	"""
	if not frappe.db.has_column(DOCTYPE, "realisasi_tambahan"):
		return

	daftar = frappe.db.sql_list("""
		select distinct pe.name
		from `tabPayment Entry` pe
		inner join `tabPayment Voucher Kas PDO` baris
			on baris.parent = pe.name
			and baris.parenttype = 'Payment Entry'
			and baris.parentfield = 'payment_voucher_kas_pdo'
		where pe.docstatus = 0
			and pe.tipe_transfer = 'Realisasi PDO'
			and coalesce(baris.pdo_child_name, '') = ''
	""")

	for name in daftar:
		frappe.db.set_value(DOCTYPE, name, "realisasi_tambahan", 1, update_modified=False)

	if daftar:
		print("Realisasi tambahan ditandai pada {0} Payment Entry yang masih draft.".format(len(daftar)))


def pastikan_role(roles):
	belum_ada = sorted({role for role in roles if not frappe.db.exists("Role", role)})

	for role in belum_ada:
		frappe.get_doc({
			"doctype": "Role",
			"role_name": role,
			"desk_access": 1
		}).insert(ignore_permissions=True)

	if belum_ada:
		print(
			"Approval Payment Voucher: role berikut belum ada dan dibuat baru, "
			"pastikan namanya memang sesuai -> " + ", ".join(belum_ada)
		)


def pastikan_workflow_state(states):
	for nama in states:
		if frappe.db.exists("Workflow State", nama):
			continue

		frappe.get_doc({
			"doctype": "Workflow State",
			"workflow_state_name": nama,
			"style": "Warning"
		}).insert(ignore_permissions=True)


def pastikan_workflow_action(actions):
	for nama in actions:
		if frappe.db.exists("Workflow Action Master", nama):
			continue

		frappe.get_doc({
			"doctype": "Workflow Action Master",
			"workflow_action_name": nama
		}).insert(ignore_permissions=True)


def pasang_state(doc):
	for state, doc_status, allow_edit in STATE_JALUR_TAMBAHAN:
		baris = next((row for row in doc.states if row.state == state), None)

		if not baris:
			doc.append("states", {
				"state": state,
				"doc_status": doc_status,
				"allow_edit": allow_edit,
				"send_email": 1
			})
			continue

		# Butuh Persetujuan 2 sudah terdaftar tapi belum dituju transisi mana pun,
		# jadi allow_edit-nya diselaraskan dengan role yang sekarang memakainya.
		baris.doc_status = doc_status
		baris.allow_edit = allow_edit


def batasi_approve_bod(doc):
	"""Approve BOD dari Butuh Persetujuan 1 hanya untuk realisasi non-tambahan.

	Tanpa syarat ini realisasi tambahan bisa langsung disetujui satu lapis dan
	jalur tiga lapisnya terlewat.
	"""
	for row in doc.transitions:
		if row.state != STATE_1 or row.action != ACTION_APPROVE:
			continue

		if row.next_state == STATE_APPROVED:
			row.condition = BUKAN_TAMBAHAN


def pasang_transisi(doc):
	for state, action, next_state, role, condition in TRANSISI_JALUR_TAMBAHAN:
		baris = next((
			row for row in doc.transitions
			if row.state == state
			and row.action == action
			and row.next_state == next_state
			and row.allowed == role
		), None)

		if not baris:
			doc.append("transitions", {
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": role,
				"condition": condition,
				"allow_self_approval": 1
			})
			continue

		baris.condition = condition
