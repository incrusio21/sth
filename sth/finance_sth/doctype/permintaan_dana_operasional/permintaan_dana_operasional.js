// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
const pdoCategories = ["Bahan Bakar", "Perjalanan Dinas", "Kas", "Dana Cadangan", "NON PDO"]


frappe.ui.form.on("Permintaan Dana Operasional", {
    setup(frm){
        frm.ignore_doctypes_on_cancel_all = ["PDO Bahan Bakar Vtwo", "PDO Perjalanan Dinas Vtwo", "PDO Kas Vtwo", "PDO Dana Cadangan Vtwo", "PDO NON PDO Vtwo"];
    },
	refresh(frm) {
        filterCreditTo(frm)
        processFilterSubDetail(frm)
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
});

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
            filters : {
                custom_routine_type: "Rutin",
                custom_pdo_type: locals[cdt][cdn].sub_detail
            }
        }
    }
}