// console.log("run unit_filter.js");

$(document).on("form-refresh", function (event, frm) {
  if (frm.meta.module !== "Mill") return;

  if (frm.fields_dict.unit) {
    frm.set_query("unit", function () {
      return {
        filters: {
          company: frm.doc.company,
          mill: 1
        }
      };
    });
  }

  frm.fields_dict.company?.df && frm.$wrapper.on("change", "[data-fieldname='company']", function () {
    if (frm.fields_dict.unit) {
      frm.set_value("unit", null);
      frm.set_query("unit", function () {
        return {
          filters: {
            company: frm.doc.company,
            mill: 1
          }
        };
      });
      frm.refresh_field("unit");
    }
  });

  if (frm.fields_dict.pabrik) {
    frm.fields_dict.pabrik.df.onchange = function () {
      // console.log("unit changed:", frm.doc.unit);
      if (frm.fields_dict.shift_proses) {
        frm.set_value("shift_proses", null);
        frm.set_query("shift_proses", function () {
          return {
            filters: {
              unit: frm.doc.unit
            }
          };
        });
        frm.refresh_field("shift_proses");
      }
    };
  }
});