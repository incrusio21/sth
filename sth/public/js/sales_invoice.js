// Tampilan link title (title field) dimatikan selama berada di Sales Invoice,
// supaya field link menampilkan nama dokumen aslinya.
// frappe.utils bersifat global dan desk tidak reload saat pindah menu, jadi fungsi
// aslinya disimpan lalu dikembalikan begitu route keluar dari doctype ini.
const SI_DOCTYPE = "Sales Invoice";
// Kosongkan untuk semua doctype, atau isi mis. ["Customer"] untuk membatasi.
const SI_HIDE_LINK_TITLE_FOR = [];

let si_original_link_title = null;

function si_is_link_title_hidden(doctype) {
	return !SI_HIDE_LINK_TITLE_FOR.length || SI_HIDE_LINK_TITLE_FOR.includes(doctype);
}

function si_hide_link_title() {
	if (si_original_link_title) return;

	si_original_link_title = {
		get: frappe.utils.get_link_title,
		fetch: frappe.utils.fetch_link_title
	};

	// Mengembalikan name apa adanya; formatter Link menganggapnya "tanpa title".
	frappe.utils.get_link_title = function (doctype, name) {
		if (si_is_link_title_hidden(doctype)) return name;
		return si_original_link_title.get.apply(this, arguments);
	};

	frappe.utils.fetch_link_title = function (doctype, name) {
		if (si_is_link_title_hidden(doctype)) return Promise.resolve(name);
		return si_original_link_title.fetch.apply(this, arguments);
	};
}

function si_restore_link_title() {
	if (!si_original_link_title) return;

	frappe.utils.get_link_title = si_original_link_title.get;
	frappe.utils.fetch_link_title = si_original_link_title.fetch;
	si_original_link_title = null;
}

function si_sync_link_title() {
	const route = frappe.get_route() || [];
	if (route[1] === SI_DOCTYPE) {
		si_hide_link_title();
	} else {
		si_restore_link_title();
	}
}

if (!frappe.__si_link_title_watcher) {
	frappe.__si_link_title_watcher = true;
	frappe.router.on("change", si_sync_link_title);
}

frappe.ui.form.on('Sales Invoice', {
	refresh: function(frm) {
		si_sync_link_title();
		set_rate_precision(frm)
		set_komoditi_filter(frm);
		set_query_unit(frm)
		toggle_qty_timbang_column(frm);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Ambil Asset'), function() {
				show_pilih_asset_dialog(frm);
			}, __('Get Items From'));
		}
	},
	jenis_penagihan: function(frm) {
		toggle_qty_timbang_column(frm);
	},
	komoditi: function(frm) {
		if (frm.doc.komoditi && frm.doc.party_name && frm.doc.quotation_to == "Customer") {
			validate_komoditi(frm);
		}

		if (frm.doc.komoditi) {
			frm.clear_table('keterangan_per_komoditi');
			
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Komoditi',
					name: frm.doc.komoditi
				},
				callback: function(r) {
					if (r.message && r.message.keterangan_per_komoditi) {
						r.message.keterangan_per_komoditi.forEach(function(row) {
							let child_row = frm.add_child('keterangan_per_komoditi');
							child_row.keterangan = row.keterangan;
							child_row.parameter = row.parameter;
						});
						
						frm.refresh_field('keterangan_per_komoditi');
					}
				}
			});
		}
	},
	onload: function(frm){
		// dipanggil sebelum field dirender, supaya link tidak sempat tampil sebagai title
		si_sync_link_title();
		set_query_unit(frm)
	},
	company: function(frm){
		set_query_unit(frm)
	},
	jenis_berikat: function(frm) {
		if (frm.doc.jenis_berikat == "Ya") {
			frm.set_value('kode_faktur', '07');
			frm.set_df_property('kode_faktur', 'read_only', 1);
		} else {
			frm.set_df_property('kode_faktur', 'read_only', 0);
		}
	},

})


