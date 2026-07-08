from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
import frappe

class DeliveryNote(DeliveryNote):
	def check_expense_account(self, item):
		if not item.get("expense_account"):
			msg = _("Please set an Expense Account in the Items table")
			frappe.throw(
				_("Row #{0}: Expense Account not set for the Item {1}. {2}").format(
					item.idx, frappe.bold(item.item_code), msg
				),
				title=_("Expense Account Missing"),
			)

		else:
			is_expense_account = (
				frappe.get_cached_value("Account", item.get("expense_account"), "report_type")
				== "Profit and Loss"
			)
			if (
				self.doctype
				not in (
					"Purchase Receipt",
					"Purchase Invoice",
					"Stock Reconciliation",
					"Stock Entry",
					"Subcontracting Receipt",
					"Delivery Note"
				)
				and not is_expense_account
			):
				frappe.throw(
					_("Expense / Difference account ({0}) must be a 'Profit or Loss' account").format(
						item.get("expense_account")
					)
				)
			if is_expense_account and not item.get("cost_center"):
				frappe.throw(
					_("{0} {1}: Cost Center is mandatory for Item {2}").format(
						_(self.doctype), self.name, item.get("item_code")
					)
				)

	def get_gl_entries(self, warehouse_account=None, default_expense_account=None, default_cost_center=None):
		from erpnext.stock import get_warehouse_account_map
		from erpnext.accounts.general_ledger import (
			make_gl_entries,
			make_reverse_gl_entries,
			process_gl_map,
		)
		from frappe import _
		from frappe.utils import flt
		
		if not warehouse_account:
			warehouse_account = get_warehouse_account_map(self.company)

		sle_map = self.get_stock_ledger_details()
		voucher_details = self.get_voucher_details(default_expense_account, default_cost_center, sle_map)

		gl_list = []
		warehouse_with_no_account = []
		precision = self.get_debit_field_precision()
		for item_row in voucher_details:
			sle_list = sle_map.get(item_row.name)
			sle_rounding_diff = 0.0
			if sle_list:
				for sle in sle_list:
					if warehouse_account.get(sle.warehouse):
						# from warehouse account
						sle_rounding_diff += flt(sle.stock_value_difference)

						self.check_expense_account(item_row)

						# expense account/ target_warehouse / source_warehouse
						if item_row.get("target_warehouse"):
							warehouse = item_row.get("target_warehouse")
							expense_account = warehouse_account[warehouse]["account"]
						else:
							expense_account = item_row.expense_account

						wh_account = ""

						if sle.get("item_code"):
							check_sth_ss = 0
							st_setting = frappe.get_single("STH Stock Settings")
							for st_row in st_setting.sth_stock_settings_persediaan_account:
								if st_row.master_barang == sle.item_code and st_row.company == self.company:
									check_sth_ss = 1
									wh_account = st_row.account

							if check_sth_ss == 0:
								item_doc = frappe.get_doc("Item",sle.get("item_code"))
								kelompok_barang_doc = frappe.get_doc("Item Group",item_doc.kelompok_barang)
								for row_kelompok in kelompok_barang_doc.account_persediaan_kelompok_barang:
									if row_kelompok.company == self.company:
										wh_account = row_kelompok.account

								if wh_account == "" or not wh_account:
									frappe.throw(
										_(
											"Account untuk Kelompok Barang <b>{0}</b> "
											"dan Company <b>{1}</b> tidak ditemukan. "
											"Harap periksa pengaturan Kelompok Barang Accounts."
										).format(kelompok_barang_doc.name, self.company)
									)

						gl_list.append(
							self.get_gl_dict(
								{
									"account": wh_account,
									"against": expense_account,
									"cost_center": item_row.cost_center,
									"project": sle.get("project") or item_row.project or self.get("project"),
									"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
									"debit": flt(sle.stock_value_difference, precision),
									"is_opening": item_row.get("is_opening")
									or self.get("is_opening")
									or "No",
								},
								warehouse_account[sle.warehouse]["account_currency"],
								item=item_row,
							)
						)

						gl_list.append(
							self.get_gl_dict(
								{
									"account": expense_account,
									"against": warehouse_account[sle.warehouse]["account"],
									"cost_center": item_row.cost_center,
									"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
									"debit": -1 * flt(sle.stock_value_difference, precision),
									"project": sle.get("project")
									or item_row.get("project")
									or self.get("project"),
									"is_opening": item_row.get("is_opening")
									or self.get("is_opening")
									or "No",
								},
								item=item_row,
							)
						)
					elif sle.warehouse not in warehouse_with_no_account:
						warehouse_with_no_account.append(sle.warehouse)

			if abs(sle_rounding_diff) > (1.0 / (10**precision)) and self.is_internal_transfer():
				warehouse_asset_account = ""
				if self.get("is_internal_customer"):
					warehouse_asset_account = warehouse_account[item_row.get("target_warehouse")]["account"]
				elif self.get("is_internal_supplier"):
					warehouse_asset_account = warehouse_account[item_row.get("warehouse")]["account"]

				expense_account = frappe.get_cached_value("Company", self.company, "default_expense_account")
				if not expense_account:
					frappe.throw(
						_(
							"Please set default cost of goods sold account in company {0} for booking rounding gain and loss during stock transfer"
						).format(frappe.bold(self.company))
					)

				gl_list.append(
					self.get_gl_dict(
						{
							"account": expense_account,
							"against": warehouse_asset_account,
							"cost_center": item_row.cost_center,
							"project": item_row.project or self.get("project"),
							"remarks": _("Rounding gain/loss Entry for Stock Transfer"),
							"debit": sle_rounding_diff,
							"is_opening": item_row.get("is_opening") or self.get("is_opening") or "No",
						},
						warehouse_account[sle.warehouse]["account_currency"],
						item=item_row,
					)
				)

				gl_list.append(
					self.get_gl_dict(
						{
							"account": warehouse_asset_account,
							"against": expense_account,
							"cost_center": item_row.cost_center,
							"remarks": _("Rounding gain/loss Entry for Stock Transfer"),
							"credit": sle_rounding_diff,
							"project": item_row.get("project") or self.get("project"),
							"is_opening": item_row.get("is_opening") or self.get("is_opening") or "No",
						},
						item=item_row,
					)
				)

		if warehouse_with_no_account:
			for wh in warehouse_with_no_account:
				if frappe.get_cached_value("Warehouse", wh, "company"):
					frappe.throw(
						_(
							"Warehouse {0} is not linked to any account, please mention the account in the warehouse record or set default inventory account in company {1}."
						).format(wh, self.company)
					)

		return process_gl_map(gl_list, precision=precision)

