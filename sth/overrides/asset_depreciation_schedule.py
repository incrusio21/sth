import frappe

from erpnext.assets.doctype.asset_depreciation_schedule.asset_depreciation_schedule import AssetDepreciationSchedule,_get_value_after_depreciation_for_making_schedule,_check_is_pro_rata,get_depreciation_amount,_get_pro_rata_amt,is_first_day_of_the_month
from erpnext.accounts.utils import get_fiscal_year
from frappe import _
from frappe.utils import (
	add_days,
	add_months,
	add_years,
	cint,
	date_diff,
	flt,
	get_first_day,
	get_last_day,
	get_link_to_form,
	getdate,
	is_last_day_of_the_month,
	month_diff,
)

class AssetDepreciationSchedule(AssetDepreciationSchedule):
	def _make_depr_schedule(
		self,
		asset_doc,
		row,
		start,
		date_of_disposal,
		update_asset_finance_book_row,
		value_after_depreciation,
	):
		asset_doc.validate_asset_finance_books(row)
		if (
			not value_after_depreciation
			and not asset_doc.flags.decrease_in_asset_value_due_to_value_adjustment
		):
			value_after_depreciation = _get_value_after_depreciation_for_making_schedule(asset_doc, row)
		row.value_after_depreciation = value_after_depreciation

		if update_asset_finance_book_row:
			row.db_update()

		final_number_of_depreciations = cint(row.total_number_of_depreciations) - cint(
			self.opening_number_of_booked_depreciations
		)

		has_pro_rata = _check_is_pro_rata(asset_doc, row)
		if has_pro_rata:
			final_number_of_depreciations += 1

		has_wdv_or_dd_non_yearly_pro_rata = False
		if (
			row.depreciation_method in ("Written Down Value", "Double Declining Balance")
			and cint(row.frequency_of_depreciation) != 12
		):
			has_wdv_or_dd_non_yearly_pro_rata = _check_is_pro_rata(asset_doc, row, wdv_or_dd_non_yearly=True)

		skip_row = False
		# should_get_last_day = is_last_day_of_the_month(row.depreciation_start_date)

		depreciation_amount = 0

		number_of_pending_depreciations = final_number_of_depreciations - start
		yearly_opening_wdv = value_after_depreciation
		current_fiscal_year_end_date = None
		prev_per_day_depr = True
		for n in range(start, final_number_of_depreciations):
			# If depreciation is already completed (for double declining balance)
			if skip_row:
				continue

			schedule_date = get_first_day(
				add_months(row.depreciation_start_date, n * cint(row.frequency_of_depreciation))
			)
			if not current_fiscal_year_end_date:
				current_fiscal_year_end_date = get_fiscal_year(row.depreciation_start_date)[2]
			elif getdate(schedule_date) > getdate(current_fiscal_year_end_date):
				current_fiscal_year_end_date = add_years(current_fiscal_year_end_date, 1)
				yearly_opening_wdv = value_after_depreciation

			if n > 0 and len(self.get("depreciation_schedule")) > n - 1:
				prev_depreciation_amount = self.get("depreciation_schedule")[n - 1].depreciation_amount
			else:
				prev_depreciation_amount = 0
			depreciation_amount, prev_per_day_depr = get_depreciation_amount(
				self,
				asset_doc,
				value_after_depreciation,
				yearly_opening_wdv,
				row,
				n,
				prev_depreciation_amount,
				has_wdv_or_dd_non_yearly_pro_rata,
				number_of_pending_depreciations,
				prev_per_day_depr,
			)
			if not has_pro_rata or (
				n < (cint(final_number_of_depreciations) - 1) or final_number_of_depreciations == 2
			):
				schedule_date = add_months(
					row.depreciation_start_date, n * cint(row.frequency_of_depreciation)
				)

				# if should_get_last_day:
				schedule_date = get_first_day(schedule_date)

			# if asset is being sold or scrapped
			if date_of_disposal and getdate(schedule_date) >= getdate(date_of_disposal):
				from_date = add_months(
					getdate(asset_doc.available_for_use_date),
					(asset_doc.opening_number_of_booked_depreciations * row.frequency_of_depreciation),
				)
				if is_last_day_of_the_month(getdate(asset_doc.available_for_use_date)):
					from_date = get_last_day(from_date)
				if self.depreciation_schedule:
					from_date = add_days(self.depreciation_schedule[-1].schedule_date, 1)

				depreciation_amount, days, months = _get_pro_rata_amt(
					row,
					depreciation_amount,
					from_date,
					date_of_disposal,
					original_schedule_date=schedule_date,
				)
				depreciation_amount = flt(depreciation_amount, asset_doc.precision("gross_purchase_amount"))

				if depreciation_amount > row.value_after_depreciation - row.expected_value_after_useful_life:
					depreciation_amount = row.value_after_depreciation - row.expected_value_after_useful_life

				if depreciation_amount > 0:
					self.add_depr_schedule_row(date_of_disposal, depreciation_amount, n)

				break

			# For first row
			if (
				n == 0
				and (has_pro_rata or has_wdv_or_dd_non_yearly_pro_rata)
				and not self.opening_accumulated_depreciation
				and not self.flags.wdv_it_act_applied
			):
				from_date = asset_doc.available_for_use_date
				# needed to calc depr amount for available_for_use_date too
				depreciation_amount, days, months = _get_pro_rata_amt(
					row,
					depreciation_amount,
					from_date,
					row.depreciation_start_date,
					has_wdv_or_dd_non_yearly_pro_rata,
				)
				if flt(depreciation_amount, asset_doc.precision("gross_purchase_amount")) <= 0:
					frappe.throw(
						_(
							"Gross Purchase Amount Too Low: {0} cannot be depreciated over {1} cycles with a frequency of {2} depreciations."
						).format(
							frappe.bold(asset_doc.gross_purchase_amount),
							frappe.bold(row.total_number_of_depreciations),
							frappe.bold(row.frequency_of_depreciation),
						)
					)
			elif n == 0 and has_wdv_or_dd_non_yearly_pro_rata and self.opening_accumulated_depreciation:
				if not is_first_day_of_the_month(getdate(asset_doc.available_for_use_date)):
					from_date = get_last_day(
						add_months(
							getdate(asset_doc.available_for_use_date),
							(
								(self.opening_number_of_booked_depreciations - 1)
								* row.frequency_of_depreciation
							),
						)
					)
				else:
					from_date = add_months(
						getdate(add_days(asset_doc.available_for_use_date, -1)),
						(self.opening_number_of_booked_depreciations * row.frequency_of_depreciation),
					)
				depreciation_amount, days, months = _get_pro_rata_amt(
					row,
					depreciation_amount,
					from_date,
					row.depreciation_start_date,
					has_wdv_or_dd_non_yearly_pro_rata,
				)

			# For last row
			elif has_pro_rata and n == cint(final_number_of_depreciations) - 1:
				if not asset_doc.flags.increase_in_asset_life:
					# In case of increase_in_asset_life, the asset.to_date is already set on asset_repair submission
					asset_doc.to_date = add_months(
						asset_doc.available_for_use_date,
						(n + self.opening_number_of_booked_depreciations)
						* cint(row.frequency_of_depreciation),
					)
					if is_last_day_of_the_month(getdate(asset_doc.available_for_use_date)):
						asset_doc.to_date = get_last_day(asset_doc.to_date)

				depreciation_amount_without_pro_rata = depreciation_amount

				depreciation_amount, days, months = _get_pro_rata_amt(
					row,
					depreciation_amount,
					schedule_date,
					asset_doc.to_date,
					has_wdv_or_dd_non_yearly_pro_rata,
				)

				depreciation_amount = self.get_adjusted_depreciation_amount(
					depreciation_amount_without_pro_rata, depreciation_amount
				)

				schedule_date = add_days(schedule_date, days - 1)

			if not depreciation_amount:
				continue
			depreciation_amount = flt(depreciation_amount, asset_doc.precision("gross_purchase_amount"))
			value_after_depreciation = flt(
				flt(value_after_depreciation) - flt(depreciation_amount),
				asset_doc.precision("gross_purchase_amount"),
			)

			# Adjust depreciation amount in the last period based on the expected value after useful life
			if (
				n == cint(final_number_of_depreciations) - 1
				and flt(value_after_depreciation) != flt(row.expected_value_after_useful_life)
			) or flt(value_after_depreciation) < flt(row.expected_value_after_useful_life):
				depreciation_amount += flt(value_after_depreciation) - flt(
					row.expected_value_after_useful_life
				)
				depreciation_amount = flt(depreciation_amount, asset_doc.precision("gross_purchase_amount"))
				skip_row = True

			if flt(depreciation_amount, asset_doc.precision("gross_purchase_amount")) > 0:
				self.add_depr_schedule_row(schedule_date, depreciation_amount, n)