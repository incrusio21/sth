// override
frappe.ui.form.PrintView.prototype.set_default_print_format = function () {
  console.log("run override set_default_print_format");

  // kalau print format sudah valid, stop
  if (
    frappe.meta
      .get_print_formats(this.frm.doctype)
      .includes(this.print_format_selector.val())
  ) {
    return;
  }

  const doctype = this.frm.doctype;

  // helper untuk set & refresh
  const setPrintFormat = (format) => {
    if (!format) return;
    this.print_format_selector.empty();
    this.print_format_selector.val(format);
    this.refresh_print_format();
  };

  // default fallback
  const setDefaultFromMeta = () => {
    setPrintFormat(this.frm.meta.default_print_format || "");
  };

  // doctype yang perlu fetch doc
  const doctypesNeedServer = [
    "Quotation",
    "Sales Order",
    "Delivery Order",
    "Payment Entry",
    "Timbangan"
  ];

  if (!doctypesNeedServer.includes(doctype)) {
    setDefaultFromMeta();
    return;
  }

  frappe.call({
    method: "sth.api.get_doc_ignore_perm",
    args: {
      doctype: doctype,
      name: this.frm.docname
    },
    callback: (r) => {
      if (!r.message) return;

      const doc = r.message;
      let format = "";

      switch (doctype) {

        case "Quotation":
          format = doc.jenis_berikat == "Ya"
            ? "PF SCR Berikat"
            : "PF SCR Non Berikat";
          break;

        case "Sales Order":
          format = doc.jenis_berikat == "Ya"
            ? "PF Kontrak Kawasan Berikat"
            : "PF Kontrak Non Berikat";
          break;

        case "Delivery Order":
          if (["FRANCO", "LOCCO"].includes(doc.tempat_penyerahan)) {
            format = doc.tempat_penyerahan == "FRANCO"
              ? "PF DO FRANCO"
              : "PF DO LOCCO";
          }
          break;

        case "Payment Entry":

          const isAdvanceOrPPD = (doc.references || []).some(r =>
            [
              "Employee Advance",
              "Pertanggungjawaban Perjalanan Dinas"
            ].includes(r.reference_doctype)
          );

          if (isAdvanceOrPPD) {
            format = "PF PV SPD Dan LPPD";
            break;
          }

          const paymentTypeMap = {
            "Pay": "PF PV KAS",
            "Internal Transfer": "PF PV TRANSAKSI INTERNAL ANTAR PT",
            "Receive": "PF RV"
          };

          format = paymentTypeMap[doc.payment_type];
          break;

        case "Timbangan":
          if (doc.receive_type == "TBS Internal" || doc.receive_type == "TBS Eksternal") {
            format = doc.receive_type == "TBS Internal" ? "PF Slip Penerimaan TBS Internal" : "PF Slip Penerimaan TBS External";
          }

          if (doc.type == "Dispatch" && doc.dispatch_type == "Product") {
            if (doc.kode_barang == "CPO") format = "Slip Pengiriman CPO Product";
            if (doc.kode_barang == "40000002") format = "Slip Pengiriman Palm Kernel Product";
          }

          break;
      }

      setPrintFormat(format || this.frm.meta.default_print_format);
    }
  });
};

// frappe.ui.form.PrintView.prototype.set_default_print_format = function () {
//   console.log("run override set_default_print_format");
//   if (
//     frappe.meta
//       .get_print_formats(this.frm.doctype)
//       .includes(this.print_format_selector.val())
//   )
//     return;

//   if (this.frm.doctype == "Quotation") {
//     frappe.call({
//       method: "sth.api.get_doc_ignore_perm",
//       args: {
//         doctype: this.frm.doctype,
//         name: this.frm.docname
//       },
//       callback: (r) => {
//         if (!r.message) return;
//         const default_print_format = r.message.jenis_berikat == "Ya" ? "PF SCR Berikat" : "PF SCR Non Berikat";

//         this.print_format_selector.empty();
//         this.print_format_selector.val(default_print_format);

//         this.refresh_print_format();
//         return;
//       }
//     });
//   }

//   if (this.frm.doctype == "Sales Order") {
//     frappe.call({
//       method: "sth.api.get_doc_ignore_perm",
//       args: {
//         doctype: this.frm.doctype,
//         name: this.frm.docname
//       },
//       callback: (r) => {
//         if (!r.message) return;
//         const default_print_format = r.message.jenis_berikat == "Ya" ? "PF Kontrak Kawasan Berikat" : "PF Kontrak Non Berikat";

//         this.print_format_selector.empty();
//         this.print_format_selector.val(default_print_format);

//         this.refresh_print_format();
//         return;
//       }
//     });
//   }

//   if (this.frm.doctype == "Delivery Order") {
//     frappe.call({
//       method: "sth.api.get_doc_ignore_perm",
//       args: {
//         doctype: this.frm.doctype,
//         name: this.frm.docname
//       },
//       callback: (r) => {
//         if (!r.message) return;

//         if (r.message.tempat_penyerahan == "FRANCO" || r.message.tempat_penyerahan == "LOCCO") {
//           const default_print_format = r.message.tempat_penyerahan == "FRANCO" ? "PF DO FRANCO" : "PF DO LOCCO";

//           this.print_format_selector.empty();
//           this.print_format_selector.val(default_print_format);

//           this.refresh_print_format();
//           return;
//         }
//       }
//     });
//   }

//   if (this.frm.doctype == "Payment Entry") {
//     frappe.call({
//       method: "sth.api.get_doc_ignore_perm",
//       args: {
//         doctype: this.frm.doctype,
//         name: this.frm.docname
//       },
//       callback: (r) => {
//         if (!r.message) return;
//         let default_print_format = "";
//         const payment_type = r.message.payment_type;
//         let isRefAdvanceOrPPD = r.message.references.some(row =>
//           row.reference_doctype == "Employee Advance" ||
//           row.reference_doctype == "Pertanggungjawaban Perjalanan Dinas"
//         );

//         if (isRefAdvanceOrPPD) {
//           default_print_format = "PF PV SPD Dan LPPD"

//           this.print_format_selector.empty();
//           this.print_format_selector.val(default_print_format);

//           this.refresh_print_format();
//           return;
//         }

//         if (payment_type == "Pay") default_print_format = "PF PV KAS";
//         if (payment_type == "Internal Transfer") default_print_format = "PF PV TRANSAKSI INTERNAL ANTAR PT";
//         if (payment_type == "Receive") default_print_format = "PF RV";
//         // console.log(r.message.references, isRefAdvanceOrPPD);

//         this.print_format_selector.empty();
//         this.print_format_selector.val(default_print_format);

//         this.refresh_print_format();
//         return;
//       }
//     });
//   }

//   this.print_format_selector.empty();
//   this.print_format_selector.val(this.frm.meta.default_print_format || "");
// };


frappe.ui.form.PrintView = class CustomPrint extends frappe.ui.form.PrintView {
  async printit() {
    if (this.frm.doctype == "Purchase Order") {
      const counter = this.frm.doc.print_counter + 1
      await frappe.xcall("sth.utils.print.update_print_counter", { doctype: this.frm.doctype, docname: this.frm.docname, val: counter })
    }

    super.printit()
  }
}
