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

		// console.log(this.page);
		this.content_wrapper = $(`
			<div id="supplier-comparasion">
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
							company: me.company
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
						"workflow_state": "Open"
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
			frappe.xcall("sth.api.get_sq_item_details", { names: [...new Set(this.selected_items)] }).then((res) => {
				me.showDialog(res)
			})
		}, {
			btn_class: "btn-default"
		})
		this.page.page_form.append(this.btn_approve)
		this.page.page_form.append(this.btn_chosen_items)

		this.sq_field.$wrapper.css({
			"margin-left": "auto"
		})

		this.btn_approve.css({
			"align-self": "center"
		})

		this.btn_chosen_items.css({
			"align-self": "center",
			"margin-left": "10px"
		})

	}

	async initTable() {
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
					{ title: "Merek", field: `${initials}_merk`, headerSort: false, headerHozAlign: "center", },
					{ title: "Negara<br> Buatan", field: `${initials}_country`, headerSort: false, headerHozAlign: "center", },
					{ title: "Spesifikasi <br>(Tipe/Model/Ukuran)", field: `${initials}_spesifikasi`, headerSort: false, headerHozAlign: "center", },
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
							if (!row[`${initials}_child_name`]) {
								return ""
							} else {
								return "<i class='fa fa-plus' style='color: #0b680b'></i>";
							}
						},
						headerSort: false, hozAlign: "center",
						cellClick: function name(e, cell) {
							const row = cell.getRow().getData();
							if (row[`${initials}_child_name`]) {
								me.selected_items.push(row[`${initials}_child_name`])
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
			{ title: "Kode Barang", field: "kode_barang", headerSort: false, frozen: true, width: 100, headerHozAlign: "center", },
			{ title: "Nama Barang", field: "nama_barang", headerSort: false, frozen: true, width: 120, headerHozAlign: "center", },
			{ title: "Satuan", field: "satuan", headerSort: false, frozen: true, headerHozAlign: "center", },
			{ title: "Harga <br> Terakhir", field: "harga_terakhir", formatter: "money", headerSort: false, frozen: true, width: 80, headerHozAlign: "center", },
			...column_suppliers
		]

		return columns
	}

	showDialog(data = []) {
		var me = this
		this.dialog = new frappe.ui.Dialog({
			title: "Selected Items",
			size: "extra-large",
			fields: [
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
							fieldname: "item_name",
							label: "Kode Barang",
							in_list_view: 1,
							read_only: 1,
							columns: 2
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
							columns: 2
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
							columns: 1
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
							fieldtype: "Data",
							fieldname: "supplier",
							label: "Supplier",
							hidden: 1,
						},
					]
				}
			],
			primary_action_label: "Create SQ",
			primary_action(values) {
				if (!values.items.length) {
					frappe.throw('Items tidak boleh kosong')
				}
				console.log(values.items);
				me.dialog.hide();
			}
		})

		this.dialog.show()
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