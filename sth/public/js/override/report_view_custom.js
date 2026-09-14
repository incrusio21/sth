frappe.listview_settings['Timbangan'] = frappe.listview_settings['Timbangan'] || {};

frappe.listview_settings['Timbangan'].onload = function (listview) {
  if (listview.doctype !== 'Timbangan') return;

  const original_get_columns_totals = listview.get_columns_totals.bind(listview);

  listview.get_columns_totals = function (data) {
    const totals = original_get_columns_totals(data);

    const values = data
      .map(r => parseFloat(r.potongan_sortasi))
      .filter(v => !isNaN(v));

    if (values.length) {
      totals['potongan_sortasi'] = values.reduce((a, b) => a + b, 0) / values.length;
    }

    return totals;
  };

  // TIDAK panggil listview.refresh() di sini — biarkan proses setup awal selesai natural
};