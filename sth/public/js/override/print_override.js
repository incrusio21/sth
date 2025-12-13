const patch = () => {
  if (!frappe.ui.form || !frappe.ui.form.PrintView) {
    return false;
  }

  // override
  frappe.ui.form.PrintView.prototype.set_default_print_format = function () {
    console.log("run override set_default_print_format");
    if (
      frappe.meta
        .get_print_formats(this.frm.doctype)
        .includes(this.print_format_selector.val())
    )
      return;

    if (this.frm.doctype == "Quotation") {
      frappe.db.get_doc(this.frm.doctype, this.frm.docname)
        .then((res) => {
          const default_print_format = res.jenis_berikat == "Ya" ? "PF SCR Berikat" : "PF SCR Non Berikat";

          this.print_format_selector.empty();
          this.print_format_selector.val(default_print_format);
          return;
        });
    }

    this.print_format_selector.empty();
    this.print_format_selector.val(this.frm.meta.default_print_format || "");
  };

  return true;
};

if (!patch()) {
  let tries = 0;
  const t = setInterval(() => {
    tries++;
    if (patch() || tries > 10) {
      clearInterval(t);
    }
  }, 200);
}