import frappe

@frappe.whitelist()
def get_travel_request_expenses(employee, company, department):
  return frappe.db.sql("""
    SELECT
    ea.name as employee_advance,
    tr.name as travel_request_name,
    tr.custom_posting_date as expense_date,
    trc.expense_type,
    trc.total_amount as amount,
    trc.total_amount as sanctioned_amount,
    eca.default_account
    FROM `tabEmployee Advance` as ea
    JOIN `tabTravel Request` as tr ON tr.custom_employee_advance = ea.name
    JOIN `tabTravel Request Costing` as trc ON trc.parent = tr.name
    JOIN `tabExpense Claim Account` as eca ON eca.parent = trc.expense_type
    WHERE ea.employee = %s AND ea.company = %s AND ea.department = %s AND eca.company = %s;
  """, (employee, company, department, company), as_dict=True)

@frappe.whitelist()
def test_safe_eval():
  thr_rule = frappe.db.get_value(
    "THR Setup Rule",
    {
        "employee_grade": "NON STAF",
        "employment_type": "KARYAWAN TETAP",
        "kriteria": "Non Satuan Hasil",
    },
    ["formula"],
  )

  context = {
      "GP": 2500000,
      "Natura": 150000,
      "Uang_Daging": 200000
  }

  hasil = frappe.safe_eval(thr_rule, None, context)

  return hasil