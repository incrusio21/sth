// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
const pdoCategories = ["Bahan Bakar", "Perjalanan Dinas", "Kas", "Dana Cadangan", "NON PDO"]


frappe.ui.form.on("Permintaan Dana Operasional", {
	setup(frm){
		frm.ignore_doctypes_on_cancel_all = ["PDO Bahan Bakar Vtwo", "PDO Perjalanan Dinas Vtwo", "PDO Kas Vtwo", "PDO Dana Cadangan Vtwo", "PDO NON PDO Vtwo"];
	},
	refresh(frm) {
		filterDebitTo(frm)
		filterCreditTo(frm)
		processFilterSubDetail(frm)
		filterFundType(frm)
		frm.fields_dict['pdo_dana_cadangan'].grid.refresh();
		make_payment_voucher(frm)
		make_realisasi_pdo(frm)
	},
});

frappe.ui.form.on("PDO Bahan Bakar Table", {
	pdo_bahan_bakar_remove(frm){
		calculateGrandTotal(frm)
	},
	plafon(frm, cdt, cdn) {
		processBahanBakar(frm, cdt, cdn);
	},
	unit_price(frm, cdt, cdn) {
		processBahanBakar(frm, cdt, cdn);
	},
	revised_plafon(frm, cdt, cdn) {
		processBahanBakar(frm, cdt, cdn);
	},
	revised_unit_price(frm, cdt, cdn) {
		processBahanBakar(frm, cdt, cdn);
	},
	designation(frm, cdt, cdn){
		get_plafon_pdo_bb(frm, cdt, cdn)
	}
});

frappe.ui.form.on("PDO Perjalanan Dinas Table", {
	pdo_perjalanan_dinas_remove(frm){
		calculateGrandTotal(frm)
	},
	plafon(frm, cdt, cdn) {
		processPerjalananDinas(frm, cdt, cdn);
	},
	hari_dinas(frm, cdt, cdn) {
		processPerjalananDinas(frm, cdt, cdn);
	},
	revised_plafon(frm, cdt, cdn) {
		processPerjalananDinas(frm, cdt, cdn);
	},
	revised_duty_day(frm, cdt, cdn) {
		processPerjalananDinas(frm, cdt, cdn);
	},
	type(frm, cdt, cdn){
		const curRow = locals[cdt][cdn]
		getExpenseAccount(frm, curRow, cdt, cdn)
		get_plafon_pdo(frm, cdt, cdn)
	}
});


frappe.ui.form.on("PDO Kas Table", {
	pdo_kas_remove(frm){
		calculateGrandTotal(frm)
	},
	qty(frm, cdt, cdn) {
		processKas(frm, cdt, cdn);
	},
	price(frm, cdt, cdn) {
		processKas(frm, cdt, cdn);
	},
	revised_qty(frm, cdt, cdn) {
		processKas(frm, cdt, cdn);
	},
	revised_price(frm, cdt, cdn) {
		processKas(frm, cdt, cdn);
	},
	type(frm, cdt, cdn){
		const curRow = locals[cdt][cdn]
		getExpenseAccount(frm, curRow, cdt, cdn)
	}
});

frappe.ui.form.on("PDO NON PDO Table", {
	pdo_non_pdo_remove(frm){
		calculateGrandTotal(frm)
	},
	qty(frm, cdt, cdn) {
		processNonPdo(frm, cdt, cdn);
	},
	price(frm, cdt, cdn) {
		processNonPdo(frm, cdt, cdn);
	},
	revised_qty(frm, cdt, cdn) {
		processNonPdo(frm, cdt, cdn);
	},
	revised_price(frm, cdt, cdn) {
		processNonPdo(frm, cdt, cdn);
	},
	type(frm, cdt, cdn){
		const curRow = locals[cdt][cdn]
		getExpenseAccount(frm, curRow, cdt, cdn)
	}
});

frappe.ui.form.on("PDO Dana Cadangan Table", {
	pdo_dana_cadangan_remove(frm){
		calculateGrandTotal(frm)
	},
	amount(frm) {
		calculateGrandTotal(frm)
	},
	revised_amount(frm) {
		calculateGrandTotal(frm)
	},
	jenis: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		set_field_properties(frm, cdt, cdn, row.jenis);
	},
	
	pdo_dana_cadangan_add: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		set_field_properties(frm, cdt, cdn, row.jenis);
	}
});

