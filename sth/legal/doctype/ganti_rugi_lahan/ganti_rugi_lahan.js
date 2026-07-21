// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.provide("sth.legal");

frappe.ui.form.on("Ganti Rugi Lahan", {
	refresh(frm) {
        frm.events.set_no_rekening(frm);
        frm.events.calculate_payment_schedule_total(frm);
        frm.events.make_payment_entry_button(frm);
	},

    make_payment_entry_button(frm) {
        if (frm.doc.docstatus !== 1) return;

        frm.add_custom_button(__("Payment"), () => {
            frappe.model.open_mapped_doc({
                method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.make_payment_entry",
                frm: frm,
            });
        }, __("Create"));
    },
    company(frm) {
        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.fetch_company_account",
            args: {
                company: frm.doc.company,
                childrens: frm.doc.items.length > 0 ? frm.doc.items : null,
            }
        })
    },

    pembayaran_lahan(frm){
        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.get_details_sppt",
            args: {
                pembayaran_lahan: frm.doc.pembayaran_lahan,
                childrens: frm.doc.items.length > 0 ? frm.doc.items : null,
            }
        })
    },

    calculate_payment_schedule_total(frm) {
        let total_invoice_portion = 0
        let total_payment_amount = 0

        for (const d of frm.doc.payment_schedule || []) {
            total_invoice_portion += flt(d.invoice_portion)
            total_payment_amount += flt(d.payment_amount)
        }

        frm.doc.total_invoice_portion = flt(total_invoice_portion)
        frm.doc.total_payment_amount = flt(total_payment_amount)
        frm.refresh_field("total_invoice_portion")
        frm.refresh_field("total_payment_amount")
    },

    set_no_rekening(frm) {

        if (!frm.doc.items || frm.doc.items.length === 0) {
            frm.set_value("no_rekening", "")
            return
        }

        let row = frm.doc.items[0]

        if (!row.sppt) {
            frm.set_value("no_rekening", "")
            return
        }

        frappe.db.get_value("GIS", row.sppt, "pemilik_lahan")
            .then(r => {

                if (!r.message || !r.message.pemilik_lahan) return

                return frappe.db.get_value(
                    "Daftar Masyarakat",
                    r.message.pemilik_lahan,
                    "norek"
                )
            })
            .then(r => {
                if (r && r.message && r.message.norek) {
                    frm.set_value("no_rekening", r.message.norek)
                }
            })
    },
});

frappe.ui.form.on("Ganti Rugi Lahan Item", {
    jenis_biaya(frm, cdt, cdn){
        let data = frappe.get_doc(cdt, cdn)

        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.get_details_jenis_biaya",
            args: {
                company: frm.doc.company,
                childrens: [data],
                sppt_update: 1 
            }
        })
    },
    sppt(frm, cdt, cdn){
        let data = frappe.get_doc(cdt, cdn)

        if(!data.sppt) return;

        frm.cscript.get_details_account({
            method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.get_details_sppt",
            args: {
                pembayaran_lahan: frm.doc.pembayaran_lahan,
                childrens: [data],
            }
        })

        frm.events.set_no_rekening(frm)
    }
});

frappe.ui.form.on("Proposal Schedule", {
    invoice_portion(frm, cdt, cdn) {
        let row = locals[cdt][cdn]

        let total_portion = 0
        for (const d of frm.doc.payment_schedule) {
            total_portion += flt(d.invoice_portion)
        }

        if (total_portion > 100) {
            frappe.msgprint(__("Total Invoice Portion tidak boleh lebih dari 100%"))
            frappe.model.set_value(cdt, cdn, "invoice_portion", 0)
            return
        }

        if (row.invoice_portion) {
            frappe.model.set_value(cdt, cdn, "payment_amount", flt(row.invoice_portion) * flt(frm.doc.grand_total) / 100)
        }

        frm.events.calculate_payment_schedule_total(frm)
    },
    payment_amount(frm) {
        frm.events.calculate_payment_schedule_total(frm)
    },
    payment_schedule_remove(frm) {
        frm.events.calculate_payment_schedule_total(frm)
    },
    ajukan(frm, cdt, cdn) {
        let row = locals[cdt][cdn]

        let first_not_diajukan = (frm.doc.payment_schedule || [])
            .slice()
            .sort((a, b) => a.idx - b.idx)
            .find((d) => !d.diajukan)

        if (first_not_diajukan && first_not_diajukan.name !== row.name) {
            frappe.msgprint(__("Termin harus diajukan secara berurutan, mulai dari baris pertama yang belum diajukan."))
            return
        }

        frappe.confirm(
            __("Ajukan termin ini agar bisa dibuatkan Payment Entry?"),
            () => {
                frappe.call({
                    method: "sth.legal.doctype.ganti_rugi_lahan.ganti_rugi_lahan.ajukan_termin",
                    args: { name: row.name },
                    freeze: true,
                    freeze_message: __("Mengajukan..."),
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.model.set_value(cdt, cdn, "diajukan", 1)
                            frappe.show_alert({ message: __("Termin berhasil diajukan."), indicator: "green" })
                        }
                    }
                })
            }
        )
    }
});

