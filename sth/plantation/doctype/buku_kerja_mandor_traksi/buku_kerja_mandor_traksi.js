// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_bkm_controller()

frappe.ui.form.on("Buku Kerja Mandor Traksi", {
	posting_date(frm){
		frm.cscript.get_details_data({
			method: "sth.plantation.doctype.buku_kerja_mandor_traksi.buku_kerja_mandor_traksi.get_details_employee",
			args: {
				childrens: frm.doc.hasil_kerja,
				posting_date: frm.doc.posting_date
			}
		})
	},
	company(frm){
		frm.cscript.get_kegiatan(frm.doc.task)
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

frappe.ui.form.on("Detail BKM Traksi Kegiatan", {
	task_add(frm, cdt, cdn){
		let data = frappe.get_doc(cdt, cdn)
		
		data.divisi = frm.doc.divisi
		data.blok = frm.doc.blok
		data.batch = frm.doc.batch
		data.project = frm.doc.project

		let index = data.idx - 1
		data.kmhm_awal = index == 0 ? frm.doc.kmhm_awal : 
			(frm.doc.task[index-1].kmhm_akhir || frm.doc.task[index-1].kmhm_awal)

		frm.refresh_field("task")
	},
	kegiatan(frm, cdt, cdn){
		let data = frappe.get_doc(cdt, cdn)
		if(!data.kegiatan) return

		frm.cscript.get_kegiatan([data])
	},
	kmhm_akhir(frm, cdt, cdn){
		frappe.call({
			method: "set_details_diffrence",
			doc: frm.doc,
			callback: (data) => {
				frm.refresh_field("task")

				frm.cscript.calculate_total(null, null, "hasil_kerja");
			}
		})
	},
})

frappe.ui.form.on("Detail BKM Hasil Kerja Traksi", {
	hasil_kerja_add(frm, cdt, cdn){
		let data = frappe.get_doc(cdt, cdn)
		
		data.position = frm.doc.position
		
		let default_employee = frm.doc[`default_${frappe.scrub(data.position)}`]
		frappe.model.set_value(cdt, cdn, "employee", default_employee)
	},
	employee(frm, cdt, cdn){
		let data = frappe.get_doc(cdt, cdn)

		frm.cscript.get_details_data({
			method: "sth.plantation.doctype.buku_kerja_mandor_traksi.buku_kerja_mandor_traksi.get_details_employee",
			args: {
				childrens: [data],
				posting_date: frm.doc.posting_date
			}
		})
	}
})

sth.plantation.BukuKerjaMandorTraksi = class BukuKerjaMandorTraksi extends sth.plantation.BKMController {
	setup(doc) {
		super.setup(doc)

		let me = this

		this.fieldname_total.push("premi_amount")
		this.skip_calculate_table = ["task"]
		this.kegiatan_fetch_fieldname = []

		// calculate grand total lagi jika field berubah
		for (const fieldname of ["base", "total_hari"]) {
			frappe.ui.form.on("Detail BKM Hasil Kerja Traksi", fieldname, function (frm, cdt, cdn) {
				me.calculate_total(cdt, cdn)
			});
		}

		// calculate grand total lagi jika field berubah
		for (const fieldname of ["hasil_kerja", "upah_hasil", "task_remove"]) {
			frappe.ui.form.on("Detail BKM Traksi Kegiatan", fieldname, function (frm, cdt, cdn) {
				for (const task of frm.doc.task) {
					task.amount = flt(task.hasil_kerja * task.upah_hasil)
				}

				me.calculate_total(null,null,"hasil_kerja")
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

		this.frm.set_query("divisi", function (doc) {
			return {
				filters: {
					unit: ["=", doc.unit]
				}
			};
		});

		this.frm.set_query("blok", function (doc) {
			return {
				filters: {
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

		this.frm.set_query("kegiatan", "task", function () {
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
	
	get_kegiatan(data){
		this.get_details_data({
			method: "sth.plantation.doctype.buku_kerja_mandor_traksi.buku_kerja_mandor_traksi.get_details_kegiatan",
			args: {
				childrens: data,
				company: this.frm.doc.company
			}
		})
	}

	get_details_data(opts){
		if(opts.args.childrens.length == 0) return

		let me = this
		frappe.call({
			method: opts.method,
			args: opts.args,
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
		
		this.calculate_total(null,null,"hasil_kerja")
	}

	custom_amount_value(item){
		let doc = this.frm.doc
		
		let is_basic_salary = true
		let amount = flt(item.base/item.total_hari)

		item.premi_amount = 0
		for (const task of doc.task) {
			let kegiatan = JSON.parse(task.company_details)[item.position || "Operator"] || {}

			if (!kegiatan.use_basic_salary){
				if(is_basic_salary){
					amount = 0
					is_basic_salary = false
				}
				
				amount += task.amount
			}

			let premi_amount = 0
			if(in_list(["Alat Berat"], doc.tipe_master_kendaraan)){
				premi_amount += flt(task.premi_heavy_equipment)
			}else{
				premi_amount += flt((task.hasil_kerja || 0) * 
					this.set_premi_non_heavy_equipment(
						item, kegiatan
					)
				)
			}

			item.premi_amount += premi_amount
		}
		
		// if (!doc.manual_hk){
		// 	item.hari_kerja = Math.min(flt(item.qty / doc.volume_basis), 1)
        // }

		item.amount = is_basic_salary ? (item.amount || amount) : amount
	}

	set_premi_non_heavy_equipment(item, kegiatan){
		let doc = this.frm.doc
		let fields = item.is_holiday ? "holiday" : "workday"
		
		let premi = kegiatan[`ump_as_${fields}`] ? flt(doc.ump_bulanan/item.total_hari) :
			kegiatan[`${fields}`]
		
		return premi || 0
	}

	update_value_after_amount(item) {
        item.sub_total = flt(item.amount || 0) + flt(item.premi_amount || 0)
    }
}

cur_frm.script_manager.make(sth.plantation.BukuKerjaMandorTraksi);