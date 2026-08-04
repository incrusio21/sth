import frappe

from sth.accounting_sth.doctype.asset_scrap_settings.asset_scrap_settings import build_workflow

ROLE_PEMOHON = "Accounts User"

# lapis awal, selanjutnya diatur lewat Asset Scrap Settings
LAPIS_AWAL = [
	(1, "Manager Unit", ["Mill Manager", "ESTATE MANAGER"]),
	(2, "Head Plantation", ["HEAD PLANTATION", "TECHNICAL CONTROLLER"]),
	(3, "Accounting Supervisor", ["Accounting Supervisor"]),
	(4, "Accounting Manager", ["Accounting Manager"]),
	(5, "BOD", ["BOD"]),
]


def execute():
	"""Isi Asset Scrap Settings dengan 5 lapis awal lalu bangun workflownya."""
	settings = frappe.get_single("Asset Scrap Settings")

	if settings.lapis_approval:
		# sudah pernah diatur, jangan timpa
		build_workflow()
		return

	pastikan_role([role for _, _, daftar in LAPIS_AWAL for role in daftar] + [ROLE_PEMOHON])

	settings.role_pemohon = ROLE_PEMOHON
	for nomor, label, daftar_role in LAPIS_AWAL:
		for role in daftar_role:
			settings.append("lapis_approval", {
				"lapis": nomor,
				"label": label,
				"role": role
			})

	settings.flags.ignore_permissions = True
	settings.save()


def pastikan_role(roles):
	dibuat = []

	for role in roles:
		if frappe.db.exists("Role", role):
			continue

		frappe.get_doc({
			"doctype": "Role",
			"role_name": role,
			"desk_access": 1
		}).insert(ignore_permissions=True)
		dibuat.append(role)

	if dibuat:
		print(
			"Asset Scrap Settings: role berikut belum ada dan dibuat baru, "
			"pastikan namanya memang sesuai -> " + ", ".join(dibuat)
		)
