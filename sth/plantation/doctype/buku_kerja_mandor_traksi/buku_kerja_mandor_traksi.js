// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Buku Kerja Mandor Traksi", {
  tgl_trk(frm) {
    frappe.db.get_value("Rencana Kerja Harian",
      { posting_date: frm.doc.tgl_trk },
      ["name"]
    ).then(r => {
      if (Object.keys(r.message).length === 0) return

      frappe.db.get_doc("Rencana Kerja Harian", r.message.name)
        .then(doc => {
          const rkh_kendaraan = doc.kendaraan.map(r => r.item_pengganti || r.item)

          frm.set_query("kdr", function () {
            return {
              filters: [
                ["Alat Berat Dan Kendaraan", "name", "in", rkh_kendaraan]
              ]
            };
          });

          console.log(rkh_kendaraan);
        });
    });
  },
  hk(frm) {
    const pekerjaan_subtotal = (frm.doc.hk * frm.doc.rp_sat) + frm.doc.premi_kgt

    if (frm.doc.jk == "Dump Truck") {
      frm.set_value("pekerjaan_subtotal", pekerjaan_subtotal)
    }
  },
  premi(frm) {
    const operator_subtotal = frm.doc.uph + frm.doc.premi

    if (frm.doc.jk != "Dump Truck") {
      frm.set_value("operator_subtotal", operator_subtotal)
    }
  }
});