function get_plafon_pdo(frm, cdt, cdn){
	let row = locals[cdt][cdn];
        
    if (row.type) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Plafon PDO',
                filters: {
                    'name': 'PERJALANAN DINAS'
                },
                fields: ['name']
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    frappe.call({
                        method: 'frappe.client.get',
                        args: {
                            doctype: 'Plafon PDO',
                            name: r.message[0].name
                        },
                        callback: function(response) {
                            if (response.message) {
                                let plafon_pdo = response.message;
                                
                                let incentif_row = plafon_pdo.plafon_pdo_table.find(
                                    item => item.jenis_plafon == row.type
                                );
                                
                                if (incentif_row && incentif_row.nilai) {

                                    frappe.model.set_value(cdt, cdn, 'plafon', incentif_row.nilai);
                                    frappe.model.set_value(cdt, cdn, 'revised_plafon', incentif_row.nilai);
                                    
                                    frm.refresh_field('pdo_perjalanan_dinas');
                                } else {
                                    frappe.msgprint(__('INCENTIF not found in Plafon PDO'));
                                }
                            }
                        }
                    });
                } else {
                    frappe.msgprint(__('Plafon PDO "PERJALANAN DINAS" not found'));
                }
            }
        });
    }
}

function get_plafon_pdo_bb(frm, cdt, cdn){
	let row = locals[cdt][cdn];
	if (row.designation) {
		console.log(row.designation)
		fetch_plafon_value('UANG PEMBANTU', row.designation, 'jenis_plafon', cdt, cdn, frm, 'pdo_bahan_bakar'); 
	}       
}

function fetch_plafon_value(plafon_name, filter_value, filter_field, cdt, cdn, frm, table_fieldname) {
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Plafon PDO',
            name: plafon_name
        },
        callback: function(response) {
            if (response.message) {
                let plafon_pdo = response.message;

                let matching_row = plafon_pdo.plafon_pdo_table.find(
                    item => item[filter_field] === filter_value
                );

                console.log(plafon_pdo)
                
                if (matching_row && matching_row.nilai) {
                    frappe.model.set_value(cdt, cdn, 'plafon', matching_row.nilai);
                    if (table_fieldname === 'pdo_bahan_bakar') {
                        frappe.model.set_value(cdt, cdn, 'revised_plafon', matching_row.nilai);
                    } else {
                        frappe.model.set_value(cdt, cdn, 'revised_plafon', matching_row.nilai);
                    }
                    frm.refresh_field(table_fieldname);
                } else {

                }
            } else {

            }
        }
    });
}

function filterCreditTo(frm) {
	for (const pdo of pdoCategories) {
		const fieldname = pdo.toLocaleLowerCase().replaceAll(" ", "_")
		frm.set_query(`${fieldname}_credit_to`, () => {
			return {
				filters: {
					"account_type": "Payable",
					"company": frm.doc.company
				}
			}
		})
	}
}

function filterDebitTo(frm) {
	for (const pdo of pdoCategories) {
		const fieldname = pdo.toLocaleLowerCase().replaceAll(" ", "_")
		frm.set_query(`${fieldname}_debit_to`, () => {
			return {
				filters: {
					"company": frm.doc.company
				}
			}
		})
	}
}

function calculateRowTotal(frm, curRow, cdt, cdn, config) {
	const {
		base1,
		base2,
		target,
		revised1,
		revised2,
		revisedTarget,
		childtable
	} = config;

	// ---- Hitung Total ----
	if (base1 && curRow[base1] !== undefined && curRow[base1]) {

		if (base2 && curRow[base2] !== undefined && curRow[base2]) {
			frappe.model.set_value(cdt, cdn, target, curRow[base1] * curRow[base2]);
		} else {
			frappe.model.set_value(cdt, cdn, target, curRow[base1]);
		}
	}

	// ---- Hitung Revised Total ----
	if (revised1 && curRow[revised1] !== undefined && curRow[revised1]) {

		if (revised2 && curRow[revised2] !== undefined && curRow[revised2]) {
			frappe.model.set_value(cdt, cdn, revisedTarget, curRow[revised1] * curRow[revised2]);
		} else {
			frappe.model.set_value(cdt, cdn, revisedTarget, curRow[revised1]);
		}
	}

	frm.refresh_field(childtable);
	calculateGrandTotal(frm);
}

