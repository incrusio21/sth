
frappe.ui.form.on("Employee Grievance", {
  async grievance_against(frm) {
    if (frm.doc.grievance_against_party != "Employee") return;
    if (!frm.doc.grievance_against) return;

    const employee = await frappe.db.get_doc(
      "Employee",
      frm.doc.grievance_against
    );
    let department_name = "";

    if (employee.department) {
      const department = await frappe.db.get_value(
        "Department",
        employee.department,
        "department_name"
      );

      department_name = department.message?.department_name || "";
    }

    await frm.set_value("department", department_name);
    await frm.set_value("unit", employee.unit);
    await frm.set_value("divisi", employee.nama_divisi);
    await frm.set_value("golongan", employee.grade);
  }
});
