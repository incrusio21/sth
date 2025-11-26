frappe.KomoditiEditor = class {
	constructor(wrapper, frm, disable) {
		this.frm = frm;
		this.wrapper = wrapper;
		this.disable = disable;
		
		let user_komoditi = this.frm.doc.custom_customer_komoditi ? this.frm.doc.custom_customer_komoditi.map((a) => a.komoditi) : [];
		
		this.multicheck = frappe.ui.form.make_control({
			parent: wrapper,
			df: {
				fieldname: "komoditi",
				fieldtype: "MultiCheck",
				columns: "15rem",
				get_data: () => {
					return frappe.call({
						method: "frappe.client.get_list",
						args: {
							doctype: "Komoditi",
							fields: ["name"],
							order_by: "name asc",
							limit_page_length: 0
						}
					}).then((r) => {
						return r.message.map((komoditi) => {
							return {
								label: __(komoditi.name),
								value: komoditi.name,
								checked: user_komoditi.includes(komoditi.name),
							};
						});
					});
				},
				on_change: () => {
					this.set_komoditi_in_table();
					this.frm.dirty();
				},
			},
			render_input: true,
		});

		let original_func = this.multicheck.make_checkboxes;
		this.multicheck.make_checkboxes = () => {
			original_func.call(this.multicheck);
			this.multicheck.$wrapper.find(".label-area").click((e) => {
				let komoditi = $(e.target).data("unit");
				komoditi && this.show_komoditi_details(komoditi);
				e.preventDefault();
			});
		};
	}

	set_enable_disable() {
		$(this.wrapper)
			.find('input[type="checkbox"]')
			.attr("disabled", this.disable ? true : false);
	}

	show_komoditi_details(komoditi_name) {
		if (!this.detail_dialog) {
			this.make_detail_dialog();
		}
		$(this.detail_dialog.body).empty();
		
		return frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Komoditi",
				name: komoditi_name
			}
		}).then((r) => {
			const $body = $(this.detail_dialog.body);
			const komoditi = r.message;
			
			$body.append(`
				<div class="komoditi-details">
					<table class="table table-bordered">
						<tbody>
							<tr>
								<th style="width: 30%">${__("Name")}</th>
								<td>${komoditi.name}</td>
							</tr>
							<!-- Add more fields as needed -->
						</tbody>
					</table>
				</div>
			`);
			
			this.detail_dialog.set_title(__(komoditi_name));
			this.detail_dialog.show();
		});
	}

	make_detail_dialog() {
		this.detail_dialog = new frappe.ui.Dialog({
			title: __("Komoditi Details"),
		});

		this.detail_dialog.$wrapper
			.find(".modal-dialog")
			.css("width", "auto")
			.css("max-width", "800px");
	}

	show() {
		this.reset();
		this.set_enable_disable();
	}

	reset() {
		let user_komoditi = (this.frm.doc.custom_customer_komoditi || []).map((a) => a.komoditi);
		this.multicheck.selected_options = user_komoditi;
		this.multicheck.refresh_input();
	}

	set_komoditi_in_table() {
		let komoditi_list = this.frm.doc.custom_customer_komoditi || [];
		let checked_options = this.multicheck.get_checked_options();
		
		komoditi_list.map((komoditi_doc) => {
			if (!checked_options.includes(komoditi_doc.komoditi)) {
				frappe.model.clear_doc(komoditi_doc.doctype, komoditi_doc.name);
			}
		});
		
		checked_options.map((komoditi) => {
			if (!komoditi_list.find((d) => d.komoditi === komoditi)) {
				let komoditi_doc = frappe.model.add_child(this.frm.doc, "Customer Komoditi", "custom_customer_komoditi");
				komoditi_doc.komoditi = komoditi;
			}
		});

		this.frm.refresh_field("custom_customer_komoditi")
	}

	get_komoditi() {
		return {
			checked_komoditi: this.multicheck.get_checked_options(),
			unchecked_komoditi: this.multicheck.get_unchecked_options(),
		};
	}
};