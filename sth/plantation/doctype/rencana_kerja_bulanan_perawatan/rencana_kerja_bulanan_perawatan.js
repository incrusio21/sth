// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

sth.plantation.setup_rencana_kerja_controller()

frappe.ui.form.on("Rencana Kerja Bulanan Perawatan", {
    refresh(frm) {
        // if (cur_frm.doc.docstatus != 1) return

        if (
            frm.doc.tambahan_rate_basis == 0 &&
            frm.doc.tambahan_volume_basis == 0 &&
            frm.doc.tambahan_target_volume == 0 &&
            frm.doc.tambahan_qty_tenaga_kerja == 0
        ) {
            frm.toggle_display([
                "tambahan_rate_basis",
                "tambahan_volume_basis",
                "tambahan_target_volume",
                "tambahan_qty_tenaga_kerja"
            ], false);
        }

        // frappe.call({
        //     method: "sth.plantation.doctype.rencana_kerja_bulanan_perawatan.rencana_kerja_bulanan_perawatan.get_pengajuan_budget_tambahan",
        //     args: {
        //         rencana_kerja_bulanan: frm.doc.rencana_kerja_bulanan,
        //         kode_kegiatan: frm.doc.kode_kegiatan,
        //     },
        //     callback: function (r) {
        //         if (!r.message) return
        //         const { pengajuan_budget_tambahan, material } = r.message

        //         frm.set_value("tambahan_kode_kegiatan", pengajuan_budget_tambahan.kode_kegiatan);
        //         frm.set_value("tambahan_rate_basis", pengajuan_budget_tambahan.rate_basis);
        //         frm.set_value("tambahan_volume_basis", pengajuan_budget_tambahan.volume_basis);
        //         frm.set_value("tambahan_tipe_kegiatan", pengajuan_budget_tambahan.tipe_kegiatan);
        //         frm.set_value("tambahan_target_volume", pengajuan_budget_tambahan.target_volume);
        //         frm.set_value("tambahan_qty_tenaga_kerja", pengajuan_budget_tambahan.qty_tenaga_kerja);

        //         material.forEach(d => {
        //             let row = frm.add_child("tambahan_material", d);
        //         });

        //         frm.refresh_fields()
        //         console.log(r.message)
        //     }
        // })
    },
    kategori_kegiatan(frm) {
        frm.set_value("blok", "")
        frm.set_value("batch", "")
    }
});

sth.plantation.RencanaKerjaBulananPerawatan = class RencanaKerjaBulananPerawatan extends sth.plantation.RencanaKerjaController {
    setup(doc) {
        super.setup(doc)

        let me = this
        for (const fieldname of ["qty_basis", "upah_per_basis", "premi"]) {
            frappe.ui.form.on(doc.doctype, fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }

    set_query_field() {
        super.set_query_field()

        this.frm.set_query("kategori_kegiatan", function () {
            return {
                filters: {
                    is_perawatan: 1
                }
            }
        })

        this.frm.set_query("kode_kegiatan", function (doc) {
            if (!(doc.company && doc.kategori_kegiatan)) {
                frappe.throw("Please Select Kategori Kegiata and Company First")
            }

            return {
                filters: {
                    is_group: 0,
                    kategori_kegiatan: doc.kategori_kegiatan,
                    company: doc.company
                }
            }
        })
    }

    get_blok_for_duplicate() {
        if (!this.frm.doc.is_bibitan) {
            super.get_blok_for_duplicate()
        } else {
            let me = this

            const dialog = new frappe.ui.Dialog({
                title: __("Select Batch"),
                size: "large",
                fields: [
                    {
                        fieldname: "trans_blok",
                        fieldtype: "Table",
                        label: "Items",
                        in_place_edit: false,
                        reqd: 1,
                        fields: [
                            {
                                fieldtype: "Link",
                                fieldname: "item",
                                options: "Batch",
                                in_list_view: 1,
                                disabled: 0,
                                label: __("Batch")
                            },
                        ],
                    }
                ],
                primary_action: function (data) {
                    const selected_items = data.trans_blok
                    if (selected_items.length < 1) {
                        frappe.throw("Please Select at least One Blok")
                    }

                    frappe.call({
                        method: "sth.controllers.rencana_kerja_controller.duplicate_rencana_kerja",
                        args: {
                            voucher_type: me.frm.doc.doctype,
                            voucher_no: me.frm.doc.name,
                            blok: selected_items,
                            is_batch: 1
                        },
                    })
                    dialog.hide();
                },
                primary_action_label: __("Submit"),
            });

            dialog.show();
        }
    }
    calculate_amount_addons() {
        let doc = this.frm.doc

        doc.jumlah_tenaga_kerja = doc.qty_basis ? flt(doc.qty / doc.qty_basis) : 0
        doc.tenaga_kerja_amount = flt(doc.jumlah_tenaga_kerja * doc.upah_per_basis) + flt(doc.premi)
    }
}

cur_frm.script_manager.make(sth.plantation.RencanaKerjaBulananPerawatan);