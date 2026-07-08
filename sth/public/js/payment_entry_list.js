console.log("PAYMENT REPORT VIEW JS LOADED");

let payment_btn_timer = null;

frappe.router.on("change", () => {

	console.log("ROUTE", frappe.get_route());

	clearTimeout(payment_btn_timer);

	const route = frappe.get_route();

	if (
		route[0] !== "List" ||
		route[1] !== "Payment Entry"
	) {
		$(".edit-payment-btn").remove();
		$(".preview-payment-btn").remove();
		return;
	}

	payment_btn_timer = setTimeout(() => {

		$(".edit-payment-btn").remove();
		$(".preview-payment-btn").remove();

		add_payment_button();

	}, 1000);

});

// let payment_btn_timer = null;


// frappe.router.on("change", () => {

// 	clearTimeout(payment_btn_timer);


// 	if (
// 		frappe.get_route()[0] !== "List" ||
// 		frappe.get_route()[1] !== "Payment Entry"
// 	) {
// 		return;
// 	}


// 	payment_btn_timer = setTimeout(() => {

// 		add_payment_button();

// 	},1000);

// });


function add_payment_button() {

	console.log("ADD BUTTON");
	console.log("ROUTE =", frappe.get_route());
	console.log("CUR LIST =", cur_list);
	console.log("PAGE ACTION =", $(".page-actions")[0]);

	$(".edit-payment-btn").remove();
	$(".preview-payment-btn").remove();

	if (
		frappe.get_route()[0] !== "List" ||
		frappe.get_route()[1] !== "Payment Entry"
	) {
		return;
	}


	if (!$(".edit-payment-btn").length) {

		let edit_btn = $(`
			<button class="btn btn-primary btn-sm edit-payment-btn">
				Unggah Bukti Pembayaran
			</button>
		`);


		// edit_btn.on("click", function () {
		// 	edit_payment_dialog();
		// });

		edit_btn.on("click", async function () {

			let pe = get_selected_payment();

			if(!pe) return;


			let doc = await frappe.db.get_value(
				"Payment Entry",
				pe,
				"docstatus"
			);


			if(doc.message.docstatus != 1){

				frappe.msgprint({
					title: __("Not Allowed"),
					message: __("Payment Entry must be Submitted before uploading payment proof."),
					indicator: "red"
				});

				return;
			}


			edit_payment_dialog(pe);

		});


		$(".page-actions").prepend(edit_btn);

	}



	if (!$(".preview-payment-btn").length) {


		let preview_btn = $(`
			<button class="btn btn-secondary btn-sm preview-payment-btn">
				Preview
			</button>
		`);


		preview_btn.on("click", function () {

			let pe = get_selected_payment();

			if(!pe) return;


			preview_payment_dialog(pe);

		});


		$(".page-actions").prepend(preview_btn);

	}

}




function edit_payment_dialog(default_pe) {


	let d = new frappe.ui.Dialog({

		title: __("Unggah Bukti Pembayaran"),

		fields: [

			{
				label: "Payment Entry",
				fieldname: "payment_entry",
				fieldtype: "Link",
				options: "Payment Entry",
				reqd: 1,

				change: async function () {

					let name =
						d.get_value("payment_entry");


					if (!name) return;


					let r =
						await frappe.db.get_value(
							"Payment Entry",
							name,
							[
								"nomor_referensi_bayar",
								"tanggal_bayar",
								"bukti_pembayaran"
							]
						);


					d.set_value(
						"nomor_referensi_bayar",
						r.message.nomor_referensi_bayar
					);


					d.set_value(
						"tanggal_bayar",
						r.message.tanggal_bayar
					);


					d.set_value(
						"bukti_pembayaran",
						r.message.bukti_pembayaran
					);


				}

			},


			{
				label:"Nomor Referensi Bayar",
				fieldname:"nomor_referensi_bayar",
				fieldtype:"Data",
				reqd:1
			},


			{
				label:"Tanggal Bayar",
				fieldname:"tanggal_bayar",
				fieldtype:"Date",
				reqd:1
			},
			{
				label:"Bukti Pembayaran",
				fieldname:"bukti_pembayaran",
				fieldtype:"Attach",
				options: {
					allowed_file_types: [
						"image/*",
						"application/pdf"
					]
				}
			}


		],


		primary_action(values) {


			frappe.call({

				method:
				"sth.custom.payment_entry.update_payment_reference",


				args: values,


				callback(r){

					if(!r.exc){

						frappe.msgprint(
							__("Updated")
						);


						d.hide();

						// location.reload();

					}

				}

			});


		}

	});


	d.show();

	if(default_pe){

		d.set_value(
			"payment_entry",
			default_pe
		);

		d.fields_dict.payment_entry.df.onchange();

	}
}

async function preview_payment_dialog(default_pe) {


	let d = new frappe.ui.Dialog({

		title: __("Preview Payment Document"),

		fields: [

			{
				label: "Payment Entry",
				fieldname: "payment_entry",
				fieldtype: "Link",
				options: "Payment Entry",
				reqd: 1,

				change: function(){

					let name =
						d.get_value("payment_entry");

					if(name){
						load_payment_preview(name,d);
					}

				}
			},


			{
				fieldname:"preview_html",
				fieldtype:"HTML"
			}

		]

	});


	d.show();

	if(default_pe){

		d.set_value(
			"payment_entry",
			default_pe
		);


		load_payment_preview(
			default_pe,
			d
		);

	}

}

async function load_payment_preview(name,d){


	let html = `
	<div style="padding:10px">
		Loading...
	</div>
	`;

	d.fields_dict.preview_html.$wrapper.html(html);



	let output = "";

	// ============================
	// Bukti Pembayaran
	// ============================


	let pe =
		await frappe.db.get_value(
			"Payment Entry",
			name,
			"bukti_pembayaran"
		);



	let bukti_html = "";


	if(pe.message.bukti_pembayaran){


		bukti_html = `

		<a href="${pe.message.bukti_pembayaran}"
		target="_blank"
		style="
			display:inline-flex;
			align-items:center;
			gap:5px;
			background:#EBF3FF;
			border:1px solid #B8D4FF;
			border-radius:4px;
			color:#1a73e8;
			font-size:12px;
			padding:4px 10px;
			text-decoration:none;
		">

		📄 View File

		</a>

		`;


	} else {


		bukti_html = `

		<div style="
			background:#f8f9fa;
			border:1px dashed #dee2e6;
			border-radius:6px;
			padding:12px 16px;
			color:#8D99AE;
			font-size:12px;
		">

			No files uploaded yet.

		</div>

		`;

	}



	output += `

	<div style="margin:10px 0 15px;">


		<div style="
			font-size:12px;
			font-weight:600;
			color:#555;
			text-transform:uppercase;
			margin-bottom:8px;
		">

			Bukti Pembayaran

		</div>


		<div style="
			border:1px solid #e4e4e4;
			border-radius:6px;
			padding:12px;
			background:#fff;
		">

			${bukti_html}

		</div>


	</div>

	`;

	// ============================
	// Print PDF
	// ============================

	output += `

	<div style="margin:10px 0 15px;">

		<div style="
			font-size:12px;
			font-weight:600;
			color:#555;
			text-transform:uppercase;
			margin-bottom:8px;
		">
			Print Preview
		</div>


		<div style="
			border:1px solid #e4e4e4;
			border-radius:6px;
			padding:12px;
			background:#fff;
		">

			<a href="/api/method/frappe.utils.print_format.download_pdf?doctype=Payment%20Entry&name=${name}&format=PF%20PV%20KAS&no_letterhead=1&letterhead=No%20Letterhead&settings=%7B%7D&_lang=en"
			target="_blank"
			style="
				display:inline-flex;
				align-items:center;
				gap:5px;
				background:#EBF3FF;
				border:1px solid #B8D4FF;
				border-radius:4px;
				color:#1a73e8;
				font-size:12px;
				padding:4px 10px;
				text-decoration:none;
			">
				🖨️ Open PDF
			</a>

		</div>

	</div>

	`;


	// ============================
	// Kriteria Upload Document
	// ============================

	let docs = await frappe.db.get_list(
		"Kriteria Upload Document",
		{
			filters:{
				voucher_type:"Payment Entry",
				voucher_no:name
			},
			fields:["name"],
			limit:1
		}
	);



	let doc_rows = [];


	if(docs.length){

		let doc =
			await frappe.db.get_doc(
				"Kriteria Upload Document",
				docs[0].name
			);

		doc_rows = doc.file_upload || [];

	}


	output += build_preview_table(
		"Kriteria Dokumen PV",
		doc_rows,
		"upload_file"
	);





	// ============================
	// Kriteria Upload Payment
	// ============================

	let payments = await frappe.db.get_list(
		"Kriteria Upload Payment",
		{
			filters:{
				voucher_type:"Payment Entry",
				voucher_no:name
			},
			fields:["name"],
			limit:1
		}
	);



	let payment_rows = [];


	if(payments.length){

		let doc =
			await frappe.db.get_doc(
				"Kriteria Upload Payment",
				payments[0].name
			);

		payment_rows = doc.file_upload || [];

	}


	output += build_preview_table(
		"Kriteria Dokumen Lainnya",
		payment_rows,
		"uploaded_file"
	);


    if (!output) {

        output = `
        <div style="padding:15px;color:#888">
            No document found
        </div>
        `;

    }

	d.fields_dict.preview_html.$wrapper.html(output);

}

