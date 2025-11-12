import  frappe

@frappe.whitelist()
def get_exit_interview_unrestricted(employee):
    data = frappe.get_all(
        "Exit Interview",
        filters={"employee": employee},
        fields=["name", "custom_upload_file_document", "interview_summary"],
        ignore_permissions=True,
    )

    if not data:
      return frappe._dict({
          "name": None,
          "custom_upload_file_document": None,
          "interview_summary": None
      })

    return data[0]

@frappe.whitelist()
def get_employee(employee):
    data = frappe.get_doc(
        "Employee",
        employee,
        ignore_permissions=True,
    )
    return data

@frappe.whitelist()
def get_kpi_values(employee):
  return frappe.db.sql("""
    SELECT
    YEAR(tb.posting_date) as year,
    tb.name,
    dtb.employee_name,
    dtb.kpi_value
    FROM `tabDetail Transaksi Bonus` as dtb
    JOIN `tabTransaksi Bonus` as tb ON tb.name = dtb.parent
    WHERE dtb.employee = %s AND YEAR(tb.posting_date) >= YEAR(CURDATE()) - 2
    ORDER BY tb.posting_date DESC;
  """, (employee), as_dict=True)

@frappe.whitelist()
def get_employee_grievance(employee):
  return frappe.db.sql("""
    SELECT
    eg.custom_grievance_name as tipe,
    eg.custom_effective_date_from as `from`,
    eg.custom_effective_date_till as until
    FROM `tabEmployee Grievance` as eg
    WHERE eg.grievance_against = %s
    AND CURDATE() <= eg.custom_effective_date_till;
  """, (employee), as_dict=True)