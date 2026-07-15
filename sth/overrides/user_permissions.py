import frappe
from frappe.utils.user import UserPermissions

# simpan reference method asli
_original_build_permissions = UserPermissions.build_permissions

def get_extra_allowed_modules(user_name):
	"""
	Ambil SEMUA module yang ada di sistem, lalu filter buang yang
	masuk block_modules (baik dari User langsung maupun dari Module Profile).
	"""
	if user_name == "Administrator":
		return []

	user_doc = frappe.get_cached_doc("User", user_name)

	# 1. semua module yang terdaftar di sistem
	all_modules = frappe.get_all("Module Def", pluck="name")

	# 2. block_modules yang di-set langsung di User
	blocked = {d.module for d in user_doc.block_modules}

	# 3. block_modules dari Module Profile (kalau user pakai module profile)
	if user_doc.module_profile:
		mp_blocked = frappe.get_all(
			"Block Module",
			filters={"parent": user_doc.module_profile},
			pluck="module",
		)
		blocked.update(mp_blocked)

	# 4. hasil akhir: semua module dikurangi yang di-block
	return [m for m in all_modules if m not in blocked]


def custom_build_permissions(self):
	# jalankan logic asli dulu (isi allow_modules berdasarkan doctype permission)
	_original_build_permissions(self)

	# tambahkan/replace dengan hasil filter block_modules
	extra_modules = get_extra_allowed_modules(self.name)
	for module in extra_modules:
		if module not in self.allow_modules:
			self.allow_modules.append(module)

UserPermissions.build_permissions = custom_build_permissions