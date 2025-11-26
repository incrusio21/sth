import  frappe
from hrms.hr.doctype.leave_application.leave_application import get_leave_allocation_records
from frappe.utils import flt, cint

@frappe.whitelist()
def get_employee_dashboard_data(employee):
  # ---- EMPLOYEE DOC ----
  emp = frappe.get_doc("Employee", employee)
  
  # ---- ATASAN DOC ----
  atasan = None
  if emp.get("reports_to"):
    try:
      atasan = frappe.get_doc("Employee", emp.get("reports_to"), ignore_permissions=True)
    except frappe.DoesNotExistError:
      atasan = None

  # ---- EXIT INTERVIEW ----
  exit_interview = frappe.get_all(
    "Exit Interview",
    filters={"employee": employee},
    fields=["name", "custom_upload_file_document", "interview_summary"],
    ignore_permissions=True,
    limit_page_length=1,
  )
  exit_interview = exit_interview[0] if exit_interview else {
    "name": None,
    "custom_upload_file_document": None,
    "interview_summary": None
  }

  # ---- KPI VALUES ----
  kpi_values = frappe.db.sql("""
    SELECT
    YEAR(tb.posting_date) as year,
    tb.name,
    dtb.employee_name,
    dtb.kpi_value
    FROM `tabDetail Transaksi Bonus` dtb
    JOIN `tabTransaksi Bonus` tb ON tb.name = dtb.parent
    WHERE dtb.employee = %s
    AND YEAR(tb.posting_date) >= YEAR(CURDATE()) - 2
    ORDER BY tb.posting_date DESC
    LIMIT 3;
  """, (employee), as_dict=True)

  # ---- EMPLOYEE GRIEVANCE ----
  grievances = frappe.db.sql("""
    SELECT
    eg.custom_grievance_name as tipe,
    eg.custom_effective_date_from as `from`,
    eg.custom_effective_date_till as until
    FROM `tabEmployee Grievance` eg
    WHERE eg.grievance_against = %s
    AND CURDATE() <= eg.custom_effective_date_till
  """, (employee,), as_dict=True)

  # ---- LEAVE DETAILS (gunakan method HRMS sendiri) ----
  leave_details = get_leave_details_unrestricted(employee=employee,date=frappe.utils.today())

  # leave_details = frappe.call(
  #   "hrms.hr.doctype.leave_application.leave_application.get_leave_details",
  #   employee=employee,
  #   date=frappe.utils.today()
  # )

  # RETURN SEMUA DATA
  return {
    "employee": emp,
    "atasan": atasan,
    "exit_interview": exit_interview,
    "kpi_values": kpi_values,
    "grievances": grievances,
    "leave_details": leave_details
  }
  
@frappe.whitelist()
def get_leave_details_unrestricted(employee, date, for_salary_slip=False):
  allocation_records = get_leave_allocation_records(employee, date)
  leave_allocation = {}
  precision = cint(frappe.db.get_single_value("System Settings", "float_precision")) or 2

  for d in allocation_records:
    allocation = allocation_records.get(d, frappe._dict())
    to_date = date if for_salary_slip else allocation.to_date

    remaining_leaves = frappe.call(
      "hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on",
      employee=employee,
      leave_type=d,
      date=date,
      to_date=to_date,
      consider_all_leaves_in_the_allocation_period=not for_salary_slip
    )

    leaves_taken = frappe.call(
      "hrms.hr.doctype.leave_application.leave_application.get_leaves_for_period",
      employee=employee,
      leave_type=d,
      from_date=allocation.from_date,
      to_date=to_date
    ) * -1

    leaves_pending = frappe.call(
      "hrms.hr.doctype.leave_application.leave_application.get_leaves_pending_approval_for_period",
      employee=employee,
      leave_type=d,
      from_date=allocation.from_date,
      to_date=to_date
    )

    expired_leaves = allocation.total_leaves_allocated - (remaining_leaves + leaves_taken)

    leave_allocation[d] = {
      "total_leaves": flt(allocation.total_leaves_allocated, precision),
      "expired_leaves": flt(expired_leaves, precision) if expired_leaves > 0 else 0,
      "leaves_taken": flt(leaves_taken, precision),
      "leaves_pending_approval": flt(leaves_pending, precision),
      "remaining_leaves": flt(remaining_leaves, precision),
    }

  lwp = frappe.db.get_list(
    "Leave Type",
    filters={"is_lwp": 1},
    pluck="name",
    ignore_permissions=True,
  )

  return {
    "leave_allocation": leave_allocation,
    "leave_approver": frappe.call(
      "hrms.hr.doctype.leave_application.leave_application.get_leave_approver",
      employee=employee
    ),
    "lwps": lwp,
  }


# @frappe.whitelist()
# def get_exit_interview_unrestricted(employee):
#     data = frappe.get_all(
#         "Exit Interview",
#         filters={"employee": employee},
#         fields=["name", "custom_upload_file_document", "interview_summary"],
#         ignore_permissions=True,
#     )

#     if not data:
#       return frappe._dict({
#           "name": None,
#           "custom_upload_file_document": None,
#           "interview_summary": None
#       })

#     return data[0]

# @frappe.whitelist()
# def get_employee(employee):
#     data = frappe.get_doc(
#         "Employee",
#         employee,
#         ignore_permissions=True,
#     )
#     return data

# @frappe.whitelist()
# def get_kpi_values(employee):
#   return frappe.db.sql("""
#     SELECT
#     YEAR(tb.posting_date) as year,
#     tb.name,
#     dtb.employee_name,
#     dtb.kpi_value
#     FROM `tabDetail Transaksi Bonus` as dtb
#     JOIN `tabTransaksi Bonus` as tb ON tb.name = dtb.parent
#     WHERE dtb.employee = %s AND YEAR(tb.posting_date) >= YEAR(CURDATE()) - 2
#     ORDER BY tb.posting_date DESC;
#   """, (employee), as_dict=True)

# @frappe.whitelist()
# def get_employee_grievance(employee):
#   return frappe.db.sql("""
#     SELECT
#     eg.custom_grievance_name as tipe,
#     eg.custom_effective_date_from as `from`,
#     eg.custom_effective_date_till as until
#     FROM `tabEmployee Grievance` as eg
#     WHERE eg.grievance_against = %s
#     AND CURDATE() <= eg.custom_effective_date_till;
#   """, (employee), as_dict=True)