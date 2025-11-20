frappe.ui.form.on("Employee", {
  date_of_joining(frm) {
    if (frm.doc.date_of_joining) {
      frm.set_value("custom_employment_tenure", getMonthDifference(frm.doc.date_of_joining));
    }
  }
});

function getMonthDifference(dateString) {
  const inputDate = new Date(dateString);
  const now = new Date();

  let years = now.getFullYear() - inputDate.getFullYear();
  let months = now.getMonth() - inputDate.getMonth();

  let totalMonths = years * 12 + months;

  if (now.getDate() < inputDate.getDate()) {
    totalMonths -= 1;
  }

  tahun = Math.floor(totalMonths / 12)
  bulan = totalMonths % 12

  return `${tahun} Tahun ${bulan} Bulan`;
}