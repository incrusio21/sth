frappe.ui.form.on("Task", {
  tipe_kriteria(frm) {
    frm.set_query("issue", () => {
      return {
        filters: {
          issue_type: frm.doc.tipe_kriteria
        }
      }
    });
    console.log(frm.doc.tipe_kriteria);
  }
});