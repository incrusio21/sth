// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_rencana_kerja_controller()

frappe.ui.form.on("Rencana Kerja Bulanan Pengangkutan Panen", {
	blok(frm) {
        frappe.call({
            method: "sth.plantation.doctype.rencana_kerja_bulanan_pengangkutan_panen.rencana_kerja_bulanan_pengangkutan_panen.get_tonase",
            frezee: true,
            args: {
                rkb: frm.doc.rencana_kerja_bulanan,
                blok: frm.doc.blok,
            },
            callback: function (data) {
                frm.set_value("tonase", data.message)
            }
        })
	}
});

sth.plantation.RencanaKerjaBulananPengangkutan = class RencanaKerjaBulananPengangkutan extends sth.plantation.RencanaKerjaController {
    setup(doc) {
        super.setup(doc)

        this.update_field_duplicate = [
            {
                fieldtype: "Float",
                fieldname: "jarak_pks",
                in_list_view: 1,
                label: __("Jarak Ke PKS")
            }
        ]
        
        this.fieldname_duplicate_edit = {"jarak_pks": "jarak_pks"}

        let me = this
        for (const fieldname of ["tonase", "jarak_pks"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function(doc, cdt, cdn) {
                me.calculate_total(cdt, cdn, "kendaraan")
            });
        }
    }

    set_query_field(){
        super.set_query_field()
    
        this.frm.set_query("kode_kegiatan", function(doc){
            return{
                filters: {
                    company: doc.company,
                    tipe_kegiatan: "Traksi",
                    is_group: 0
                }
            }
        })

        this.frm.set_query("item", "kendaraan", function(doc){
            if(!doc.unit){
                frappe.throw("Please Select RKB First")
            }

		    return{
		        filters: {
                    unit: doc.unit
                }
		    }
		})

        this.frm.set_query("item", "biaya_angkut", function(doc){
		    return{
		        filters: {
                    tipe_kegiatan: "Biaya Umum",
                    is_group: 0,
                }
		    }
		})

    }
    
    update_rate_or_qty_value(item){
        if(item.parentfield == "kendaraan"){
            let doc = this.frm.doc
            item.qty = flt(doc.tonase / item.kap_kg * doc.jarak_pks * 2, precision("amount", item))
        }
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananPengangkutan);