frappe.pages['komparasi-penawaran-supplier'].on_page_load = function (wrapper) {
	new SupplierComparasion(wrapper)
}

class SupplierComparasion {
	constructor(wrapper) {
		this.wrapper = wrapper
		frappe.require(
			[
				"/assets/sth/css/komparasi_supplier.css",
			], () => {
				this.init()
			})
	}

	init() {
		this.page = frappe.ui.make_app_page({
			parent: this.wrapper,
			title: 'Komparasi Penawaran Harga Supplier',
			single_column: true
		});

		this.suppliers = []
		this.data = []
		this.selected_items = []
		this.selected_suppliers = ""

		// console.log(this.page);
		this.content_wrapper = $(`
			<div id="supplier-comparasion" class='komparasion-style'>
				<div id="table-comparasion">
				</div>
			</div>
		`)
		this.page.main.append(this.content_wrapper)
		this.setupSearchField()
		this.setupCustomField()
		this.initTable()
	}

	setupSearchField() {
		var me = this;

		this.company = frappe.defaults.get_user_default("company");

		this.page.add_field({
			fieldtype: "Link",
			fieldname: "company",
			options: "Company",
			label: __("Company"),
			reqd: 1,
			default: this.company,
			change: function () {
				me.company = this.value

			},
		})

		this.page.add_field({
			fieldtype: "Link",
			fieldname: "pr_sr",
			options: "Material Request",
			label: __("PR/SR"),
			get_query: function () {
				return {
					filters: {
						"company": me.company,
					}
				};
			},
			change: function () {
				me.pr_sr = this.value
				me.refresh_table()
			},
		})

		this.page.add_field({
			fieldtype: "Data",
			fieldname: "item_name",
			label: __("Nama Barang"),
			change: function () {
				me.item_name = this.value
				me.refresh_table()
			},
		})

		this.page.add_field({
			fieldtype: "MultiSelectList",
			fieldname: "filter_sq",
			label: __("Supplier Quotation"),
			get_data: function () {
				return frappe.call({
					method: 'frappe.client.get_list',
					args: {
						doctype: 'Supplier Quotation',
						filters: {
							company: me.company,
							custom_material_request: me.pr_sr
						},
						fields: ['name', "supplier"],
						order_by: 'name asc',
						limit_page_length: 0
					}
				}).then(r => {
					return r.message.map(item => ({
						value: item.name,
						description: item.supplier
					}));
				});
			},
			change: frappe.utils.debounce(function () {
				me.filter_sq = this._selected_values.map((r) => r.value)
				me.refresh_table()
			}, 1000)
		})
	}

	setupCustomField() {
		var me = this;

		this.sq_field = this.page.add_field({
			fieldtype: "Link",
			fieldname: "sq",
			options: "Supplier Quotation",
			label: __("SQ Number"),
			get_query: function () {
				return {
					filters: {
						"company": me.company,
						"workflow_state": "Need To Compare"
					}
				};
			},
			change: function () {
				me.supllier_quotation = this.value
			},
		})
		this.btn_approve = this.page.add_button("Approve", () => {
			if (!this.supllier_quotation) {
				return
			}

			frappe.confirm(`Apakah anda yakin ingin approve document ${this.supllier_quotation} ?`,
				() => {
					me.approve_sq()
				}, () => {
					// action to perform if No is selected
				})
		}, {
			btn_class: "btn-success"
		})

		this.btn_chosen_items = this.page.add_button("Choosen items", () => {
			frappe.xcall("sth.api.get_sq_item_details", { names: [...new Set(this.selected_items.map(r => r.child_name))] }).then((res) => {
				me.showSelectedItem(res)
			})
		}, {
			btn_class: "btn-default"
		})
		this.page.page_form.append(this.btn_approve)
		this.page.page_form.append(this.btn_chosen_items)

		this.sq_field.$wrapper.css({
			"margin-left": "auto",
			"display": "none"
		})

		this.btn_approve.css({
			"align-self": "center",
			"display": "none"
		})

		this.btn_chosen_items.css({
			"align-self": "center",
			"margin-left": "auto"
		})
		// "margin-left": "10px", jika nanti btn approve tidak di hide 

	}

