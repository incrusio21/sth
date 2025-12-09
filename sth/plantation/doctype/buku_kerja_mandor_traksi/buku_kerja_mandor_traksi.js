// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_bkm_controller()

frappe.ui.form.on("Buku Kerja Mandor Traksi", {
  	refresh(frm) {

  	},
	posting_date(frm){
		frm.cscript.get_employee_data({
			childrens: frm.doc.hasil_kerja,
			posting_date: frm.doc.posting_date
		})
	},
	company(frm){
		frm.cscript.get_kegiatan_data({
			childrens: frm.doc.hasil_kerja,
			company: frm.doc.company
		})
	},
	kendaraan(frm){
		frappe.call({
			method: "get_details_kendaraan",
			doc: frm.doc,
			callback: (data) => {
				frm.cscript.calculate_total(null,null,"hasil_kerja");
			}
		})
	}
	// kmhm_akhir(frm){
	// 	frm.trigger("premi_heavy_equipment")
	// },
	// kmhm_awal(frm){
	// 	frm.trigger("premi_heavy_equipment")
	// },
	// premi_heavy_equipment(frm){
	// 	frappe.call({
	// 		method: "set_premi_heavy_equipment",
	// 		doc: frm.doc,
	// 		freeze: true,
	// 		callback: function (data) {
	// 			me.calculate_total(null, null, "hasil_kerja")
	// 		}
	// 	})
	// }
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
	hasil_kerja_add(frm, cdt, cdn){
		frappe.model.set_value(cdt, cdn, "employee", frm.doc.default_employee)
	},
	kegiatan(frm, cdt, cdn){
		let data = frappe.get_doc(cdt, cdn)
		if(!data.kegiatan) return

		frm.cscript.get_kegiatan_data({
			childrens: [data],
			company: frm.doc.company
		})
	},
	kmhm_ahkir(frm, cdt, cdn){
		frappe.call({
			method: "get_details_diffrence",
			doc: frm.doc,
			callback: (data) => {
				frm.cscript.calculate_total(null,null,"hasil_kerja");
			}
		})
	},
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
		this.kegiatan_fetch_fieldname = []

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

		this.frm.set_query("kegiatan", "hasil_kerja", function () {
            return {
              	filters: {
					tipe_kegiatan: "Traksi"
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

	get_kegiatan_data(args){
		if(args.childrens.length == 0) return

		let me = this
		frappe.call({
			method: "sth.plantation.doctype.buku_kerja_mandor_traksi.buku_kerja_mandor_traksi.get_details_kegiatan",
			args: args,
			freeze: true,
			callback: function (data) {
				me._set_values_for_item_list(data.message);
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
				me._set_values_for_item_list(data.message);
			}
		})
	}
	
	_set_values_for_item_list(children) {
		for (const child of children) {
			let data = frappe.get_doc(child.doctype, child.name)

			for (const [key, value] of Object.entries(child)) {
				data[key] = value 
			}
		}

		this.calculate_total(children[0].doctype, children[0].name)
	}

	update_rate_or_qty_value(item) {
        if (item.parentfield != "hasil_kerja") return

        let doc = this.frm.doc
        item.rate = item.rupiah_basis

		if (!in_list(["Dump Truck"], doc.tipe_master_kendaraan)){
			item.rate = flt(item.base/item.total_hari)
		}
        
		if (!doc.manual_hk){
			item.hari_kerja = Math.min(flt(item.qty / doc.volume_basis), 1)
        }
        
		if(in_list(["Alat Berat"], doc.tipe_master_kendaraan)){
			item.premi_amount = flt(item.premi_heavy_equipment)
		}else{
			this.set_premi_non_heavy_equipment(item)
		}
    }

	set_premi_non_heavy_equipment(item){
		let doc = this.frm.doc
		let fields = item.is_holiday ? "holiday" : "workday"
		let premi = item[`ump_as_${fields}`] ? flt(doc.ump_bulanan/item.total_hari) :
			item[`premi_${fields}`]
		
		item.premi_amount = flt(premi*item.qty)
	}

	update_value_after_amount(item) {
        item.sub_total = flt(item.amount) + flt(item.premi_amount)
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorTraksi);