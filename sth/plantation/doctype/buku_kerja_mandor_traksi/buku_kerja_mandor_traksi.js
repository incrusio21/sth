// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_bkm_controller()

frappe.ui.form.on("Buku Kerja Mandor Traksi", {
  	refresh(frm) {
		frm.set_df_property("hasil_kerja", "cannot_add_rows", true);
		frm.set_df_property("hasil_kerja", "cannot_delete_rows", true);
  	},
	kendaraan(frm){
		frm.call({
			method: "get_details_kendaraan",
			doc: frm.doc,
			callback: () => {
				frm.refresh_fields()
			}
		})
	}
//   tgl_trk(frm) {
//     frappe.db.get_value("Rencana Kerja Harian",
//       { posting_date: frm.doc.tgl_trk },
//       ["name"]
//     ).then(r => {
//       if (Object.keys(r.message).length === 0) {
//         // frappe.throw("Rencana Kerja Harian Tidak Ditemukan!")
//         return
//       }

//       frappe.db.get_doc("Rencana Kerja Harian", r.message.name)
//         .then(doc => {
//           const rkh_kendaraan = doc.kendaraan.map(r => r.item_pengganti || r.item)

//           frm.set_query("kdr", function () {
//             return {
//               filters: [
//                 ["Alat Berat Dan Kendaraan", "name", "in", rkh_kendaraan]
//               ]
//             };
//           });

//           console.log(rkh_kendaraan);
//         });
//     });
//   }
});

sth.plantation.BukuKerjaMandorTraksi = class BukuKerjaMandorTraksi extends sth.plantation.BKMController {
	setup(doc) {
		super.setup(doc)

		this.fieldname_total.push("premi_amount")
        // this.kegiatan_fetch_fieldname.push("have_premi", "min_basis_premi", "rupiah_premi")
        this.max_qty_fieldname = { "hasil_kerja": "volume_basis" }
        
        // this.get_data_rkh_field.push("batch")
        // this.hasil_kerja_update_field.push("have_premi", "min_basis_premi", "rupiah_premi")

        this.setup_bkm(doc)
	}
  	set_query_field() {
		this.frm.set_query("unit", function (doc) {
			return {
				filters: {
					company: ["=", doc.company]
				}
			};
		});

		this.frm.set_query("blok", function (doc) {
			return {
				filters: {
					unit: ["=", doc.unit],
					divisi: ["=", doc.divisi],
				}
			};
		});

		this.frm.set_query("mandor", function () {
            return {
				query: "sth.controllers.queries.employee_designation_query",
              	filters: {
					supervisi: "Traksi"
				}
            };
		});

		this.frm.set_query("kendaraan", function (doc) {
			return {
				filters: {
					tipe_master: ["=", doc.tipe_master_kendaraan]
				} 
			};
		});

		this.frm.set_query("employee", "hasil_kerja", function () {
            return {
				query: "sth.controllers.queries.employee_designation_query",
              	filters: {
					is_traksi: 1
				}
            };
		});
   	}

	update_rate_or_qty_value(item) {
        if (item.parentfield != "hasil_kerja") return

        let doc = this.frm.doc
        
        item.rate = item.rate || this.frm.doc.rupiah_basis
        item.premi_amount = 0
        
        if (!self.manual_hk){
            item.hari_kerja = Math.min(flt(item.qty / doc.volume_basis), 1)
        }
        
        if (doc.have_premi && doc.persentase_premi && item.qty >= doc.min_basis_premi){
            item.premi_amount = doc.rupiah_premi
        }
    }

	update_value_after_amount(item) {
        item.sub_total = flt(item.amount) + flt(item.premi_amount)
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorTraksi);