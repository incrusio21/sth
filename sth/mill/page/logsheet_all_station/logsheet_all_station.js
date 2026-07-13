frappe.pages['logsheet-all-station'].on_page_load = function (wrapper) {

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Logsheet All Station",
		single_column: true
	});

	page.main.html(`
		<div id="export-wrapper">
			<div id="sterillizer-table" style="margin-bottom: 1rem"></div>
			<div id="press-table"></div>
		</div>
	`);

	let sterillizer_table = init_sterillizer_table();
	let press_table = init_press_table();

	page.add_action_item(__("Export Excel"), () => {
		let wb = XLSX.utils.book_new();
		let ws1 = XLSX.utils.json_to_sheet(
			sterillizer_table.getData()
		);

		XLSX.utils.book_append_sheet(
			wb,
			ws1,
			"Sterilizer"
		);

		let ws2 = XLSX.utils.json_to_sheet(
			press_table.getData()
		);

		XLSX.utils.book_append_sheet(
			wb,
			ws2,
			"Screw Press"
		);
		XLSX.writeFile(
			wb,
			"Logsheet All Station.xlsx"
		);
	});

	page.add_action_item(__("Export PDF"), () => {
		html2pdf()
			.set({
				margin: 10,
				filename: "Logsheet All Station.pdf",
				image: {
					type: "jpeg",
					quality: 1
				},
				html2canvas: {
					scale: 1
				},
				jsPDF: {
					unit: "mm",
					format: "a3",
					orientation: "landscape"
				}
			})
			.from(
				document.getElementById("export-wrapper")
			)
			.save();
	});
}

//========================================================
// TABLE STERILLIZER
//========================================================
function init_sterillizer_table() {
	let data = [
		{
			sterilizer: "Sterilizer 1",
			masuk: "08:00",
			keluar: "08:30",
			total_waktu: 30,
			waktu_perebusan: 20,
			opr: "",
			asisten: "",
			manager: "",
			keterangan: ""
		}
	];

	return new Tabulator("#sterillizer-table", {
		layout: "fitColumns",
		data: data,
		columnHeaderVertAlign: "middle",
		columns: [
			{
				title: "STERILIZER",
				field: "sterilizer",
				width: 150,
				headerHozAlign: "center",
				hozAlign: "center"
			},
			{
				title: "JAM",
				headerHozAlign: "center",
				columns: [
					{
						title: "MASUK",
						field: "masuk",
						width: 110,
						hozAlign: "center"
					},
					{
						title: "KELUAR",
						field: "keluar",
						width: 110,
						hozAlign: "center"
					}
				]
			},
			{
				title: "TOTAL WAKTU",
				field: "total_waktu",
				width: 120,
				headerHozAlign: "center",
				hozAlign: "center"
			},
			{
				title: "WAKTU PEREBUSAN (menit)",
				field: "waktu_perebusan",
				width: 170,
				headerHozAlign: "center",
				hozAlign: "center"
			},
			{
				title: "PARAF",
				headerHozAlign: "center",
				columns: [
					{
						title: "OPR",
						field: "opr",
						width: 120,
						hozAlign: "center"
					},
					{
						title: "ASISTEN",
						field: "asisten",
						width: 120,
						hozAlign: "center"
					},
					{
						title: "MANAGER",
						field: "manager",
						width: 120,
						hozAlign: "center"
					}
				]
			},
			{
				title: "KETERANGAN",
				field: "keterangan",
				widthGrow: 2
			}
		]
	});
}

//========================================================
// TABLE PRESS
//========================================================
function init_press_table() {
	let data = [
		{
			time: "08:00",

			sp1_amp: "",
			sp1_cone: "",

			sp2_amp: "",
			sp2_cone: "",

			sp3_amp: "",
			sp3_cone: "",

			sp4_amp: "",
			sp4_cone: "",

			opr: "",
			asisten: "",
			manager: ""
		}
	];

	function screwPressGroup(no) {
		return {
			title: `SCREW PRESS ${no}`,
			headerHozAlign: "center",
			columns: [
				{
					title: "AMP",
					field: `sp${no}_amp`,
					width: 100,
					hozAlign: "center"
				},
				{
					title: "CONE",
					field: `sp${no}_cone`,
					width: 100,
					hozAlign: "center"
				}
			]
		};
	}

	return new Tabulator("#press-table", {
		layout: "fitColumns",
		data: data,
		columnHeaderVertAlign: "middle",
		columns: [
			{
				title: "TIME",
				field: "time",
				width: 100,
				hozAlign: "center"
			},

			screwPressGroup(1),
			screwPressGroup(2),
			screwPressGroup(3),
			screwPressGroup(4),

			{
				title: "PARAF",
				headerHozAlign: "center",
				columns: [
					{
						title: "OPR",
						field: "opr",
						width: 120
					},
					{
						title: "ASISTEN",
						field: "asisten",
						width: 120
					},
					{
						title: "MANAGER",
						field: "manager",
						width: 120
					}
				]
			}
		]
	});
}