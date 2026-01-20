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
			fieldname: "rfq",
			options: "Request for Quotation",
			label: __("RFQ Number"),
			get_query: function () {
				return {
					filters: {
						"company": me.company,
						"custom_offering_status": "Open"
					}
				};
			},
			change: function () {
				me.rfq = this.value
				me.refresh_table()
			},
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

		this.page.page_form.append(this.btn_approve)

		this.sq_field.$wrapper.css({
			"margin-left": "auto"
		})

		this.btn_approve.css({
			"align-self": "center"
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
		return new Promise((resolve, reject) => {
			frappe
				.xcall("sth.api.get_table_data", { rfq: this.rfq || "", freeze: true, freeze_message: "Fetching Data" })
				.then((res) => {
					resolve(res)
				})
		})
	}

	generateColumns() {
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