function processBahanBakar(frm, cdt, cdn) {
	const curRow = locals[cdt][cdn];
	calculateRowTotal(frm, curRow, cdt, cdn, {
		base1: "plafon",
		base2: "unit_price",
		target: "price_total",
		revised1: "revised_plafon",
		revised2: "revised_unit_price",
		revisedTarget: "revised_price_total",
		childtable: "pdo_bahan_bakar"
	});
}

function processPerjalananDinas(frm, cdt, cdn) {
	const curRow = locals[cdt][cdn];
	calculateRowTotal(frm, curRow, cdt, cdn, {
		base1: "plafon",
		base2: "hari_dinas",
		target: "total",
		revised1: "revised_plafon",
		revised2: "revised_duty_day",
		revisedTarget: "revised_total",
		childtable: "pdo_perjalanan_dinas"
	});
}

function processKas(frm, cdt, cdn) {
	const curRow = locals[cdt][cdn];
	calculateRowTotal(frm, curRow, cdt, cdn, {
		base1: "qty",
		base2: "price",
		target: "total",
		revised1: "revised_qty",
		revised2: "revised_price",
		revisedTarget: "revised_total",
		childtable: "pdo_kas"
	});
}

function processNonPdo(frm, cdt, cdn) {
	const curRow = locals[cdt][cdn];
	calculateRowTotal(frm, curRow, cdt, cdn, {
		base1: "qty",
		base2: "price",
		target: "total",
		revised1: "revised_qty",
		revised2: "revised_price",
		revisedTarget: "revised_total",
		childtable: "pdo_kas"
	});
}

function calculateGrandTotal(frm) {
	const totalFieldname = {
		"Bahan Bakar": "price_total",
		"Perjalanan Dinas": "total",
		"Kas": "total",
		"Dana Cadangan": "amount",
		"NON PDO": "total",
	}
	for (const pdo of pdoCategories) {
		const fieldname = pdo.toLocaleLowerCase().replaceAll(" ", "_");
		
		const childs = frm.doc[`pdo_${fieldname}`];
		let revisedTotal = 0
		const totalField = totalFieldname[pdo]
		
		if (frm.doc[`pdo_${fieldname}`]) {
			for (const row of childs) {
				revisedTotal += row[`revised_${totalField}`]
			}
		}
		frappe.run_serially([
			() => frm.set_value(`grand_total_${fieldname}`, revisedTotal),
			() => frm.set_value(`outstanding_amount_${fieldname}`, revisedTotal),
		])
	}
}

function processFilterSubDetail(frm) {
	const filtered = pdoCategories.filter(cat => 
		cat !== "Bahan Bakar" && cat !== "Dana Cadangan"
	);

	for (const category of filtered) {
		let childTable = category.toLocaleLowerCase().replace(" ", "_");
		childTable = `pdo_${childTable}`
		
		filterSubDetail(frm, childTable, category);
		filterType(frm, childTable);
	}
}

function filterSubDetail(frm, childTable, category) { 
	frm.fields_dict[childTable].grid.get_field('sub_detail').get_query = function (doc, cdt, cdn) {
		return {
			query: 'sth.finance_sth.doctype.pdo_type.pdo_type.filter_link_pdo_type',
			filters : {
				category: category
			}
		}
	}
}

function filterType(frm, childTable) { 
	frm.fields_dict[childTable].grid.get_field('type').get_query = function (doc, cdt, cdn) {
		return {
			query: 'sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.filter_type',
			filters : {
				routine_type: locals[cdt][cdn].routine_type,
				company: frm.doc.company
			}
		}
	}
}

