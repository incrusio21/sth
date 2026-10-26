$(document).on("app_ready", function () {
  if (!erpnext.accounts || !erpnext.accounts.ledger_preview) return;

  erpnext.accounts.ledger_preview.get_datatable = function (columns, data, wrapper) {
    const money_cols = /^(Debit|Credit|Kredit)/i;

    columns = columns.map((col) => {
      if (money_cols.test(col.name || "")) {
        return Object.assign({}, col, {
          align: "right",
          format: (value) =>
            value === "" || value === null || value === undefined
              ? ""
              : format_number(value, null, 2),
        });
      }
      return col;
    });

    new frappe.DataTable(wrapper, {
      columns: columns,
      data: data,
      dynamicRowHeight: true,
      checkboxColumn: false,
      inlineFilters: true,
    });
  };
});