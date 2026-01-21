frappe.listview_settings["Permintaan Pengeluaran Barang"] = {
    get_indicator: function (doc) {
        const status_colors = {
            "Sebagian di Keluarkan": "yellow",
            "Barang Telah Dikeluarkan": "green",
            "Submitted": "blue",
            "Closed": "gray"
        };

        return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
    },
}