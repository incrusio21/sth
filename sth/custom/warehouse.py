import frappe

def autoname_warehouse(self,method):
	if self.company:
		suffix = "-" + frappe.get_cached_value("Company", self.company, "abbr")
		if not self.warehouse_name.endswith(suffix):
			self.name = self.warehouse_name + suffix
			return

	self.name = self.warehouse_name

"""
ERPNext Warehouse Renamer — removes spaces from all Warehouse names.

Usage (run from your Frappe bench directory):

	bench --site your-site.com execute rename_warehouses.rename_warehouses

Or drop this file into your bench's apps/frappe/ folder and run:

	bench --site your-site.com console
	>>> exec(open("/path/to/rename_warehouses.py").read())

Or for a dry-run preview without making changes:
	Set DRY_RUN = True below.
"""

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DRY_RUN = False   # Set True to preview changes without renaming anything
# ─────────────────────────────────────────────────────────────────────────────

def rename_warehouses():
	warehouses = frappe.get_all("Warehouse", fields=["name"], order_by="name asc")

	renamed = []
	skipped = []
	errors = []

	print(f"\n{'='*60}")
	print(f"  ERPNext Warehouse Space Remover  {'[DRY RUN]' if DRY_RUN else ''}")
	print(f"{'='*60}")
	print(f"Found {len(warehouses)} warehouse(s) total.\n")

	for wh in warehouses:
		old_name = wh["name"]

		# Remove ALL spaces from the full warehouse name.
		# ERPNext format: "Warehouse Name - Company Abbr"
		# e.g. "Main Warehouse - My Company" → "MainWarehouse-MyCompany"
		new_name = old_name.replace(" ", "")

		if new_name == old_name:
			skipped.append(old_name)
			continue

		print(f"  RENAME: '{old_name}'")
		print(f"      --> '{new_name}'")

		if not DRY_RUN:
			try:
				frappe.rename_doc(
					"Warehouse",
					old_name,
					new_name,
					force=True,       # bypass duplicate check
					merge=False,
				)
				frappe.db.commit()
				renamed.append((old_name, new_name))
				print(f"      ✓  Done\n")
			except Exception as e:
				frappe.db.rollback()
				errors.append((old_name, str(e)))
				print(f"      ✗  ERROR: {e}\n")
		else:
			renamed.append((old_name, new_name))
			print()

	# ── Summary ───────────────────────────────────────────────────────────────
	print(f"{'='*60}")
	print(f"  Summary {'[DRY RUN — no changes made]' if DRY_RUN else ''}")
	print(f"{'='*60}")
	print(f"  Would rename : {len(renamed)}" if DRY_RUN else f"  Renamed  : {len(renamed)}")
	print(f"  No change    : {len(skipped)}")
	print(f"  Errors       : {len(errors)}")

	if errors:
		print("\n  Failed renames:")
		for old, err in errors:
			print(f"    - {old}: {err}")

	print(f"{'='*60}\n")


# Allow running via: bench --site <site> execute rename_warehouses.rename_warehouses
# or directly inside bench console
if __name__ == "__main__":
	rename_warehouses()