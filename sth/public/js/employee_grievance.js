frappe.ui.form.on("Employee Grievance", {
  async grievance_against(frm) {
    if (frm.doc.grievance_against_party != "Employee") return;
    if (!frm.doc.grievance_against) return;

    const employee = await frappe.db.get_doc(
      "Employee",
      frm.doc.grievance_against
    );

    frm.set_value("department", employee.department);
    frm.set_value("unit", employee.unit);
    frm.set_value("divisi", employee.nama_divisi);
    frm.set_value("golongan", employee.grade);
  }
});