function build_preview_table(title, rows, file_field) {


	if(!rows || !rows.length){

		return `

		<div style="margin:10px 0 15px;">

			<div style="
				font-size:12px;
				font-weight:600;
				color:#555;
				text-transform:uppercase;
				margin-bottom:8px;
			">
				${title}
			</div>


			<div style="
				background:#f8f9fa;
				border:1px dashed #dee2e6;
				border-radius:6px;
				padding:12px 16px;
				color:#8D99AE;
				font-size:12px;
			">
				No files uploaded yet.
			</div>

		</div>

		`;

	}


	let rows_html = "";


	rows.forEach((r,i)=>{


		let file = r[file_field];


		if(!file) return;



		rows_html += `

		<tr style="border-bottom:1px solid #f0f0f0;">

			<td style="
				padding:10px 12px;
				color:#aaa;
				font-size:12px;
				width:36px;
			">
				${i+1}
			</td>


			<td style="
				padding:10px 12px;
				font-size:12px;
				color:#555;
			">
				${frappe.utils.escape_html(
					r.rincian_dokumen_finance || "-"
				)}
			</td>


			<td style="padding:10px 12px;">


				<a href="${file}"
				   target="_blank"
				   style="
					display:inline-flex;
					align-items:center;
					gap:5px;
					background:#EBF3FF;
					border:1px solid #B8D4FF;
					border-radius:4px;
					color:#1a73e8;
					font-size:12px;
					padding:4px 10px;
					text-decoration:none;
					font-weight:500;
				   ">

				   📄 View File

				</a>


			</td>


		</tr>

		`;

	});



return `

<div style="margin:10px 0 15px;">


	<div style="
		font-size:12px;
		font-weight:600;
		color:#555;
		text-transform:uppercase;
		margin-bottom:8px;
	">
		${title}
	</div>



	<div style="
		border:1px solid #e4e4e4;
		border-radius:6px;
		overflow:hidden;
		background:#fff;
	">


	<table style="
		width:100%;
		border-collapse:collapse;
	">


	<thead>

	<tr style="
		background:#f8f9fa;
		border-bottom:1px solid #e4e4e4;
	">


	<th style="
		padding:9px 12px;
		text-align:left;
		font-size:11px;
		color:#888;
		width:36px;
	">
		#
	</th>


	<th style="
		padding:9px 12px;
		text-align:left;
		font-size:11px;
		color:#888;
	">
		Dokumen
	</th>


	<th style="
		padding:9px 12px;
		text-align:left;
		font-size:11px;
		color:#888;
		width:110px;
	">
		File
	</th>


	</tr>

	</thead>


	<tbody>

	${rows_html}

	</tbody>


	</table>


	</div>


</div>

`;

}

function get_selected_payment(){

	let checked = cur_list.get_checked_items();


	if(!checked.length){

		frappe.msgprint(
			__("Please select one Payment Voucher")
		);

		return null;
	}


	if(checked.length > 1){

		frappe.msgprint(
			__("Please select only one Payment Voucher")
		);

		return null;
	}


	return checked[0].name;

}