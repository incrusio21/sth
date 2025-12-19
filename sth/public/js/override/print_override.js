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
      frappe.call({
        method: "sth.api.get_doc_ignore_perm",
        args: {
          doctype: this.frm.doctype,
          name: this.frm.docname
        },
        callback: (r) => {
          if (!r.message) return;
          const default_print_format = r.message.jenis_berikat == "Ya" ? "PF SCR Berikat" : "PF SCR Non Berikat";

          this.print_format_selector.empty();
          this.print_format_selector.val(default_print_format);

          this.refresh_print_format();
          return;
        }
      });
    }

    if (this.frm.doctype == "Sales Order") {
      frappe.call({
        method: "sth.api.get_doc_ignore_perm",
        args: {
          doctype: this.frm.doctype,
          name: this.frm.docname
        },
        callback: (r) => {
          if (!r.message) return;
          const default_print_format = r.message.jenis_berikat == "Ya" ? "PF Kontrak Kawasan Berikat" : "PF Kontrak Non Berikat";

          this.print_format_selector.empty();
          this.print_format_selector.val(default_print_format);

          this.refresh_print_format();
          return;
        }
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