function getExpenseAccount(frm, curRow, cdt, cdn) {
	frappe.call('sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.get_expense_account', {
		company: frm.doc.company,
		parent: curRow.type
	}).then(r => {
		const default_account = r.message
		frappe.model.set_value(cdt, cdn, 'debit_to', default_account)
	})

	frm.refresh_field(curRow.parentfield)
}

function filterFundType(frm) {
	frm.fields_dict.pdo_dana_cadangan.grid.get_field('fund_type').get_query = function (doc, cdt, cdn) {
		return {
			query: 'sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.filter_fund_type',
			filters: {
				company: frm.doc.company
			}
		}
	}
}

function set_field_properties(frm, cdt, cdn, jenis) {
	let grid_row = frm.fields_dict['pdo_dana_cadangan'].grid.grid_rows_by_docname[cdn];
	
	if (!grid_row) return;
	
	if (jenis == 'Kas' || jenis == 'Bank') {
		grid_row.toggle_editable('amount', true);
		grid_row.toggle_editable('revised_amount', true);
		grid_row.toggle_editable('cash_bank_balance_adjustment', false);
		
		frappe.model.set_df_property(cdt, 'amount', 'read_only', 0, cdn);
		frappe.model.set_df_property(cdt, 'revised_amount', 'read_only', 0, cdn);
		frappe.model.set_df_property(cdt, 'cash_bank_balance_adjustment', 'read_only', 1, cdn);
		
	} else if (jenis === 'Saldo') {
		grid_row.toggle_editable('amount', false);
		grid_row.toggle_editable('revised_amount', false);
		grid_row.toggle_editable('cash_bank_balance_adjustment', true);
		
		frappe.model.set_df_property(cdt, 'amount', 'read_only', 1, cdn);
		frappe.model.set_df_property(cdt, 'revised_amount', 'read_only', 1, cdn);
		frappe.model.set_df_property(cdt, 'cash_bank_balance_adjustment', 'read_only', 0, cdn);
	}
	
	grid_row.refresh();
}

function make_payment_voucher(frm){
	if (frm.doc.docstatus == 1 && !frm.doc.payment_voucher) {
		frm.add_custom_button(__('Create Payment Voucher'), function() {
			frappe.model.open_mapped_doc({
				method: 'sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.create_payment_voucher',
				frm: frm
			});
		});
	}	
}

function make_realisasi_pdo(frm){
	if (frm.doc.docstatus == 1 && frm.doc.payment_voucher) {
	 	frm.add_custom_button(__('Realisasi PDO'), function() {
            show_realisasi_dialog(frm);
        });    
	}	
}

function show_realisasi_dialog(frm) {
    // Get available types first
    frappe.call({
        method: 'sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.get_available_tipe_pdo',
        args: {
            source_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__('All types have been fully paid'));
                return;
            }
            
            // Build options string for select field
            let options = [''];
            let option_labels = {};
            
            r.message.forEach(function(item) {
                options.push(item.value);
                option_labels[item.value] = item.label;
            });
            
            let dialog = new frappe.ui.Dialog({
                title: __('Realisasi PDO'),
                fields: [
                    {
                        fieldname: 'tipe_pdo',
                        label: __('Pilih Tipe PDO'),
                        fieldtype: 'Select',
                        options: options.join('\n'),
                        reqd: 1,
                        description: __('Only types with outstanding amounts are shown')
                    }
                ],
                primary_action_label: __('Create Payment Voucher Kas'),
                primary_action: function(values) {
                    if (!values.tipe_pdo) {
                        frappe.msgprint(__('Please select a type'));
                        return;
                    }
                    
                    dialog.hide();
                    
                    // Call the method with tipe_pdo parameter
                    frappe.call({
                        method: 'sth.finance_sth.doctype.permintaan_dana_operasional.permintaan_dana_operasional.create_payment_voucher_kas',
                        args: {
                            source_name: frm.doc.name,
                            tipe_pdo: values.tipe_pdo
                        },
                        callback: function(r) {
                            if (r.message) {
                                // Open the created document
                                frappe.model.sync(r.message);
                                frappe.set_route('Form', r.message.doctype, r.message.name);
                            }
                        }
                    });
                }
            });
            
            dialog.show();
        }
    });
}