# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.permissions import has_permission
from frappe.utils import flt, format_date, get_datetime, get_last_day, getdate
from erpnext.controllers.queries import get_fields, has_ignored_field
from frappe.model.document import Document

from sth.utils import generate_duplicate_key
from sth.hr_customize import get_overtime_settings

class LemburList(Document):
	
	def validate(self):
		self.validate_employee_overtime()
		self.validate_detail_overtime()
		self.set_missing_value()
		self.calculate()

	def validate_employee_overtime(self):
		# check jika lembur hanya boleh untuk pegawai tertentu
		if not get_overtime_settings("overtime_for_selected_staff"):
			return
		
		# untuk sekarang hanya akan mengecek designation
		req_value = frappe.get_value("Employee", self.employee, "designation")
		if not req_value:
			frappe.throw("Please Set Designation in Employee first")

		if not frappe.get_cached_value("Designation", req_value, "can_overtime"):
			frappe.throw("This employee is not eligible for overtime")
		
	def validate_detail_overtime(self):
		tgl_lembur_sama = ''
		tanggal_lembur = []
		for row in self.details:
			if row.overtime_date in tanggal_lembur:
				tgl_lembur_sama += " Overtime date {} in row {} is already taken. Please check again ".format(
					format_date(row.overtime_date, "dd-mm-yyyy"), 
					row.idx
				) + '<br>'
				continue

			if getdate(row.overtime_date).month != self.month_number:
				frappe.throw("Overtime on {} #Row{} does not match the period of {}".format(
						format_date(row.overtime_date, "dd-mm-yyyy"), 
						row.idx, 
						self.month_period
					)
				)

			# if getdate(row.tanggal) >= getdate(None):
			# 	frappe.throw("Tanggal lembur tidak boleh lebih besar dari {}".format(today()) + '<br>')

			# tanggal tidak boleh sama
			tanggal_lembur.append(row.overtime_date)
			
		if tgl_lembur_sama:
			frappe.throw(tgl_lembur_sama)

	def set_missing_value(self):
		if not self.salary_component:
			self.salary_component = get_overtime_settings("default_salary_component")

		if getdate(self.posting_date).month != self.month_number:
			frappe.throw("Posting Date does not match the period of {}".format(self.month_period))

		self.natura_price = frappe.get_value("Natura Price", {
            "company": self.company, 
			"valid_from": ["<=", get_last_day(self.posting_date)]
		}, "harga_beras", order_by="valid_from desc") or 0

	def calculate(self):
		self.calculate_total_overtime()
		self.calculate_overtime_amount()
	
	def calculate_total_overtime(self):
		# cari child sesuai dengan nama
		overtime_settings = sorted(get_overtime_settings("roundings"), key=lambda x: x.end_time, reverse=True)

		# frappe.get_all("Overtime Rounding Settings", 
		# 	filters={'parent' : "Overtime Settings"}, fields=['start_time', 'end_time', 'rounding_time'], order_by="rounding_time desc")

		tidak_lembur = ''

		overtime_total = 0
		for row in self.details:
			# attendance belum d siapkan
			# if not row.jam_check_out:
			# 	attendance = frappe.db.get_value("Attendance", { "employee" : self.kode_karyawan, 'attendance_date' : row.tanggal }, 'out_time')
			#  	row.overtime_to = get_time(out)
			# else:
			attendance = get_datetime("{} {}".format(row.overtime_date, row.overtime_to))

			if not attendance:
				frappe.throw('Employee did not check out on {}'.format(format_date(row.overtime_date, "dd-mm-yyyy")))

			# waktu lembur - waktu pulang 
			# out = get_datetime(attendance)
			overtime_from = get_datetime("{} {}".format(row.overtime_date, row.overtime_from))

			overtime_total = int((attendance - overtime_from).total_seconds() / 60)
			if overtime_total < 0:
				tidak_lembur += "Check-out time on attendance document for {} is earlier than overtime hours in row {}".format(
					format_date(row.overtime_date, "dd-mm-yyyy"), 
					row.idx
				) + '<br>'
				continue
			
			overtime = 0
			# check jika jumlah lembur lebih besar dari rounding pengaturan jam lembur terbesar
			if overtime_total > overtime_settings[0].end_time:
				# true sampai jumlah lembur lebih kecil dari 1
				while overtime_total > 0:
					copy_overtime = overtime_total
					for over_s in overtime_settings:
						if overtime_total > over_s.end_time:
							# jika jumlah lembur lebih besar dari nilai rounding, kurangi jumlah lembur dengan nilai menit akhir 
							# jika nilai menit akhir sama dengan nol kurangi dengan jumlah lembur untuk menghidari infinite loop
							overtime_total -= over_s.rounding_time if over_s.rounding_time else overtime_total
							overtime += over_s.rounding_time
							break

						if overtime_total >= over_s.start_time and overtime_total <= over_s.end_time:
							# jika jumlah lembur lebih besar dari nilai menit awal dan lebih kecil dari nilai rounding, kuraingi jumlah lembur dengan nilai menit awal 
							# jika nilai menit awal sama dengan nol kurangi dengan jumlah lembur untuk menghidari infinite loop
							overtime_total -= over_s.start_time if over_s.start_time else overtime_total
							overtime += over_s.rounding_time
							break

					if copy_overtime == overtime_total:
						frappe.throw("{} minutes is not included in Overtime Settings".format(overtime_total))
			
			# jumlah lembur d ubah menjadi jam
			lembur = abs(flt(overtime / 60, 2))
			row.overtime_today = lembur

			if not row.rejected:
				overtime_total += lembur
		
		# Jumlah Jam Lembur = total jumlah jam lembur
		self.overtime_total = overtime_total
		
	def calculate_overtime_amount(self):
		# ngecek apakah lemburnya di hari libur atau tidak (pakai doc Holiday List)
		overtime_amount = 0
		if self.overtime_total <= 0:
			frappe.throw(f"No overtime hours recorded")
		
		thp = self.get_thp()

		if not self.is_holiday:
			# satu jam pertama
			overtime_amount += flt(
				min(self.overtime_total, 1) / 173 * 1.5 * thp
			)
			# 12/04/2024, PERGANTIAN MEKANISME PERHITUNGAN LEMBUR 
			# overtime_amount += flt(1*1.5/173)*thp				

			# jam berikutny
			if self.overtime_total > 1:
				# 12/04/2024, PERGANTIAN MEKANISME PERHITUNGAN LEMBUR 
				# overtime_amount += flt(temp_total_jam_lembur*2/173)*thp			
				overtime_amount += flt(
					(self.overtime_total - 1) * 2 / 173 * thp
				)		
		else:
			# belum ada pengecekan d attendance
			# is_attendance = frappe.db.sql("""
			# 	SELECT
			# 		shift.is_office_hour
			# 	FROM
			# 		`tabAttendance` att
			# 	LEFT JOIN
			# 		`tabShift Type` shift on att.shift = shift.name
			# 	WHERE
			# 		att.employee = '{}' AND att.attendance_date = '{}'
			# 	LIMIT 1
			# """.format(self.employee, self.posting_date),as_dict=1)

			is_attendance = [0]

			if not is_attendance:
				frappe.throw("Mohon Bersabar ini ujian")

			# JIKA ATTENDANCE NYA DIA IS OFFICE HOUR
			overtime_amount = self.holidays_overtime_amount(
				thp, 
				8 if is_attendance[0] else 7
			)
			
		self.overtime_amount = flt(overtime_amount, self.precision("overtime_amount"))

	def holidays_overtime_amount(self, thp, first_min_hours=8):
		upah_lembur = flt(
			min(self.overtime_total, first_min_hours) * 2 * 1 / 173 * thp
		)
		# print(f'upah lembur 1 - {first_min_hours} jam pertama : 8*2*1/173*{thp} = {flt(8*2*1/173*thp)}')

		if self.overtime_total > first_min_hours:
			upah_lembur += flt(1 * 3 * 1 / 173 * thp)
			# print(f'upah lembur {first_min_hours + 1} jam : 1*3*1/173*{thp} = {flt(1*3*1/173*thp)}')

			jam_lembur = (self.overtime_total - (first_min_hours + 1))
			if jam_lembur > 0:
				upah_lembur += flt(jam_lembur * 4 * 1 / 173 * thp)
				# print(f'upah lembur 10-12 jam : {jam_lembur}*4*1/173*{thp} = {flt(jam_lembur*4*1/173*thp)}')
		
		# print(f'Total Upah Lembur = {upah_lembur}')
		return upah_lembur
	
	def get_thp(self):
		ssa = frappe.db.sql("""
			SELECT 
				COALESCE(base, 0) AS thp
			FROM 
				`tabSalary Structure Assignment`
			WHERE
				employee = %s AND docstatus = 1
			ORDER BY 
				from_date DESC
			LIMIT 1
		""", self.employee)

		if not ssa:
			frappe.throw("Please set Salary Structure Assignment for Employee {}".format(self.employee))
		
		return flt(ssa[0][0] + self.natura_price, self.precision("overtime_amount"))
	
	def before_submit(self):
		for d in self.details:
			generate_duplicate_key(d, "duplicate_key", [self.employee, d.overtime_date])
		
	def on_submit(self):
		self.create_or_update_payment_log()

	def create_or_update_payment_log(self):
		if target_key := self.get("employee_payment_log"):
			doc = frappe.get_doc("Employee Payment Log", target_key)
		else:
			doc = frappe.new_doc("Employee Payment Log")

		doc.employee = self.employee
		doc.company = self.company
		doc.posting_date = self.posting_date
		doc.payroll_date = self.posting_date

		doc.amount = self.overtime_amount

		doc.salary_component = self.get("salary_component")
		doc.save()

		self.db_set("employee_payment_log", doc.name)

	def before_cancel(self):
		for d in self.details:
			generate_duplicate_key(d, "duplicate_key", cancel=1)

	def on_cancel(self):
		self.remove_employee_payment_log()

	def remove_employee_payment_log(self):
		value = self.get("employee_payment_log")
		if not value:
			return
		
		self.db_set("employee_payment_log", "")
		frappe.delete_doc("Employee Payment Log", value)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def employee_sellected_staff_query(
	doctype,
	txt,
	searchfield,
	start,
	page_len,
	filters,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
):
	doctype = "Employee"
	conditions = []
	fields = get_fields(doctype, ["name", "employee_name"])
	ignore_permissions = False

	if reference_doctype and ignore_user_permissions:
		ignore_permissions = has_ignored_field(reference_doctype, doctype) and has_permission(
			doctype,
			ptype="select" if frappe.only_has_select_perm(doctype) else "read",
		)

	mcond = "" if ignore_permissions else get_match_cond(doctype)

	if get_overtime_settings("overtime_for_selected_staff"):
		# telalu malas untuk join table
		filters["designation"] = [
			"in", 
			frappe.get_all("Designation", filters={"can_overtime": 1}, pluck="name")
		]

	return frappe.db.sql(
		"""select {fields} from `tabEmployee`
		where status in ('Active', 'Suspended')
			and docstatus < 2
			and ({key} like %(txt)s
				or employee_name like %(txt)s)
			{fcond} {mcond}
		order by
			(case when locate(%(_txt)s, name) > 0 then locate(%(_txt)s, name) else 99999 end),
			(case when locate(%(_txt)s, employee_name) > 0 then locate(%(_txt)s, employee_name) else 99999 end),
			idx desc,
			name, employee_name
		limit %(page_len)s offset %(start)s""".format(
			**{
				"fields": ", ".join(fields),
				"key": searchfield,
				"fcond": get_filters_cond(doctype, filters, conditions),
				"mcond": mcond,
			}
		),
		{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len},
	)