	initTable() {
		const columns = this.generateColumns()
		this.table = new Tabulator("#table-comparasion", {
			// layout: "fitDataStretch",
			selectable: true,
			columnHeaderVertAlign: "middle",
			maxHeight: "80vh",
			renderHorizontal: "virtual",
			// rowHeader: {
			// 	headerSort: false, resizable: false, frozen: true, headerHozAlign: "center", hozAlign: "center", formatter: "rowSelection", titleFormatter: "rowSelection", cellClick: function (e, cell) {
			// 		cell.getRow().toggleSelect();
			// 	}
			// },
			columns
		});

		// this.setTableEvent()
		this.refresh_view()
		// window.pageData = this
	}

	initTablePamakaianMaterial(el, data = []) {
		let options = {
			// layout: "fitDataStretch",
			selectable: true,
			data,
			columnHeaderVertAlign: "middle",
			maxHeight: "80vh",
			renderHorizontal: "virtual",
			columns: [
				{ title: "No", formatter: "rownum", headerSort: false, hozAlign: "center", headerHozAlign: "center", resizable: false, },
				{ title: "No Transaksi", field: "no_transaksi", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Tanggal", field: "tanggal", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Gudang", field: "gudang", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Sub Unit", field: "sub_unit", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Alokasi", field: "alokasi", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Kendaraan", field: "kendaraan", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Pengguna", field: "pengguna", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Kode Barang", field: "kode_barang", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Nama Barang", field: "nama_barang", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Kode <br> Kelompok <br> Barang", field: "kode_kelompok_barang", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Kelompok <br> Barang", field: "kelompok_barang", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Kode Sub <br> Kelompok <br> Barang", field: "kode_sub_kelompok_barang", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Sub <br> Kelompok <br> Barang", field: "nama_sub_kelompok_barang", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "KM/HM", field: "km", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Jumlah", field: "jumlah", headerSort: false, width: 120, headerHozAlign: "center", },
			]
		}

		if (!data.length) {
			Object.assign(options, {
				minHeight: "20vh",
				placeholder: "No Data"
			})
		}

		this.table_history = new Tabulator(el, options);
	}

	initTablePembelianMaterial(el, data = []) {
		let options = {
			// layout: "fitDataStretch",
			selectable: true,
			data,
			columnHeaderVertAlign: "middle",
			maxHeight: "80vh",
			renderHorizontal: "virtual",
			columns: [
				{ title: "Kode Barang", field: "item_code", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Nama Barang", field: "item_name", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "No PO/SO", field: "no_po", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Tanggal", field: "tanggal_po", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Jumlah Dipesan", field: "qty", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Merk", field: "merk", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Negara Buatan", field: "country", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Spesifikasi <br> (Tipe/Model/ <br> Ukuran)", field: "description", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Mata Uang", field: "currency", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Harga Satuan", field: "rate", formatter: "money", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Total", field: "amount", formatter: "money", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Nama Supplier", field: "supplier_name", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "No. PR/SR", field: "material_request", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Keterangan", field: "keterangan", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Tanggal PR/SR", field: "tanggal_pr_sr", headerSort: false, width: 120, headerHozAlign: "center", },
			]
		}

		if (!data.length) {
			Object.assign(options, {
				minHeight: "20vh",
				placeholder: "No Data"
			})
		}

		this.table_history = new Tabulator(el, options);
	}

	initTablePemakaianBarang(el, data = [], month = []) {
		const month_column = month.map((row) => {
			return {
				title: row, field: row, headerSort: false, width: 120, headerHozAlign: "center", mutator: function (value) {
					return value || 0;
				}
			}
		})

		let options = {
			// layout: "fitDataStretch",
			selectable: true,
			data,
			columnHeaderVertAlign: "middle",
			maxHeight: "80vh",
			renderHorizontal: "virtual",
			columns: [
				{ title: "No", formatter: "rownum", headerSort: false, hozAlign: "center", headerHozAlign: "center", resizable: false, },
				{ title: "Kode Barang", field: "kode_barang", headerSort: false, width: 200, headerHozAlign: "center", },
				{ title: "Nama Barang", field: "nama_barang", headerSort: false, width: 200, headerHozAlign: "center", },
				{ title: "Bulan", headerSort: false, headerHozAlign: "center", columns: month_column },
				{ title: "Jumlah", field: "jumlah", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Harga", field: "harga", formatter: "money", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Total", field: "total", formatter: "money", headerSort: false, width: 120, headerHozAlign: "center", },
			]
		}

		if (!data.length) {
			Object.assign(options, {
				minHeight: "20vh",
				placeholder: "No Data"
			})
		}

		this.table_pemakaian_barang = new Tabulator(el, options);
	}

	initTablePurchaseRequest(el, data = []) {

		let options = {
			// layout: "fitDataStretch",
			selectable: true,
			data,
			columnHeaderVertAlign: "middle",
			maxHeight: "80vh",
			renderHorizontal: "virtual",
			columns: [
				{ title: "No", formatter: "rownum", headerSort: false, hozAlign: "center", headerHozAlign: "center", resizable: false, },
				{ title: "Tanggal", field: "tanggal", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "No. PO/SO", field: "no_po", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "No. PR/SR", field: "no_mr", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Kode Barang", field: "item_code", headerSort: false, width: 200, headerHozAlign: "center", },
				{ title: "Nama Barang", field: "item_name", headerSort: false, width: 200, headerHozAlign: "center", },
				{ title: "KM/HM", field: "km_hm", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Jumlah", field: "qty", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Harga", field: "rate", formatter: "money", headerSort: false, width: 120, headerHozAlign: "center", },
				{ title: "Total", field: "amount", formatter: "money", headerSort: false, width: 120, headerHozAlign: "center", },
			]
		}

		if (!data.length) {
			Object.assign(options, {
				minHeight: "20vh",
				placeholder: "No Data"
			})
		}

		this.table_pr_sr = new Tabulator(el, options);
	}

	getTableData() {
		const args = {
			pr_sr: this.pr_sr,
			item_name: this.item_name,
			list_sq: this.filter_sq
		}
		return new Promise((resolve, reject) => {
			frappe
				.xcall("sth.api.get_table_data", { args, freeze: true, freeze_message: "Fetching Data" })
				.then((res) => {
					resolve(res)
				})
		})

	}

	generateColumns() {
		const me = this
		let column_suppliers = this.suppliers.map((name) => {
			const initials = this.initials(name)
			return {
				title: name,
				headerHozAlign: "center",
				columns: [
					{ title: "Merek", field: `${initials}_merk`, headerSort: false, minWidth: 120, headerHozAlign: "center", },
					{ title: "Negara<br> Buatan", field: `${initials}_country`, headerSort: false, minWidth: 120, headerHozAlign: "center", },
					{ title: "Spesifikasi <br>(Tipe/Model/Ukuran)", field: `${initials}_spesifikasi`, headerSort: false, minWidth: 220, headerHozAlign: "center", formatter: "html" },
					{ title: "Jumlah", field: `${initials}_jumlah`, headerSort: false, headerHozAlign: "center", },
					{ title: "Harga", field: `${initials}_harga`, formatter: "money", headerSort: false, headerHozAlign: "center", },
					{ title: "Sub <br> Total", field: `${initials}_sub_total`, formatter: "money", headerSort: false, headerHozAlign: "center", },
					{
						title: "Document Number", field: `${initials}_doc_no`, headerSort: false, width: 200, headerHozAlign: "center", formatter: "link",
						formatterParams: {
							urlPrefix: "/app/supplier-quotation/",
							target: "_blank"
						}
					},
					{
						title: "",
						width: 60,
						formatter: function (cell, formatterParams) {
							const row = cell.getRow().getData()
							if (!row[`${initials}_child_name`] || row[`${initials}_workflow_state`] == "Draft") {
								return ""
							} else {
								return "<i class='fa fa-plus' style='color: #0b680b'></i>";
							}
						},
						headerSort: false, hozAlign: "center",
						cellClick: function (e, cell) {
							const row = cell.getRow().getData();
							if (row[`${initials}_child_name`] && row[`${initials}_workflow_state`] != "Draft") {
								me.validateSelectedData(row, initials)

								me.selected_suppliers = name
								me.selected_items.push({
									child_name: row[`${initials}_child_name`],
									item_name: row.mark,
								})
								frappe.show_alert({
									message: "Item has been selected",
									indicator: 'green'
								})
							}
						}
					}
				],
			}
		})

		let columns = [
			{ title: "No", field: "idx", formatter: "number", headerSort: false, headerHozAlign: "center", hozAlign: "center", resizable: false, frozen: true },
			{
				title: "Kode Barang", field: "kode_barang", headerSort: false, frozen: true, width: 100, headerHozAlign: "center",
				cellClick: function (e, cell) {
					const row = cell.getRow().getData();
					if (!row.kode_barang) return

					frappe.xcall("sth.procurement_sth.doctype.pengeluaran_barang.pengeluaran_barang.get_report_pemakaian_material",
						{ kode_barang: row.kode_barang })
						.then((res) => {
							me.showHistory(res, "out")
						})
				}
			},
			{
				title: "Nama Barang", field: "nama_barang", headerSort: false, frozen: true, width: 120, headerHozAlign: "center",
				cellClick: function (e, cell) {
					const row = cell.getRow().getData();
					if (!row.nama_barang) return

					frappe.xcall("sth.buying_sth.custom.purchase_order.get_history_purchase_item",
						{ nama_barang: row.nama_barang })
						.then((res) => {
							me.showHistory(res, "purchase")
						})
				}
			},
			{ title: "Satuan", field: "satuan", headerSort: false, frozen: true, headerHozAlign: "center", },
			{ title: "Harga <br> Terakhir", field: "harga_terakhir", formatter: "money", headerSort: false, frozen: true, width: 80, headerHozAlign: "center", },
			{ title: "Notes SQ", field: "notes_sq", headerSort: false, frozen: true, width: 100, headerHozAlign: "center", },
			{ title: "Notes PR/SR", field: "notes_pr_sr", headerSort: false, frozen: true, width: 100, headerHozAlign: "center", },
			{
				title: "Asset", field: "asset", headerSort: false, frozen: true, width: 100, headerHozAlign: "center",
				cellClick: async function (e, cell) {
					const row = cell.getRow().getData();
					if (!row.asset) return

					try {
						const pemakaian_barang = await frappe.xcall("sth.procurement_sth.doctype.pengeluaran_barang.pengeluaran_barang.history_pemakaian_barang", { asset: row.asset })
						const purchase_request = await frappe.xcall("sth.custom.material_request.get_history_purchase_request", { asset: row.asset })

						const data = {
							pemakaian_barang,
							purchase_request
						}

						me.showHistoryAsset(data)
					} catch (error) {
						console.error(error);

					}
				}
			},
			...column_suppliers
		]

		return columns
	}

	validateSelectedData(data, supplier) {
		let is_selected_before = this.selected_items.find(r => r.item_name == data.mark)

		// if (this.selected_suppliers && this.selected_suppliers != supplier) {
		// 	frappe.throw('Hanya diperbolehkan memilih penawaran dari 1 supplier')
		// }

		if (is_selected_before) {
			frappe.throw('Item sudah dipilih sebelumnya')
		} else if (data[`${supplier}_status`] == "Expired") {
			frappe.throw('Penawaran sudah expired, silahkan pilih penawaran lainnya')
		}
	}

	showSelectedItem(data = []) {
		var me = this
		let grand_total = 0

		data.forEach((row) => { grand_total += row.amount })

		this.dialog = new frappe.ui.Dialog({
			title: "Selected Items",
			size: "extra-large",
			fields: [
				{
					fieldname: "pr_sr",
					fieldtype: "Data",
					hidden: 1,
					default: me.pr_sr
				},

				{
					fieldname: "items",
					fieldtype: "Table",
					label: "Items",
					cannot_add_rows: true,
					in_place_edit: true,
					data,
					fields: [
						{
							fieldtype: "Data",
							fieldname: "item_code",
							hidden: 1
						},
						{
							fieldtype: "Data",
							fieldname: "item_name",
							label: "Kode Barang",
							in_list_view: 1,
							read_only: 1,
							columns: 1
						},
						{
							fieldtype: "Data",
							fieldname: "merek",
							label: "Merek",
							in_list_view: 1,
							read_only: 1,
							columns: 1
						},
						{
							fieldtype: "Data",
							fieldname: "country",
							label: "Negara Buatan",
							in_list_view: 1,
							read_only: 1,
							columns: 1
						},
						{
							fieldtype: "Data",
							fieldname: "description",
							label: "Spesifikasi",
							in_list_view: 1,
							read_only: 1,
							columns: 1
						},
						{
							fieldtype: "Float",
							fieldname: "qty",
							label: "Jumlah",
							in_list_view: 1,
							read_only: 1,
							columns: 1
						},
						{
							fieldtype: "Currency",
							fieldname: "rate",
							label: "Harga",
							in_list_view: 1,
							read_only: 1,
							columns: 2
						},
						{
							fieldtype: "Currency",
							fieldname: "amount",
							label: "Sub Total",
							in_list_view: 1,
							read_only: 1,
							columns: 2
						},
						{
							fieldname: "supplier",
							label: "Supplier",
							fieldtype: "Link",
							options: "Supplier",
							in_list_view: 1,
							read_only: 1,
							columns: 1
						},
						{
							fieldtype: "Data",
							fieldname: "doc_no",
							label: "Doc Number",
							hidden: 1,
						},
					]
				},

				{
					label: "Grand Total",
					fieldname: "grand_total",
					fieldtype: "Currency",
					read_only: 1,
					default: grand_total
				},
			],
			primary_action_label: "Approve",
			primary_action(values) {
				if (!values.items.length) {
					frappe.throw('Items tidak boleh kosong')
				}
				frappe.dom.freeze('Approving...')
				console.log(values);
				frappe.xcall("sth.api.comparasion_create_sq", { items: values.items, pr_sr: values.pr_sr }).then((res) => {
					frappe.show_alert({
						message: __(`Document successfully approved`),
						indicator: 'green'
					}, 5);
				}).finally(() => {
					frappe.dom.unfreeze()
				})

				me.dialog.hide();
			}
		})

		this.dialog.show()
		const delete_button = this.dialog.get_field('items').grid.remove_rows_button
		delete_button
			.off("click.myMarker")
			.on("click.myMarker", function () {
				const data = me.dialog.get_field('items').df.data.map((r) => r.item_code)
				me.selected_items = me.selected_items.filter((r) => data.includes(r))
			});
	}

	showHistory(data, type) {
		let func = null
		let title = ""
		if (type == "out") {
			title = "Pemakaian Material"
			func = this.initTablePamakaianMaterial.bind(this)
		} else if (type == "purchase") {
			title = "Pembelian Terakhir"
			func = this.initTablePembelianMaterial.bind(this)
		} else if (type == "asset") {

		}

		if (!func) {
			return
		}


		const d = new frappe.ui.Dialog({
			title: title,
			size: "extra-large",
			fields: [
				{
					fieldname: "data",
					fieldtype: "HTML"
				}
			]
		})


		const wrapper = d.get_field('data').$wrapper
		if (!wrapper.find("#table-history").length) {
			wrapper.append(
				`<div class='komparasion-style'>
					<div id="table-history"></div>
				</div>`
			)
		}

		if (this.table_history) {
			this.table_history.destroy()
		}

		func(wrapper.find('#table-history')[0], data)

		d.show()
	}

	showHistoryAsset(data) {
		let { details, data: res, month } = data.pemakaian_barang

		month = month.sort()

		const d = new frappe.ui.Dialog({
			title: "History Asset",
			size: "extra-large",
			fields: [
				{
					fieldname: "data",
					fieldtype: "HTML"
				}
			]
		})
		const wrapper = d.get_field('data').$wrapper
		if (!wrapper.find("#history-asset").length) {
			let grand_total = 0
			data.purchase_request.forEach((r) => grand_total += r.amount)
			grand_total = format_number(grand_total, null, 2)
			wrapper.append(frappe.render_template("template_history_asset", { ...details, periode: `${month[0]} s/d ${month[month.length - 1]}`, grand_total }))
		}

		if (this.table_pemakaian_barang) {
			this.table_pemakaian_barang.destroy()
		}

		this.initTablePemakaianBarang(wrapper.find('#table-pemakaian-barang')[0], res, month)
		this.initTablePurchaseRequest(wrapper.find('#table-purchase-request')[0], data.purchase_request)
		d.show()
	}

	initials(text) {
		return text
			?.trim()
			.split(/\s+/)
			.map(w => w[0].toLowerCase())
			.join("") || "";
	}

	setTableEvent() {
		this.table.on("rowSelectionChanged", function (data, rows) {
			console.log(data, rows);
		});
	}

	refresh_table() {
		var me = this
		this.getTableData().then((res) => {
			console.log(res);

			this.data = res.data
			this.suppliers = res.suppliers
			const columns = this.generateColumns()

			this.table.setColumns(columns);
			this.table.setData(res.data)
			this.table.redraw(true);
			me.refresh_view()
		})
	}

	refresh_view() {
		if (!this.data.length) {
			$("#table-comparasion").css({
				"visibility": "hidden"
			})
		} else {
			$("#table-comparasion").css({
				"visibility": "visible"
			})
		}
	}

	approve_sq() {
		if (!this.supllier_quotation) {
			return
		}
		frappe.xcall("sth.api.submit_sq", { "name": this.supllier_quotation, freeze: true, freeze_message: "Approving" })
			.then(() => {
				frappe.show_alert({
					message: __(`Document ${this.supllier_quotation} successfully approved`),
					indicator: 'green'
				}, 5);
				this.page.fields_dict.sq.set_value('')
			})
			.catch((e) => {
				console.error(e);

			})
	}

}