frappe.ui.form.on('Sales Invoice Item', {
	qty_timbang_customer:function(frm,cdt,cdn){
		let baris = locals[cdt][cdn]
		if(baris.qty_timbang_customer){
			if(baris.rate){
				baris.sub_total_timbang = baris.rate * baris.qty_timbang_customer
			}
		}
	},
	item_code: function(frm, cdt, cdn) {
		cek_item_default_account(frm, cdt, cdn);
	}
})

// Untuk Jenis Penagihan Others kedua akun wajib datang dari Item Defaults, dan save
// ditolak kalau belum ada. Pengecekannya diulang di sini supaya ketahuan sejak
// itemnya dipilih, bukan setelah seluruh invoice selesai diisi.
function cek_item_default_account(frm, cdt, cdn) {
	if (frm.doc.jenis_penagihan != 'Others') return;

	let baris = locals[cdt][cdn];
	if (!baris.item_code || !frm.doc.company) return;

	frappe.xcall(
		'sth.sales_sth.custom.sales_invoice.get_item_default_accounts',
		{ item_code: baris.item_code, company: frm.doc.company }
	).then(function (akun) {
		let kosong = [];
		if (!akun.income_account) kosong.push(__('Income Account'));
		if (!akun.expense_account) kosong.push(__('Expense Account'));

		if (kosong.length) {
			frappe.msgprint({
				title: __('Item Default Belum Lengkap'),
				indicator: 'red',
				message: __('Item {0} belum punya {1} di Item Defaults untuk company {2}. Lengkapi dulu di master Item, kalau tidak invoice ini tidak bisa disimpan.', [
					baris.item_code.bold(), kosong.join(__(' dan ')).bold(), frm.doc.company.bold()
				])
			});
			return;
		}

		// Disamakan sekarang juga supaya yang tampil di form sama dengan yang
		// nanti ditulis server saat save
		frappe.model.set_value(cdt, cdn, 'income_account', akun.income_account);
		frappe.model.set_value(cdt, cdn, 'expense_account', akun.expense_account);
	});
}

function set_komoditi_filter(frm) {
	if (frm.doc.quotation_to == "Customer" && frm.doc.party_name) {
		frappe.call({
			method: 'frappe.client.get',
			args: {
				doctype: 'Customer',
				name: frm.doc.party_name
			},
			callback: function(r) {
				if (r.message && r.message.custom_customer_komoditi) {
					let komoditi_list = r.message.custom_customer_komoditi.map(function(row) {
						return row.komoditi;
					});
				
					if (komoditi_list.length > 0) {
						frm.set_query('komoditi', function() {
							return {
								filters: {
									'name': ['in', komoditi_list]
								}
							};
						});
					} else {
						frm.set_query('komoditi', function() {
							return {
								filters: {
									'name': ['in', []]
								}
							};
						});
					}
				}
			}
		});
	} else {
		frm.set_query('komoditi', function() {
			return {};
		});
	}
}

function validate_komoditi(frm) {
	if (!frm.doc.quotation_to == "Customer") {
		return;
	}

	if (!frm.doc.party_name) {
		return;
	}
	
	frappe.call({
		method: 'frappe.client.get',
		args: {
			doctype: 'Customer',
			name: frm.doc.party_name
		},
		callback: function(r) {
			if (r.message && r.message.custom_customer_komoditi) {
				let komoditi_list = r.message.custom_customer_komoditi.map(function(row) {
					return row.komoditi;
				});
				
				if (!komoditi_list.includes(frm.doc.komoditi)) {
					frappe.msgprint({
						title: __('Invalid Komoditi'),
						indicator: 'red',
						message: __('The selected Komoditi "{0}" is not linked to Customer "{1}". Please select a valid Komoditi.', [frm.doc.komoditi, frm.doc.party_name])
					});
					frm.set_value('komoditi', '');
				}
			}
		}
	});
}


function set_query_unit(frm){
	frm.set_query('unit', function() {
		return {
			filters: {
				'company': frm.doc.company
			}
		};
	});
}