sth.legal.GantiRugiLahan = class GantiRugiLahan extends sth.plantation.AccountsController {
    setup() {
        let me = this

        for (const fieldname of ["qty", "rate", "biaya_surat"]) {
            frappe.ui.form.on('Ganti Rugi Lahan Item', fieldname, function (doc, cdt, cdn) {
                me.calculate_total(cdt, cdn)
            });
        }
    }
    
    refresh() {
        this.set_query_field()
        this.set_dynamic_labels()
    }

    set_query_field() {
        this.frm.set_query("unit", function (doc) {
			return {
				filters: {
					company: ["=", doc.company]
				}
			};
		});

		this.frm.set_query("sppt", "items", function (doc, cdt, cdn) {
            let item = locals[cdt][cdn]

			return {
				filters: {
					perangkat_desa: ["=", item.perangkat_desa]
				}
			};
		});

        this.frm.set_query("pemilik_lahan", "items", function (doc, cdt, cdn) {
            let item = locals[cdt][cdn]

			return {
				filters: {
					pd: ["=", item.perangkat_desa]
				}
			};
		});
    }

    get_details_account(opts){
        let me = this

        frappe.call({
            method: opts.method,
            args: opts.args,
            callback: function(r) {
                if(!r.exc && r.message) {
                    for (const [key, value] of Object.entries(r.message)) {
                        if(key == "childrens"){
                            me._set_values_for_item_list(r.message.childrens, false)
                        }else{
                            me.frm.doc[key] = value
                        }
                    }

                    me.calculate_total()
                }
            }
        });
    }

    _set_values_for_item_list(children, recalculate=true) {
		for (const child of children) {
			let data = frappe.get_doc(child.doctype, child.name)

			for (const [key, value] of Object.entries(child)) {
				data[key] = value 
			}
		}

        if(recalculate) this.calculate_total();
	}

    calculate_total(){
        let doc = this.frm.doc

        let grand_total = 0

        for (const child of doc.items) {
            child.amount = flt(child.qty) * flt(child.rate) + flt(child.biaya_surat)
			grand_total += child.amount
		}

        doc.grand_total = flt(grand_total)

        this.frm.refresh_fields()
    }

    payment_term(doc, cdt, cdn) {
		const me = this;
		var row = locals[cdt][cdn];
		if(row.payment_term) {
			frappe.call({
				method: "erpnext.controllers.accounts_controller.get_payment_term_details",
				args: {
					term: row.payment_term,
					posting_date: this.frm.doc.posting_date,
					grand_total: this.frm.doc.grand_total
				},
				callback: function(r) {
					if(r.message && !r.exc) {
						for (var d in r.message) {
							frappe.model.set_value(cdt, cdn, d, r.message[d]);
                            const company_currency = me.get_company_currency();
							me.update_payment_schedule_grid_labels(company_currency);
						}
					}
				}
			})
		}
	}

    update_payment_schedule_grid_labels(company_currency) {
		const me = this;
		if (this.frm.doc.payment_schedule && this.frm.doc.payment_schedule.length > 0) {
			this.frm.set_currency_labels(["base_payment_amount", "base_outstanding", "base_paid_amount"],
				company_currency, "payment_schedule");
			this.frm.set_currency_labels(["payment_amount", "outstanding", "paid_amount"],
				this.frm.doc.currency, "payment_schedule");

			var schedule_grid = this.frm.fields_dict["payment_schedule"].grid;
			$.each(["base_payment_amount", "base_outstanding", "base_paid_amount"], function(i, fname) {
				if (frappe.meta.get_docfield(schedule_grid.doctype, fname))
					schedule_grid.set_column_disp(fname, me.frm.doc.currency != company_currency);
			});
		}
	}

}

cur_frm.script_manager.make(sth.legal.GantiRugiLahan);
