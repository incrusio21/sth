frappe.pages['ess'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'ESS',
		single_column: true
	});

	wrapper.ess_page = page;

	frappe.ess_page.setup(wrapper);
}

function getAge(birthDateStr) {
	const birthDate = new Date(birthDateStr);
	const today = new Date();
	let age = today.getFullYear() - birthDate.getFullYear();
	const m = today.getMonth() - birthDate.getMonth();
	if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
		age--;
	}
	return age;
}

frappe.ess_page = {
	setup: async function (wrapper) {
		let page = wrapper.ess_page;
		const emp_list = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Employee",
				filters: { user_id: frappe.session.user }
			}
		});

		if (!emp_list.message[0]) {
			$(page.body).html(`<h4 class="text-center">Silahkan lengkapi data employee dan users</h4>`);
			return;
		}

		const res = await frappe.call({
			method: "sth.overrides.ess.get_employee_dashboard_data",
			args: {
				employee: emp_list.message[0].name,
			},
		});
		const data = res.message;

		const emp_doc = data.employee;
		const atasan = data.atasan;
		const exit_interview = data.exit_interview;
		const kpi_values = data.kpi_values;
		const grievances = data.grievances;
		const leaves = data.leave_details.leave_allocation;

		// const emp_list = await frappe.call({
		// 	method: "frappe.client.get_list",
		// 	args: {
		// 		doctype: "Employee",
		// 		filters: { user_id: frappe.session.user }
		// 	}
		// });

		// if (!emp_list.message[0]) {
		// 	$(page.body).html(`<h4 class="text-center">Silahkan lengkapi data employee dan users</h4>`);
		// 	return;
		// }

		// const emp_doc = await frappe.call({
		// 	method: "frappe.client.get",
		// 	args: {
		// 		doctype: "Employee",
		// 		name: emp_list.message[0].name
		// 	}
		// });
		// // const atasan = await frappe.call({
		// // 	method: "sth.overrides.ess.get_employee",
		// // 	args: {
		// // 		employee: emp_doc.message.reports_to,
		// // 	},
		// // });
		// const exit_interview = await frappe.call({
		// 	method: "sth.overrides.ess.get_exit_interview_unrestricted",
		// 	args: {
		// 		employee: emp_list.message[0].name,
		// 	},
		// });
		// const leaves = await frappe.call({
		// 	method: "hrms.hr.doctype.leave_application.leave_application.get_leave_details",
		// 	args: {
		// 		employee: emp_list.message[0].name,
		// 		date: new Date().toISOString().split("T")[0]
		// 	},
		// });
		// const kpi_values = await frappe.call({
		// 	method: "sth.overrides.ess.get_kpi_values",
		// 	args: {
		// 		employee: emp_list.message[0].name,
		// 		date: new Date().toISOString().split("T")[0]
		// 	},
		// });
		// const grievances = await frappe.call({
		// 	method: "sth.overrides.ess.get_employee_grievance",
		// 	args: {
		// 		employee: emp_list.message[0].name,
		// 	},
		// });

		const { name, no_ktp, employee_name, company, designation, date_of_joining, date_of_birth, current_address, custom_nomor_kartu_keluarga, custom_no_bpjs_ketenagakerjaan, custom_no_bpjs_kesehatan, npwp, cell_number, emergency_phone_number, personal_email, image, department, reports_to, bio } = emp_doc;
		const { custom_upload_file_document, interview_summary } = exit_interview;
		let tableCuti = ``;
		let tableKpi = ``;
		let tableGrievance = ``;

		for (const key in leaves) {
			const data = leaves[key];
			tableCuti += `
			<tr>
				<td>${key}</td>
				<td class="text-center">${data.total_leaves}</td>
				<td class="text-center">${data.leaves_taken}</td>
				<td class="text-center">${data.remaining_leaves}</td>
			</tr>
			`;
		}
		for (const key in kpi_values) {
			const data = kpi_values[key]
			tableKpi += `
				<tr>
					<td>${data.year}</td>
					<td class="text-center">${data.kpi_value}</td>
				</tr>
			`;
		}
		for (const key in grievances) {
			const data = grievances[key]
			tableGrievance += `
				<tr>
					<td>${data.tipe}</td>
					<td class="text-center">${data.from}</td>
					<td class="text-center">${data.until}</td>
				</tr>
			`;
		}

		$(page.body).html(`
				<h4>1. BASIS INFORMASI</h4>
				<div class="container-fluid px-0">
					<div class="row">
						<div class="col-5 ps-0">
							<table>
								<tr>
									<td>No Induk Karyawan</td>
									<td>:</td>
									<td>${name ?? '-'}</td>
								</tr>
								<tr>
									<td>Nama</td>
									<td>:</td>
									<td>${employee_name ?? '-'}</td>
								</tr>
								<tr>
									<td>Perusahaan</td>
									<td>:</td>
									<td>${company ?? '-'}</td>
								</tr>
								<tr>
									<td>Jabatan</td>
									<td>:</td>
									<td>${designation ?? '-'}</td>
								</tr>
								<tr>
									<td>Tanggal Masuk</td>
									<td>:</td>
									<td>${date_of_joining ?? '-'}</td>
								</tr>
								<tr>
									<td>Tanggal Lahir</td>
									<td>:</td>
									<td>${date_of_birth ?? '-'}</td>
								</tr>
								<tr>
									<td>Usia</td>
									<td>:</td>
									<td>${date_of_birth ? getAge(date_of_birth) : '-'}</td>
								</tr>
								<tr>
									<td>Alamat</td>
									<td>:</td>
									<td>${current_address ?? '-'}</td>
								</tr>
							</table>
						</div>
						<div class="col-5">
							<table>
								<tr>
									<td>No. KTP</td>
									<td>:</td>
									<td>${no_ktp ?? '-'}</td>
								</tr>
								<tr>
									<td>No. KK</td>
									<td>:</td>
									<td>${custom_nomor_kartu_keluarga ?? '-'}</td>
								</tr>
								<tr>
									<td>BPJS Ketenagakerjaan</td>
									<td>:</td>
									<td>${custom_no_bpjs_ketenagakerjaan ?? '-'}</td>
								</tr>
								<tr>
									<td>BPJS Kesehatan</td>
									<td>:</td>
									<td>${custom_no_bpjs_kesehatan ?? '-'}</td>
								</tr>
								<tr>
									<td>NPWP</td>
									<td>:</td>
									<td>${npwp ?? '-'}</td>
								</tr>
								<tr>
									<td>No. HP</td>
									<td>:</td>
									<td>${cell_number ?? '-'}</td>
								</tr>
								<tr>
									<td>HP Keluarga</td>
									<td>:</td>
									<td>${emergency_phone_number ?? '-'}</td>
								</tr>
								<tr>
									<td>Email</td>
									<td>:</td>
									<td>${personal_email ?? '-'}</td>
								</tr>
							</table>
						</div>
						<div class="col-2">
							${image ? `<img src="${image}" class="img-fluid">` : ''}
						</div>
					</div >
				</div >
				<h4 class="mt-5">2. STRUKTUR ORGANISASI</h4>
				<div class="container-fluid px-0">
					<div class="row">
						<div class="col-5 ps-0">
							<table>
								<tr>
									<td>Departement</td>
									<td>:</td>
									<td>${department ?? '-'}</td>
								</tr>
								<tr>
									<td>Atasan</td>
									<td>:</td>
									<td>${atasan?.employee_name ?? '-'}</td>
								</tr>
								<tr>
									<td>Jobdes</td>
									<td>:</td>
									<td>${bio ?? '-'}</td>
								</tr>
							</table>
						</div>
					</div>
				</div>
				<h4 class="mt-5">3. KPI</h4>
				<div class="container-fluid px-0">
					<div class="row">
						<div class="col-5 ps-0">
							<table>
								<tr>
									<td>Nilai Kinerja</td>
									<td>:</td>
									<td>
										<table border="1">
											<tr>
												<th>Tahun</th>
												<th>KPI Value</th>
											</tr>
											${tableKpi}
										</table>
									</td>
								</tr>
								<tr>
									<td>Surat Teguran/Peringatan</td>
									<td>:</td>
									<td>
										<table border="1">
											<tr>
												<th>Tipe</th>
												<th>Masa berlaku Dari</th>
												<th>Masa berlaku Sampai</th>
											</tr>
											${tableGrievance}
										</table>
									</td>
								</tr>
							</table>
						</div>
					</div>
				</div>
				<h4 class="mt-5">4. Cuti</h4>
				<div class="container-fluid px-0">
					<div class="row">
						<div class="col-5 ps-0">
							<table border="1">
								<tr>
									<th>Tipe Cuti</th>
									<th>Hak Cuti</th>
									<th>Cuti Terpakai</th>
									<th>Sisa Cuti</th>
								</tr>
								${tableCuti}
							</table>
						</div>
					</div>
				</div>
				<h4 class="mt-5">5. EXIT INTERVIEW</h4>
				<div class="container-fluid px-0">
					<div class="row">
						<div class="col-5 ps-0">
							<table>
								<tr>
									<td>Upload Surat Pengunduran Diri</td>
									<td>:</td>
									<td>
									${custom_upload_file_document ? `<a href="${custom_upload_file_document}" class="underline" target="_blank">${custom_upload_file_document}</a>` : '-'}
									</td>
								</tr>
								<tr>
									<td>Exit Interview di isi ybs/HR</td>
									<td>:</td>
									<td>${interview_summary ?? '-'}</td>
								</tr>
							</table>
						</div>
					</div>
				</div>
		`);

		// // Tambahkan tombol
		page.add_action_item("Export PDF", () => {
			frappe.msgprint("Export PDF");
		});
	}
};