function show_pilih_asset_dialog(frm) {
	let dialog = new frappe.ui.Dialog({
		title: __('Pilih Asset untuk Dijual'),
		fields: [
			{
				fieldname: 'asset',
				fieldtype: 'Link',
				options: 'Asset',
				label: __('Asset'),
				reqd: 1,
				get_query: function() {
					let filters = [
						['docstatus', '=', 1],
						['status', '=', 'Scrapped']
					];
					if (frm.doc.company) {
						filters.push(['company', '=', frm.doc.company]);
					}
					return { filters: filters };
				}
			}
		],
		primary_action_label: __('Ambil'),
		primary_action: function(values) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Asset',
					filters: values.asset,
					fieldname: ['item_code', 'asset_name', 'unit', 'company']
				},
				callback: function(r) {
					if (!r.message) return;
					let asset = r.message;

					if (frm.doc.company && asset.company && asset.company !== frm.doc.company) {
						frappe.msgprint(__('Company Asset ({0}) berbeda dengan Company Sales Invoice ({1}).', [asset.company, frm.doc.company]));
						return;
					}

					let row = frm.add_child('items');
					row.item_code = asset.item_code;
					row.is_fixed_asset = 1;
					row.asset = values.asset;
					row.qty = 1;
					frm.refresh_field('items');

					// Sekali ambil, dipakai dua kali: debit_to sekarang dan expense_account
					// setelah trigger asset selesai.
					let akun_penjualan_asset = ambil_akun_penjualan_asset(frm);

					frm.script_manager.trigger('item_code', row.doctype, row.name).then(function() {
						frappe.model.set_value(row.doctype, row.name, 'item_code', asset.item_code);
						frappe.model.set_value(row.doctype, row.name, 'is_fixed_asset', 1);
						frappe.model.set_value(row.doctype, row.name, 'asset', values.asset).then(function() {
							frm.script_manager.trigger('asset', row.doctype, row.name).then(function() {
								// Harus setelah trigger asset selesai, kalau tidak akan ditimpa
								// expense account bawaan (disposal account dari Company).
								akun_penjualan_asset.then((akun) => {
									if (akun.expense_account) {
										frappe.model.set_value(row.doctype, row.name, 'expense_account', akun.expense_account);
									}
								});
							});
						});
					});

					frm.set_value('jenis_penagihan', 'Disposal');
					if (asset.unit) {
						frm.set_value('unit', asset.unit);
					}

					akun_penjualan_asset.then((akun) => {
						if (akun.piutang_account) {
							frm.set_value('debit_to', akun.piutang_account);
						}
					});

					frm.refresh_field('items');
					dialog.hide();
				}
			});
		}
	});

	dialog.show();
}

function ambil_akun_penjualan_asset(frm) {
	return frappe.call({
		method: 'sth.accounting_sth.doctype.sth_accounting_settings.sth_accounting_settings.get_akun_penjualan_asset',
		args: { company: frm.doc.company }
	}).then((r) => {
		let akun = (r && r.message) || {};

		if (!akun.piutang_account || !akun.expense_account) {
			frappe.msgprint(__('Akun Penjualan Asset untuk company {0} belum lengkap di STH Accounting Settings.', [frm.doc.company]));
		}

		return akun;
	});
}

