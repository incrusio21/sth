// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pemeriksaan Ampere Motor", {
    onload(frm) {
        if (frm.is_new()) {
            new frappe.ui.Scanner({
                dialog: true,
                multiple: false,
                on_scan(data) {
                    if (data && data.result && data.result.text) {
                        const scan_data = JSON.parse(data.result.text)
                        frm.set_value("stasiun", scan_data.stasiun);
                        frm.set_value("stasiun_latitude", scan_data.latitude);
                        frm.set_value("stasiun_longitude", scan_data.longitude);

                        frm.set_value("tanggal_scan", frappe.datetime.get_today())
                        frm.set_value("jam_scan", moment().format('HH:mm:ss'))
                        frm.set_value("user_scan", frappe.session.user)
                    }
                },
            })

            frm.trigger('get_location')
        }
    },

    refresh(frm) {
        if (frm.doc.docstatus != 2) {
            frm.trigger("show_warning_list")
        }
    },

    show_warning_list(frm) {
        let warning_lists = JSON.parse(frm.doc.warning_list || "[]");
        if (!warning_lists.length) {
            frm.set_df_property("section_break_wmxo", "hidden", 1)
            return
        }

        const message = `
			<div class="warning-message form-message yellow">
				<ul class="mb-0">
					${warning_lists.map(item => `<li>${item}</li>`).join('')}
				</ul>
			</div>
		`

        frm.get_field("warning_message").$wrapper.html(message)
        frm.set_df_property("section_break_wmxo", "hidden", 0)
    },

    get_location(frm) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                let latitude = position.coords.latitude
                let longitude = position.coords.longitude
                frm.set_value("latitude", latitude)
                frm.set_value("longitude", longitude)
            },
            (err) => {
                frappe.msgprint(err.message);
            }
        );
    },
});
