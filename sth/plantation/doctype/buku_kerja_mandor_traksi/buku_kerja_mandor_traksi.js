// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_bkm_controller()

frappe.ui.form.on("Buku Kerja Mandor Traksi", {
  	refresh(frm) {
		frm.set_df_property("hasil_kerja", "cannot_add_rows", true);
		frm.set_df_property("hasil_kerja", "cannot_delete_rows", true);
  	},
	posting_date(frm){
		frm.cscript.get_employee_data({
			childrens: frm.doc.hasil_kerja,
			posting_date: frm.doc.posting_date
		})
	},
	kmhm_akhir(frm){
		frm.set_value("selisih_kmhm", flt(frm.doc.kmhm_akhir) - flt(frm.doc.kmhm_awal))
	},
	kmhm_awal(frm){
		frm.set_value("selisih_kmhm", flt(frm.doc.kmhm_akhir) - flt(frm.doc.kmhm_awal))
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

frappe.ui.form.on("Detail BKM Hasil Kerja Traksi", {
	employee(frm, cdt, cdn){
		let data = frappe.get_doc(cdt, cdn)

		frm.cscript.get_employee_data({
			childrens: [data],
			posting_date: frm.doc.posting_date
		})
	}
})

sth.plantation.BukuKerjaMandorTraksi = class BukuKerjaMandorTraksi extends sth.plantation.BKMController {
	setup(doc) {
		super.setup(doc)

		this.fieldname_total.push("premi_amount")
        this.kegiatan_fetch_fieldname.push(
			"workday as premi_workday", "holiday as premi_holiday", 
			"workday_base as ump_as_workday", "holiday_base as ump_as_holiday"
		)

		// calculate grand total lagi jika field berubah
		for (const fieldname of ["base", "total_hari"]) {
			frappe.ui.form.on("Detail BKM Hasil Kerja Traksi", fieldname, function (frm, cdt, cdn) {
				me.calculate_total(cdt, cdn)
			});
		}
        // this.get_data_rkh_field.push("batch")
        this.hasil_kerja_update_field.push("premi_workday", "premi_holiday", "ump_bulanan", "ump_as_workday", "ump_as_holiday")

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

	kendaraan(doc){
		let me = this
		
		this.frm.call({
			method: "get_details_kendaraan",
			doc: doc,
			callback: () => {
				me.calculate_total(null, null, "hasil_kerja")
			}
		})
	}

	get_employee_data(args){
		if(!args.childrens) return

		let me = this
		frappe.call({
			method: "sth.plantation.doctype.buku_kerja_mandor_traksi.buku_kerja_mandor_traksi.get_details_employee",
			args: args,
			freeze: true,
			callback: function (data) {
				me.frm.doc.hasil_kerja = data.message
				me.calculate_total(null, null, "hasil_kerja")
			}
		})
	}
	
	update_rate_or_qty_value(item) {
        if (item.parentfield != "hasil_kerja") return

        let doc = this.frm.doc
        
		if (!in_list(["Dump Truck"], doc.tipe_master_kendaraan)){
			item.rate = flt(item.base/item.total_hari)
		}
        
		if (!doc.manual_hk){
			item.hari_kerja = Math.min(flt(item.qty / doc.volume_basis), 1)
        }
        
		if(doc.is_heavy_equipment){
			item.premi_amount = flt(doc.premi_heavy_equipment)
		}else{
			this.set_premi_non_heavy_equipment(item)
		}
    }

	set_premi_non_heavy_equipment(item){
		let doc = this.frm.doc
		let fields = item.is_holiday ? "holiday" : "workday"
		let premi = doc[`ump_as_${fields}`] ? flt(doc.ump_bulanan/item.total_hari) :
			doc[`premi_${fields}`]
		
		item.premi_amount = flt(premi*item.qty)
	}

	update_value_after_amount(item) {
        item.sub_total = flt(item.amount) + flt(item.premi_amount)
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorTraksi);