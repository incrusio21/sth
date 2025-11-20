import frappe
from datetime import datetime, date

def get_month_difference(date_value):
    if isinstance(date_value, date):
        input_date = datetime.combine(date_value, datetime.min.time())
    else:
        input_date = datetime.strptime(date_value, "%Y-%m-%d")

    now = datetime.now()

    years = now.year - input_date.year
    months = now.month - input_date.month

    total_months = years * 12 + months

    if now.day < input_date.day:
        total_months -= 1

    tahun = total_months // 12
    bulan = total_months % 12

    return f"{tahun} Tahun {bulan} Bulan"

def update_employee_employment_tenure():
  today = datetime.today()

  employees = frappe.get_list(
    "Employee", 
    fields=["name", "date_of_joining"]
  )

  for emp in employees:
    doj = emp.get("date_of_joining")
    if not doj:
      continue

    if doj.day == today.day and doj.month == today.month:
      tenure = get_month_difference(doj)

      frappe.db.set_value(
        "Employee",
        emp.get("name"),
        "custom_employment_tenure",
        tenure,
        update_modified=False
      )

      print(f"--- UPDATE tenure {emp.get('name')} → {tenure} ---")