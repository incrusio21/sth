frappe.pages['ess'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'ESS',
		single_column: true
	});

	wrapper.ess_page = page;

	frappe.ess_page.setup(wrapper);
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
		const emp_doc = await frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Employee",
				name: emp_list.message[0].name
			}
		});

		const { no_ktp, employee_name, company, designation, date_of_joining, date_of_birth, current_address, custom_nomor_kartu_keluarga, custom_no_bpjs_ketenagakerjaan, custom_no_bpjs_kesehatan, npwp, cell_number, personal_email, image } = emp_doc.message;

		$(page.body).html(`
			<h3>Basis Informasi (Data Pribadi & Kepegawaian)</h3>
			<table>
				<tr>
					<td>No Induk Karyawan</td>
					<td>:</td>
					<td>${no_ktp ?? '-'}</td>
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
					<td></td>
				</tr>
				<tr>
					<td>Alamat</td>
					<td>:</td>
					<td>${current_address ?? '-'}</td>
				</tr>
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
					<td></td>
				</tr>
				<tr>
					<td>Email</td>
					<td>:</td>
					<td>${personal_email ?? '-'}</td>
				</tr>
				<tr>
					<td>Foto</td>
					<td>:</td>
					<td>
						<img src="${image}" width="150"/>
					</td>
				</tr>
			</table>
		`);

		// // Tambahkan tombol
		// page.add_action_item('Create Leave Application', () => {
		// 	frappe.new_doc('Leave Application');
		// });

		// page.add_action_item('Create Expense Claim', () => {
		// 	frappe.new_doc('Expense Claim');
		// });
	}
};