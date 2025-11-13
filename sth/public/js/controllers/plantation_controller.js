// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

frappe.provide("sth.plantation");

sth.plantation.TransactionController = class TransactionController extends sth.plantation.AccountsController {
    setup(doc) {
        let doctype = doc.doctype
        this.fieldname_total = ["amount"]
        this.skip_table_amount = []
        this.skip_fieldname_amount = ["outstanding_amount"]
        this.kegiatan_fetch_fieldname = []
        this.max_qty_fieldname = {}
        
        // check daftar fieldname dengan total didalamny untuk d gabungkan ke grand_total
        if (!sth.plantation.doctype_ref[doctype]) {
            sth.plantation.setup_doctype_ref(doctype)
        }
    }

    refresh() {
        this.set_query_field()
    }

    company(doc) {
        this.fetch_data_kegiatan(doc.kegiatan, doc.company)
    }

    kegiatan(doc) {
        this.fetch_data_kegiatan(doc.kegiatan, doc.company)
    }

    item(doc, cdt, cdn) {
        let data = frappe.get_doc(cdt, cdn)
        let doctype = this.frm.fields_dict[data.parentfield].grid.fields_map.item.options;

        frappe.call({
            method: "sth.plantation.utils.get_details_item",
            args: {
                item: data.item,
                doctype: doctype,
                company: doc.company
            },
            freeze: true,
            callback: function (data) {
                frappe.model.set_value(cdt, cdn, data.message)
            }
        })
    }

    qty(_, cdt, cdn) {
        this.calculate_total(cdt, cdn)
    }

    rate(_, cdt, cdn) {
        this.calculate_total(cdt, cdn)
    }

    // mempersingkat structur koding
    doctype_ref(dict) {
        return sth.plantation.doctype_ref[this.frm.doc.doctype][dict]
    }

    set_query_field() {
        this.frm.set_query("unit", function (doc) {
            if (!doc.company) {
                frappe.throw("Please Select Company First")
            }

            return {
                filters: {
                    company: doc.company
                }
            }
        })

        this.frm.set_query("divisi", function (doc) {
            if (!doc.unit) {
                frappe.throw("Please Select Unit/Kebun First")
            }

            return {
                filters: {
                    unit: doc.unit
                }
            }
        })
    }

    calculate_total(cdt, cdn, parentfield = null) {
        if (!parentfield) {
            parentfield = frappe.get_doc(cdt, cdn).parentfield
        }

        if (parentfield) {
            this.calculate_item_values(parentfield);
        } else {
            this.calculate_non_table_values();
        }
        this.calculate_grand_total();

        this.frm.refresh_fields();
    }

    calculate_item_values(table_name) {
        let me = this
        const total = {};
        for (const f of this.fieldname_total) {
            total[f] = 0;
        }

        let data_table = me.frm.doc[table_name] || []
        let max_qty = this.max_qty_fieldname[table_name] || undefined

        // menghitung amount, rotasi, qty
        for (const item of data_table) {
            // rate * qty * (rotasi jika ada)
            this.update_rate_or_qty_value(item)
            
            let qty = max_qty && flt(item.qty) > this.frm.doc[max_qty] ? this.frm.doc[max_qty] : item.qty  
            item.amount = flt(item.rate * qty, precision("amount", item));

            this.update_value_after_amount(item)

            // total amount dan qty untuk d input ke doctype utama jika d butuhkan
            for (const f of this.fieldname_total) {
                total[f] += item[f]
            }
        }

        for (const total_field of this.fieldname_total) {
            let fieldname = `${table_name}_${total_field}`
            if (!this.frm.fields_dict[fieldname]) continue;

            this.frm.doc[fieldname] = total[total_field];
        }

        this.after_calculate_item_values(table_name, total)
    }

    update_rate_or_qty_value() {
        // set on child class if needed
    }

    update_value_after_amount() {
        // set on child class if needed
    }


    calculate_non_table_values() {
        // set on child class if needed
    }

    after_calculate_item_values(table_name) {
        // set on child class if needed
    }

    calculate_grand_total() {
        let grand_total = 0.0

        this.before_calculate_grand_total()

        for (const field of this.doctype_ref("amount")) {
            if (in_list(this.skip_table_amount, field.replace("_amount", "")) ||
                in_list(this.skip_fieldname_amount, field)) continue;
            
            grand_total += this.frm.doc[field] || 0;
        }

        this.frm.doc.grand_total = grand_total

        this.after_calculate_grand_total()
    }

    before_calculate_grand_total() {
        // set on child class if needed
    }

    after_calculate_grand_total() {
        // set on child class if needed
    }

    get_blok_list(opts, callback) {
        const fields = [
            {
                fieldtype: "Link",
                fieldname: "item",
                options: "Blok",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Blok")
            },
            {
                fieldtype: "Int",
                fieldname: "tahun_tanam",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Tahun Tanam"),
                columns: 1
            },
            {
                fieldtype: "Int",
                fieldname: "luas_areal",
                in_list_view: 1,
                read_only: 1,
                disabled: 0,
                label: __("Luas Areal")
            },
            {
                fieldtype: "Int",
                fieldname: "sph",
                in_list_view: 1,
                read_only: 1,
                label: __("SPH"),
                columns: 1
            },
            {
                fieldtype: "Int",
                fieldname: "jumlah_pokok",
                in_list_view: 1,
                read_only: 1,
                label: __("Jumlah Pokok")
            },
        ]


        if ($.isArray(opts.fields)) {
            opts.fields.forEach((field, index) => {
                fields.push(field);
            });
        }

        frappe.call({
            method: opts.method || "sth.plantation.utils.get_blok",
            args: {
                args: opts.args
            },
            freeze: true,
            callback: function (data) {
                if (data.message.length == 0) {
                    frappe.throw(__("Blok Not Found."))
                }

                const dialog = new frappe.ui.Dialog({
                    title: __("Select Blok"),
                    size: "large",
                    fields: [
                        {
                            fieldname: "trans_blok",
                            fieldtype: "Table",
                            label: "Items",
                            cannot_add_rows: 1,
                            cannot_delete_rows: 1,
                            in_place_edit: false,
                            reqd: 1,
                            get_data: () => {
                                return data.message;
                            },
                            fields: fields,
                        }
                    ],
                    primary_action: function () {
                        const selected_items = dialog.fields_dict.trans_blok.grid.get_selected_children();
                        if (selected_items.length < 1) {
                            frappe.throw("Please Select at least One Blok")
                        }

                        callback && callback(selected_items)
                        dialog.hide();
                    },
                    primary_action_label: __("Submit"),
                });

                dialog.show();
            }
        })
    }

    fetch_data_kegiatan(kegiatan, company) {
        console.log("tes")
        let me = this
        if (!me.kegiatan_fetch_fieldname) return

        if (!(kegiatan && company)) {
            me.frm.set_value(Object.fromEntries(me.kegiatan_fetch_fieldname.map(key => [key, ""])))
        } else {
            frappe.call({
                method: "sth.controllers.queries.kegiatan_fetch_data",
                args: {
                    kegiatan: kegiatan,
                    company: company,
                    fieldname: me.kegiatan_fetch_fieldname
                },
                callback: (data) => {
                    me.frm.set_value(data.message)
                }
            })
        }
    }

    clear_table(list_table = []) {
        for (const field_table of list_table || []) {
            this.frm.clear_table(field_table)
            this.calculate_item_values(field_table)
        }

        this.calculate_grand_total();
        this.frm.refresh_fields();
    }
}


// menyimpan fieldname yang di butuhkan (fieltype Table)
sth.plantation.doctype_ref = {}
sth.plantation.setup_doctype_ref = function (doctype) {
    let fields = frappe.get_doc("DocType", doctype).fields;
    sth.plantation.doctype_ref[doctype] = {
        "amount": [],
        "table_fieldname": []
    };

    fields.forEach(d => {
        if (d.fieldtype === "Currency" && in_list(d.fieldname, "amount")) {
            sth.plantation.doctype_ref[doctype].amount.push(d.fieldname);
        }

        if (d.fieldtype === "Table") {
            sth.plantation.doctype_ref[doctype].table_fieldname.push(d.fieldname);
        }
    });
}