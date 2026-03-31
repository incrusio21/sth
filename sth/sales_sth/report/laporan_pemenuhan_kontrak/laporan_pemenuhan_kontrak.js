// Copyright (c) 2024, [Your Company] and contributors
// For license information, please see license.txt

frappe.query_reports["Laporan Pemenuhan Kontrak"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
        },
        {
            "fieldname": "unit",
            "label": __("Unit"),
            "fieldtype": "Link",
            "options": "Unit",
        },
        {
            "fieldname": "komoditi",
            "label": __("Komoditi"),
            "fieldtype": "Link",
            "options": "Komoditi",
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 0
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 0
        },
        // {
        //     "fieldname": "from_date",
        //     "label": __("From Date"),
        //     "fieldtype": "Date",
        //     "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        //     "reqd": 0
        // },
        // {
        //     "fieldname": "to_date",
        //     "label": __("To Date"),
        //     "fieldtype": "Date",
        //     "default": frappe.datetime.get_today(),
        //     "reqd": 0
        // },
        // {
        //     "fieldname": "sales_order",
        //     "label": __("Sales Order"),
        //     "fieldtype": "Link",
        //     "options": "Sales Order",
        //     "get_query": function() {
        //         return {
        //             "filters": {
        //                 "docstatus": 1
        //             }
        //         }
        //     }
        // },
        // {
        //     "fieldname": "customer",
        //     "label": __("Customer"),
        //     "fieldtype": "Link",
        //     "options": "Customer"
        // },
        // {
        //     "fieldname": "item_code",
        //     "label": __("Item Code"),
        //     "fieldtype": "Link",
        //     "options": "Item"
        // },
        // {
        //     "fieldname": "company",
        //     "label": __("Company"),
        //     "fieldtype": "Link",
        //     "options": "Company",
        //     "default": frappe.defaults.get_user_default("Company")
        // }
    ],
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname == "no_kontrak" && data) {
            value = `
            <a class="show-kontrak" href="/app/query-report/Laporan%20Histori%20Pemenuhan%20Kontrak?no_kontrak=${data.no_kontrak_alias}" target="_blank">
                ${data.no_kontrak}
            </a>`;
        }

        return value;
    },
    // after_datatable_render: function (datatable) {
    //     $(".show-kontrak").on("click", function () {
    //         const kontrak = $(this).data("kontrak");
    //         console.log(kontrak);

    //         let dialog = new frappe.ui.Dialog({
    //             title: "Histori Pemenuhan Kontrak",
    //             size: "extra-large",
    //             fields: [
    //                 {
    //                     fieldtype: "HTML",
    //                     fieldname: "table_html"
    //                 }
    //             ]
    //         });

    //         dialog.fields_dict.table_html.$wrapper.html(`
    //                 <table class="table table-bordered">
    //                     <thead>
    //                         <tr>
    //                             <th rowspan="2">No</th>
    //                             <th rowspan="2">Kode PT</th>
    //                             <th rowspan="2">No Transaksi</th>
    //                             <th rowspan="2">Tanggal</th>
    //                             <th rowspan="2">No.Kontrak</th>
    //                             <th rowspan="2">No. SIPB</th>
    //                             <th rowspan="2">No. DO</th>
    //                             <th rowspan="2">Kendaraan</th>
    //                             <th rowspan="2">Nama Sopir</th>
    //                             <th rowspan="2">Berat Bersih Pabrik</th>
    //                             <th rowspan="2">Berat Bersih Pembeli</th>
    //                             <th colspan="3">Kontrak</th>
    //                             <th colspan="3">Transportir</th>
    //                             <th rowspan="2">No. Invoice</th>
    //                         </tr>
    //                         <tr>
    //                             <th>Nama Customer</th>
    //                             <th>Harga Satuan</th>
    //                             <th>Nilai per Truk</th>
    //                             <th>Nama</th>
    //                             <th>Harga Satuan</th>
    //                             <th>Nilai per Truk</th>
    //                         </tr>
    //                     </thead>
    //                     <tbody>
    //                     </tbody>
    //                 </table>
    //             `);

    //         dialog.show();
    //         dialog.$wrapper.find('.modal-dialog').css({
    //             "max-width": "95%",
    //             "width": "95%"
    //         });
    //     });
    // }
};