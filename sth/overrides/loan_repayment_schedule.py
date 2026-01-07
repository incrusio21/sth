# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

from frappe.utils import add_days, add_months, cint, getdate
from lending.loan_management.doctype.loan_repayment_schedule.utils import (
	get_amounts,
	get_monthly_repayment_amount,
)
from lending.loan_management.doctype.loan_repayment_schedule.loan_repayment_schedule import LoanRepaymentSchedule

class STHLoanRepaymentSchedule(LoanRepaymentSchedule):
    def on_submit(self):
        super().on_submit()
        self.db_set("status", "Active")

    def make_repayment_schedule(
        self,
        schedule_field,
        previous_interest_amount,
        balance_amount,
        additional_principal_amount,
        pending_prev_days,
        rate_of_interest,
        principal_share_percentage,
        interest_share_percentage,
        partner_schedule_type=None,
    ):
        payment_date = self.repayment_start_date
        repayment_period = self.repayment_periods
        carry_forward_interest = self.adjusted_interest
        moratorium_interest = 0
        row = 0
    
        if self.first_payment:
            balance_amount = (balance_amount - self.first_payment)
            repayment_period -= 1
            self.add_repayment_schedule_row(
                payment_date,
                self.first_payment,
                0,
                self.first_payment,
                balance_amount,
                payment_date,
                repayment_schedule_field=schedule_field,
                principal_share_percentage=principal_share_percentage,
                interest_share_percentage=interest_share_percentage,
            )

            payment_date = self.get_next_payment_date(payment_date)

        if not self.restructure_type and self.repayment_method != "Repay Fixed Amount per Period":
            monthly_repayment_amount = get_monthly_repayment_amount(
                balance_amount, rate_of_interest, repayment_period, self.repayment_frequency
            )
        else:
            monthly_repayment_amount = self.monthly_repayment_amount

        if not self.restructure_type:
            if (
                self.moratorium_tenure
                and self.repayment_frequency == "Monthly"
                and self.repayment_schedule_type == "Monthly as per cycle date"
            ):
                payment_date = self.repayment_start_date
                self.moratorium_end_date = add_months(self.repayment_start_date, self.moratorium_tenure - 1)
            elif self.moratorium_tenure and self.repayment_frequency == "Monthly":
                self.moratorium_end_date = add_months(self.repayment_start_date, self.moratorium_tenure)
                if self.repayment_schedule_type == "Pro-rated calendar months":
                    self.moratorium_end_date = add_days(self.moratorium_end_date, -1)
        
        tenure = self.get_applicable_tenure(payment_date)

        if len(self.get(schedule_field)) > 0:
            self.broken_period_interest_days = 0

        additional_days = cint(self.broken_period_interest_days)
        if additional_days < 0:
            self.broken_period_interest_days = 0

        while balance_amount > 0:
            if self.moratorium_tenure and self.repayment_frequency == "Monthly":
                if getdate(payment_date) > getdate(self.moratorium_end_date):
                    if (
                        self.moratorium_type == "EMI"
                        and self.treatment_of_interest == "Capitalize"
                        and moratorium_interest
                    ):
                        balance_amount = self.loan_amount + moratorium_interest
                        monthly_repayment_amount = get_monthly_repayment_amount(
                            balance_amount, rate_of_interest, repayment_period, self.repayment_frequency
                        )
                        moratorium_interest = 0

            prev_balance_amount = balance_amount

            payment_days, months = self.get_days_and_months(
                payment_date,
                additional_days,
                balance_amount,
                rate_of_interest,
                schedule_field,
                principal_share_percentage,
                interest_share_percentage,
            )

            (
                interest_amount,
                principal_amount,
                balance_amount,
                total_payment,
                days,
                previous_interest_amount,
            ) = get_amounts(
                balance_amount,
                rate_of_interest,
                payment_days,
                months,
                monthly_repayment_amount,
                carry_forward_interest,
                previous_interest_amount,
                additional_principal_amount,
                pending_prev_days,
            )

            if (
                schedule_field == "colender_schedule"
                and partner_schedule_type == "POS reduction plus interest at partner ROI"
                and row <= len(self.get("repayment_schedule")) - 1
            ):
                principal_amount = self.get("repayment_schedule")[row].principal_amount
                balance_amount = prev_balance_amount - (principal_amount * principal_share_percentage / 100)
                row = row + 1

            if (
                self.moratorium_end_date and self.moratorium_tenure and self.repayment_frequency == "Monthly"
            ):
                if getdate(payment_date) <= getdate(self.moratorium_end_date):
                    principal_amount = 0
                    balance_amount = self.current_principal_amount
                    moratorium_interest += interest_amount

                    if self.moratorium_type == "EMI":
                        total_payment = 0
                        interest_amount = 0
                    else:
                        total_payment = interest_amount

                elif (
                    self.moratorium_type == "EMI"
                    and self.treatment_of_interest == "Add to first repayment"
                    and moratorium_interest
                ):
                    interest_amount += moratorium_interest
                    total_payment = principal_amount + interest_amount
                    moratorium_interest = 0

            self.add_repayment_schedule_row(
                payment_date,
                principal_amount,
                interest_amount,
                total_payment,
                balance_amount,
                days,
                repayment_schedule_field=schedule_field,
                principal_share_percentage=principal_share_percentage,
                interest_share_percentage=interest_share_percentage,
            )

            # All the residue amount is added to the last row for "Repay Over Number of Periods"
            #
            # Also, when such a Repayment Schedule is rescheduled, its repayment_method changes to Repay Fixed Amount per Period
            # Here, the tenure shouldn't change. Thus, if this is a restructed repayment schedule, the last row is all the residue amount left.
            # This is a special case.

            if (
                self.repayment_method == "Repay Over Number of Periods"
                or (self.restructure_type and self.repayment_method == "Repay Fixed Amount per Period")
            ) and len(self.get(schedule_field)) >= tenure:
                self.get(schedule_field)[-1].principal_amount += balance_amount
                self.get(schedule_field)[-1].balance_loan_amount = 0
                self.get(schedule_field)[-1].total_payment = (
                    self.get(schedule_field)[-1].interest_amount + self.get(schedule_field)[-1].principal_amount
                )
                balance_amount = 0

            payment_date = self.get_next_payment_date(payment_date)
            carry_forward_interest = 0
            additional_days = 0
            additional_principal_amount = 0
            pending_prev_days = 0

        if schedule_field == "repayment_schedule" and not self.restructure_type:
            if self.repayment_frequency == "One Time":
                self.monthly_repayment_amount = self.get(schedule_field)[0].total_payment
            else:
                self.monthly_repayment_amount = monthly_repayment_amount
        else:
            self.repayment_periods = self.number_of_rows