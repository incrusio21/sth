// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sounding Stock CPO di BST", {
    setup(frm) {
        erpnext.queries.setup_queries(frm, "Warehouse", function (doc) {
            return {
                filters: {
                    company: doc.company,
                    is_group: 0,
                    unit: doc.unit
                }
            }
        })
    },

    refresh(frm) {

    },

    pabrik(frm) {
        if (!frm.doc.pabrik) return
        frm.trigger('get_warehouse_bst')
    },

    get_data(frm) {
        frm.call("get_data").then(() => {
            frm.refresh()
        })
    },

    get_warehouse_bst(frm) {
        const method = frappe.model.get_server_module_name(cur_frm.doctype) + ".get_warehouse_bst"
        return frappe.xcall(method, { pabrik: frm.doc.pabrik }).then((res) => {
            if (!res.length) {
                frappe.throw(`Silahkan set default warehouse di pabrik ${frm.doc.pabrik}`)
            }

            res.forEach(row => {
                if (row.name == "BST 01") {
                    frm.set_value("gudang", row.gudang)
                } else {
                    frm.set_value("gudang_2", row.gudang)
                }
            });
        })
    },

    get_ukuran_sounding(tinggi, bst, pabrik) {
        const method = frappe.model.get_server_module_name(cur_frm.doctype) + ".get_ukuran_sounding"
        return frappe.xcall(method, { tinggi, bst, pabrik })
    },

    get_berat_jenis_suhu(pabrik = "", suhu) {
        const method = frappe.model.get_server_module_name(cur_frm.doctype) + ".get_berat_jenis"
        return frappe.xcall(method, { pabrik, suhu })
    },

    ukuran_hasil_sounding(frm) {
        frm.events.get_ukuran_sounding(frm.doc.ukuran_hasil_sounding, "BST 01", frm.doc.pabrik || '').then((res) => {
            frm.set_value("ukuran_hasil_sounding_kg", res)
            frm.set_value("tonase_sebenarnya", frm.doc.ukuran_hasil_sounding_kg * frm.doc.berat_jenis_suhu)
        })
    },

    ukuran_hasil_sounding_2(frm) {
        frm.events.get_ukuran_sounding(frm.doc.ukuran_hasil_sounding_2, "BST 02", frm.doc.pabrik || '').then((res) => {
            frm.set_value("ukuran_hasil_sounding_kg_2", res)
            frm.set_value("tonase_sebenarnya_2", frm.doc.ukuran_hasil_sounding_kg_2 * frm.doc.berat_jenis_suhu_2)
        })
    },

    hasil_suhu(frm) {
        if (!frm.doc.hasil_suhu) return
        frm.events.get_berat_jenis_suhu(frm.doc.pabrik, frm.doc.hasil_suhu).then((res) => {
            frm.set_value("berat_jenis_suhu", res)
        })
    },

    hasil_suhu_2(frm) {
        frm.events.get_berat_jenis_suhu(frm.doc.pabrik, frm.doc.hasil_suhu_2).then((res) => {
            frm.set_value("berat_jenis_suhu_2", res)
        })
    },

    berat_jenis_suhu(frm) {
        frm.set_value("tonase_sebenarnya", frm.doc.ukuran_hasil_sounding_kg * frm.doc.berat_jenis_suhu)
    },

    berat_jenis_suhu_2(frm) {
        frm.set_value("tonase_sebenarnya_2", frm.doc.ukuran_hasil_sounding_kg_2 * frm.doc.berat_jenis_suhu_2)
    },

    tonase_sebenarnya(frm) {
        frm.trigger('calculate_produksi_cpo')
    },

    tonase_sebenarnya_2(frm) {
        frm.trigger('calculate_produksi_cpo')
    },

    produksi_cpo(frm) {
        frm.trigger('calculate_oer_netto')
    },

    calculate_oer_netto(frm) {
        const oer_netto_1 = frm.doc.tbs_olah == 0 ? 0 : frm.doc.produksi_cpo / frm.doc.tbs_olah * 100
        const oer_netto_2 = frm.doc.tbs_olah == 0 ? 0 : frm.doc.produksi_cpo / (frm.doc.tbs_olah - frm.doc.potongan_sortasi) * 100
        frm.set_value("oer_netto_1", oer_netto_1)
        frm.set_value("oer_netto_2", oer_netto_2)
    },

    calculate_produksi_cpo(frm) {
        const total = (frm.doc.tonase_sebenarnya + frm.doc.tonase_sebenarnya_2) - frm.doc.stock_bst
        frm.set_value("produksi_cpo", total)
    },

});