erpnext.accounts.SalesInvoiceControllerCustom = class SalesInvoiceController extends (
	erpnext.selling.SellingController
) {
	setup(doc) {
		this.setup_posting_date_time_check();
		super.setup(doc);
		this.frm.make_methods = {
			Dunning: this.make_dunning.bind(this),
			"Invoice Discounting": this.make_invoice_discounting.bind(this),
		};
	}
	company() {
		super.company();
		erpnext.accounts.dimensions.update_dimension(this.frm, this.frm.doctype);
	}
	onload() {
		var me = this;
		super.onload();

		this.frm.ignore_doctypes_on_cancel_all = [
			"POS Invoice",
			"Timesheet",
			"POS Invoice Merge Log",
			"POS Closing Entry",
			"Journal Entry",
			"Payment Entry",
			"Repost Payment Ledger",
			"Repost Accounting Ledger",
			"Unreconcile Payment",
			"Unreconcile Payment Entries",
			"Serial and Batch Bundle",
			"Bank Transaction",
		];

		if (!this.frm.doc.__islocal && !this.frm.doc.customer && this.frm.doc.debit_to) {
			// show debit_to in print format
			this.frm.set_df_property("debit_to", "print_hide", 0);
		}

		erpnext.queries.setup_queries(this.frm, "Warehouse", function () {
			return erpnext.queries.warehouse(me.frm.doc);
		});

		if (this.frm.doc.__islocal && this.frm.doc.is_pos) {
			//Load pos profile data on the invoice if the default value of Is POS is 1

			me.frm.script_manager.trigger("is_pos");
			me.frm.refresh_fields();
		}
		erpnext.queries.setup_warehouse_query(this.frm);
	}

	refresh(doc, dt, dn) {
		const me = this;
		super.refresh();

		if (this.frm?.msgbox && this.frm.msgbox.$wrapper.is(":visible")) {
			// hide new msgbox
			this.frm.msgbox.hide();
		}

		this.frm.toggle_reqd("due_date", !this.frm.doc.is_return);

		if (this.frm.doc.is_return) {
			this.frm.return_print_format = "Sales Invoice Return";
		}

		this.show_general_ledger();
		erpnext.accounts.ledger_preview.show_accounting_ledger_preview(this.frm);

		if (doc.update_stock) {
			this.show_stock_ledger();
			erpnext.accounts.ledger_preview.show_stock_ledger_preview(this.frm);
		}

		if (doc.docstatus == 1 && doc.outstanding_amount != 0) {
			this.frm.add_custom_button(__("Payment"), () => this.make_payment_entry(), __("Create"));
			this.frm.page.set_inner_btn_group_as_primary(__("Create"));
		}

		if (doc.docstatus == 1 && !doc.is_return) {
			var is_delivered_by_supplier = false;

			is_delivered_by_supplier = cur_frm.doc.items.some(function (item) {
				return item.is_delivered_by_supplier ? true : false;
			});

			if (doc.outstanding_amount >= 0 || Math.abs(flt(doc.outstanding_amount)) < flt(doc.grand_total)) {
				cur_frm.add_custom_button(__("Return / Credit Note"), this.make_sales_return, __("Create"));
				cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
			}

			if (cint(doc.update_stock) != 1) {
				// show Make Delivery Note button only if Sales Invoice is not created from Delivery Note
				var from_delivery_note = false;
				from_delivery_note = cur_frm.doc.items.some(function (item) {
					return item.delivery_note ? true : false;
				});

				if (!from_delivery_note && !is_delivered_by_supplier) {
					cur_frm.add_custom_button(
						__("Delivery"),
						cur_frm.cscript["Make Delivery Note"],
						__("Create")
					);
				}
			}

			if (doc.outstanding_amount > 0) {
				cur_frm.add_custom_button(
					__("Payment Request"),
					function () {
						me.make_payment_request();
					},
					__("Create")
				);
				this.frm.add_custom_button(
					__("Invoice Discounting"),
					this.make_invoice_discounting.bind(this),
					__("Create")
				);

				const payment_is_overdue = doc.payment_schedule
					.map((row) => Date.parse(row.due_date) < Date.now())
					.reduce((prev, current) => prev || current, false);

				if (payment_is_overdue) {
					this.frm.add_custom_button(__("Dunning"), this.make_dunning.bind(this), __("Create"));
				}
			}

			if (doc.docstatus === 1) {
				cur_frm.add_custom_button(
					__("Maintenance Schedule"),
					this.make_maintenance_schedule.bind(this),
					__("Create")
				);
			}
		}

		// Show buttons only when pos view is active
		if (cint(doc.docstatus == 0) && cur_frm.page.current_view_name !== "pos" && !doc.is_return) {
			this.frm.cscript.sales_order_btn();
			this.frm.cscript.delivery_note_btn();
			this.frm.cscript.quotation_btn();
		}

		this.set_default_print_format();
		if (doc.docstatus == 1 && !doc.inter_company_invoice_reference) {
			let internal = me.frm.doc.is_internal_customer;
			if (internal) {
				let button_label =
					me.frm.doc.company === me.frm.doc.represents_company
						? "Internal Purchase Invoice"
						: "Inter Company Purchase Invoice";

				me.frm.add_custom_button(
					button_label,
					function () {
						me.make_inter_company_invoice();
					},
					__("Create")
				);
			}
		}

		erpnext.accounts.unreconcile_payment.add_unreconcile_btn(me.frm);
	}

	make_invoice_discounting() {
		frappe.model.open_mapped_doc({
			method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.create_invoice_discounting",
			frm: this.frm,
		});
	}

	make_dunning() {
		frappe.model.open_mapped_doc({
			method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.create_dunning",
			frm: this.frm,
		});
	}

	make_maintenance_schedule() {
		frappe.model.open_mapped_doc({
			method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_maintenance_schedule",
			frm: cur_frm,
		});
	}

	on_submit(doc, dt, dn) {
		var me = this;

		super.on_submit();
		if (frappe.get_route()[0] != "Form") {
			return;
		}

		doc.items.forEach((row) => {
			if (row.delivery_note) frappe.model.clear_doc("Delivery Note", row.delivery_note);
		});
	}

	set_default_print_format() {
		// set default print format to POS type or Credit Note
		if (cur_frm.doc.is_pos) {
			if (cur_frm.pos_print_format) {
				cur_frm.meta._default_print_format = cur_frm.meta.default_print_format;
				cur_frm.meta.default_print_format = cur_frm.pos_print_format;
			}
		} else if (cur_frm.doc.is_return && !cur_frm.meta.default_print_format) {
			if (cur_frm.return_print_format) {
				cur_frm.meta._default_print_format = cur_frm.meta.default_print_format;
				cur_frm.meta.default_print_format = cur_frm.return_print_format;
			}
		} else {
			if (cur_frm.meta._default_print_format) {
				cur_frm.meta.default_print_format = cur_frm.meta._default_print_format;
				cur_frm.meta._default_print_format = null;
			} else if (
				in_list(
					[cur_frm.pos_print_format, cur_frm.return_print_format],
					cur_frm.meta.default_print_format
				)
			) {
				cur_frm.meta.default_print_format = null;
				cur_frm.meta._default_print_format = null;
			}
		}
	}

	sales_order_btn() {
		var me = this;
		this.$sales_order_btn = this.frm.add_custom_button(
			__("Sales Order"),
			function () {
				erpnext.utils.map_current_doc({
					method: "sth.overrides.sales_order.make_sales_invoice",
					source_doctype: "Sales Order",
					target: me.frm,
					setters: {
						customer: me.frm.doc.customer || undefined,
						no_kontrak_external : undefined

						
					},
					get_query_filters: {
						docstatus: 1,
						status: ["not in", ["Closed", "On Hold"]],
						per_billed: ["<", 99.99],
						company: me.frm.doc.company,
					},
				});
			},
			__("Get Items From")
		);
	}

	quotation_btn() {
		var me = this;
		this.$quotation_btn = this.frm.add_custom_button(
			__("Quotation"),
			function () {
				erpnext.utils.map_current_doc({
					method: "erpnext.selling.doctype.quotation.quotation.make_sales_invoice",
					source_doctype: "Quotation",
					target: me.frm,
					setters: [
						{
							fieldtype: "Link",
							label: __("Customer"),
							options: "Customer",
							fieldname: "party_name",
							default: me.frm.doc.customer,
						},
					],
					get_query_filters: {
						docstatus: 1,
						status: ["!=", "Lost"],
						company: me.frm.doc.company,
					},
				});
			},
			__("Get Items From")
		);
	}

	delivery_note_btn() {
		var me = this;
		this.$delivery_note_btn = this.frm.add_custom_button(
			__("Delivery Note"),
			function () {
				erpnext.utils.map_current_doc({
					method: "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
					source_doctype: "Delivery Note",
					target: me.frm,
					date_field: "posting_date",
					setters: {
						customer: me.frm.doc.customer || undefined,
					},
					get_query: function () {
						var filters = {
							docstatus: 1,
							company: me.frm.doc.company,
							is_return: 0,
						};
						if (me.frm.doc.customer) filters["customer"] = me.frm.doc.customer;
						return {
							query: "erpnext.controllers.queries.get_delivery_notes_to_be_billed",
							filters: filters,
						};
					},
				});
			},
			__("Get Items From")
		);
	}

	tc_name() {
		this.get_terms();
	}
	customer() {
		if (this.frm.doc.is_pos) {
			var pos_profile = this.frm.doc.pos_profile;
		}
		var me = this;
		if (this.frm.updating_party_details) return;

		if (this.frm.doc.__onload && this.frm.doc.__onload.load_after_mapping) return;

		erpnext.utils.get_party_details(
			this.frm,
			"erpnext.accounts.party.get_party_details",
			{
				posting_date: this.frm.doc.posting_date,
				party: this.frm.doc.customer,
				party_type: "Customer",
				account: this.frm.doc.debit_to,
				price_list: this.frm.doc.selling_price_list,
				pos_profile: pos_profile,
				fetch_payment_terms_template: cint(
					(this.frm.doc.is_return == 0) & !this.frm.doc.ignore_default_payment_terms_template
				),
			},
			function () {
				me.apply_pricing_rule();
			}
		);

		if (this.frm.doc.customer) {
			frappe.call({
				method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.get_loyalty_programs",
				args: {
					customer: this.frm.doc.customer,
				},
				callback: function (r) {
					if (r.message && r.message.length > 1) {
						select_loyalty_program(me.frm, r.message);
					}
				},
			});
		}
	}

	make_inter_company_invoice() {
		let me = this;
		frappe.model.open_mapped_doc({
			method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_inter_company_purchase_invoice",
			frm: me.frm,
		});
	}

	debit_to() {
		var me = this;
		if (this.frm.doc.debit_to) {
			me.frm.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Account",
					fieldname: "account_currency",
					filters: { name: me.frm.doc.debit_to },
				},
				callback: function (r, rt) {
					if (r.message) {
						me.frm.set_value("party_account_currency", r.message.account_currency);
						me.set_dynamic_labels();
					}
				},
			});
		}
	}

	allocated_amount() {
		this.calculate_total_advance();
		this.frm.refresh_fields();
	}

	write_off_outstanding_amount_automatically() {
		if (cint(this.frm.doc.write_off_outstanding_amount_automatically)) {
			frappe.model.round_floats_in(this.frm.doc, ["grand_total", "paid_amount"]);
			// this will make outstanding amount 0
			this.frm.set_value(
				"write_off_amount",
				flt(
					this.frm.doc.grand_total - this.frm.doc.paid_amount - this.frm.doc.total_advance,
					precision("write_off_amount")
				)
			);
		}

		this.calculate_outstanding_amount(false);
		this.frm.refresh_fields();
	}

	write_off_amount() {
		this.set_in_company_currency(this.frm.doc, ["write_off_amount"]);
		this.write_off_outstanding_amount_automatically();
	}

	items_add(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		this.frm.script_manager.copy_from_first_row("items", row, [
			"income_account",
			"discount_account",
			"cost_center",
		]);
	}

	set_dynamic_labels() {
		super.set_dynamic_labels();
		this.frm.events.hide_fields(this.frm);
	}

	items_on_form_rendered() {
		erpnext.setup_serial_or_batch_no();
	}

	packed_items_on_form_rendered(doc, grid_row) {
		erpnext.setup_serial_or_batch_no();
	}

	make_sales_return() {
		frappe.model.open_mapped_doc({
			method: "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return",
			frm: cur_frm,
		});
	}

	asset(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.asset) {
			frappe.call({
				method: erpnext.assets.doctype.asset.depreciation.get_disposal_account_and_cost_center,
				args: {
					company: frm.doc.company,
				},
				callback: function (r, rt) {
					frappe.model.set_value(cdt, cdn, "income_account", r.message[0]);
					frappe.model.set_value(cdt, cdn, "cost_center", r.message[1]);
				},
			});
		}
	}

	is_pos(frm) {
		this.set_pos_data();
	}

	pos_profile() {
		this.frm.doc.taxes = [];
		this.set_pos_data();
	}

	set_pos_data() {
		if (this.frm.doc.is_pos) {
			this.frm.set_value("allocate_advances_automatically", 0);
			if (!this.frm.doc.company) {
				this.frm.set_value("is_pos", 0);
				frappe.msgprint(__("Please specify Company to proceed"));
			} else {
				var me = this;
				const for_validate = me.frm.doc.is_return ? true : false;
				return this.frm.call({
					doc: me.frm.doc,
					method: "set_missing_values",
					args: {
						for_validate: for_validate,
					},
					callback: function (r) {
						if (!r.exc) {
							if (r.message && r.message.print_format) {
								me.frm.pos_print_format = r.message.print_format;
							}
							me.frm.trigger("update_stock");
							if (me.frm.doc.taxes_and_charges) {
								me.frm.script_manager.trigger("taxes_and_charges");
							}

							frappe.model.set_default_values(me.frm.doc);
							me.set_dynamic_labels();
							me.calculate_taxes_and_totals();
						}
					},
				});
			}
		} else this.frm.trigger("refresh");
	}

	amount() {
		this.write_off_outstanding_amount_automatically();
	}

	change_amount() {
		if (this.frm.doc.paid_amount > this.frm.doc.grand_total) {
			this.calculate_write_off_amount();
		} else {
			this.frm.set_value("change_amount", 0.0);
			this.frm.set_value("base_change_amount", 0.0);
		}

		this.frm.refresh_fields();
	}

	loyalty_amount() {
		this.calculate_outstanding_amount();
		this.frm.refresh_field("outstanding_amount");
		this.frm.refresh_field("paid_amount");
		this.frm.refresh_field("base_paid_amount");
	}

	currency() {
		var me = this;
		super.currency();
		if (this.frm.doc.timesheets) {
			this.frm.doc.timesheets.forEach((d) => {
				let row = frappe.get_doc(d.doctype, d.name);
				set_timesheet_detail_rate(row.doctype, row.name, me.frm.doc.currency, row.timesheet_detail);
			});
			this.frm.trigger("calculate_timesheet_totals");
		}
	}

	is_cash_or_non_trade_discount() {
		this.frm.set_df_property(
			"additional_discount_account",
			"hidden",
			1 - this.frm.doc.is_cash_or_non_trade_discount
		);
		this.frm.set_df_property(
			"additional_discount_account",
			"reqd",
			this.frm.doc.is_cash_or_non_trade_discount
		);

		if (!this.frm.doc.is_cash_or_non_trade_discount) {
			this.frm.set_value("additional_discount_account", "");
		}

		this.calculate_taxes_and_totals();
	}
};

function toggle_qty_timbang_column(frm) {
	const is_pengiriman = frm.doc.jenis_penagihan == "Pengiriman";

	frm.fields_dict['items'].grid.toggle_display('qty_timbang_customer', is_pengiriman);
	frm.fields_dict['items'].grid.refresh();
	frm.fields_dict['items'].grid.toggle_display('sub_total_timbang', is_pengiriman);
	frm.fields_dict['items'].grid.refresh();
}

function set_rate_precision(frm){
	frm.fields_dict['items'].grid.update_docfield_property(
		'rate', 'precision', 2
	);
}

// for backward compatibility: combine new and previous states
extend_cscript(cur_frm.cscript, new erpnext.accounts.SalesInvoiceControllerCustom({ frm: cur_frm }));

