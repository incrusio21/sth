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

  if (this.frm.doctype == "Delivery Note") {
    frappe.call({
      method: "sth.api.get_doc_ignore_perm",
      args: {
        doctype: this.frm.doctype,
        name: this.frm.docname
      },
      callback: (r) => {
        if (!r.message) return;

        if (r.message.tempat_penyerahan == "FRANCO" || r.message.tempat_penyerahan == "LOCCO") {
          const default_print_format = r.message.tempat_penyerahan == "FRANCO" ? "PF DO FRANCO" : "PF DO LOCCO";

          this.print_format_selector.empty();
          this.print_format_selector.val(default_print_format);

          this.refresh_print_format();
          return;
        }
      }
    });
  }

  this.print_format_selector.empty();
  this.print_format_selector.val(this.frm.meta.default_print_format || "");
};


frappe.ui.form.PrintView = class CustomPrint extends frappe.ui.form.PrintView {
  async printit() {
    if (this.frm.doctype == "Purchase Order") {
      const counter = this.frm.doc.print_counter + 1
      await frappe.xcall("sth.utils.print.update_print_counter", { doctype: this.frm.doctype, docname: this.frm.docname, val: counter })
    }

    super.printit()
  }
}
