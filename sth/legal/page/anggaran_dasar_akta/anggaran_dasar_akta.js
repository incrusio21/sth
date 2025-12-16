// Copyright (c) 2025, DAS and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("sth.legal")

frappe.pages['anggaran-dasar-akta'].on_page_load = function(wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Aggaran Dasar Akta',
		single_column: true
	});

	wrapper.anggaran_dasar = new sth.legal.AnggaranDasarAkta(page);
}

sth.legal.AnggaranDasarAkta = class AnggaranDasarAkta {
	constructor(page) {
		var me = this;
		this.page = page
		
		// 0 setTimeout hack - this gives time for canvas to get width and height
		setTimeout(function () {
			me.setup();
			me.get_data();
		}, 0);
	}

	setup() {
		var me = this;
		
		this.company = frappe.defaults.get_user_default("company");
		
		this.company_field = this.page.add_field({
			fieldtype: "Link",
			fieldname: "company",
			options: "Company",
			label: __("Company"),
			reqd: 1,
			default: this.company,
			change: function () {
				me.company = this.value
				me.get_data();
			},
		})

		this.anggaran_field = this.page.add_field({
			fieldtype: "Link",
			fieldname: "anggaran_dasar",
			options: "Anggaran Dasar",
			label: __("Anggaran Dasar"),
			reqd: 1,
			get_query: function() {
				return {
					filters: {
						"company": me.company
					}
				};
			},
			change: function () {
				me.anggaran_dasar = this.value || "";
				me.get_data();
			},
		})

		this.options = {}
		this.$layout_akta = $(this.layout_div()).hide().appendTo(this.page.main);
		this.$loading = $(this.message_div("")).hide().appendTo(this.page.main);
		this.$message = $(this.message_div("")).hide().appendTo(this.page.main);
		
		// bind refresh
		this.set_default_secondary_action()
	}

	set_default_secondary_action() {
		let me = this
		this.refresh_button && this.refresh_button.remove();
		this.refresh_button = this.page.add_action_icon(
			"es-line-reload",
			() => {
				me.get_data();
				// this.refresh();
			},
			"",
			__("Reload Report")
		);
	}

	get_data(btn) {
		let me = this;
		
		frappe.call({
			method: "sth.legal.page.anggaran_dasar_akta.anggaran_dasar_akta.get_anggaran_dasar_akta",
			args: {
				company: this.company,
				anggaran_dasar: this.anggaran_dasar || "",
			},
			btn: btn,
			callback: function (r) {
				if (!r.exc) {
					me.options.data = r.message;
					if (!me.options.data) {
						me.$message.find("div").html(me.get_no_result_message());
						me.$message.show();
						return;
					}else{
						me.$message.hide();
					}

					me.render()
				}
			},
		});		
	}

	render() {
		let me = this;
		me.render_table_header();
		me.render_table_data()
		this.$layout_akta.show();
	}

	get_no_result_message() {
		return `<div class="msg-box no-border">
			<div>
				<img src="/assets/frappe/images/ui-states/list-empty-state.svg" alt="Generic Empty State" class="null-state">
			</div>
			<p>${__("Nothing to show")}</p>
		</div>`;
	}

	layout_div() {
		return `<div class="row">
			<div class="col-md-12" id="akta-layout"></div>
			<div class="col-md-6" id="saham-layout"></div>
			<div class="col-md-6" id="pengurus-layout"></div>
		</div>`;
	}

	message_div(message) {
		return `<div class='flex justify-center align-center text-muted' style='height: 50vh;'>
			<div>${message}</div>
		</div>`;
	}

	render_table_header(){
		this.$layout_akta.find("#akta-layout").html(`
		<table class="table table-bordered table-striped" style="font-size: 11px;">
			<thead style="background-color: #5e8ca8; color: white;">
				<tr>
					<th class="text-center" style="vertical-align: middle;">No</th>
					<th class="text-center" style="vertical-align: middle;">Jenis Akta</th>
					<th class="text-center" style="vertical-align: middle;">Nomor</th>
					<th class="text-center" style="vertical-align: middle;">Tanggal Akta</th>
					<th class="text-center" style="vertical-align: middle;">Nama Notaris</th>
					<th class="text-center" style="vertical-align: middle;">Nomor SK Kehakiman</th>
					<th class="text-center" style="vertical-align: middle;">Tanggal SK Kehakiman</th>
					<th class="text-center" style="vertical-align: middle;">Kedudukan</th>
					<th class="text-center" style="vertical-align: middle;">Alamat</th>
					<th class="text-center" style="vertical-align: middle;">Modal Dasar</th>
					<th class="text-center" style="vertical-align: middle;">Modal di Setor</th>
					<th class="text-center" style="vertical-align: middle;">Kegiatan Usaha</th>
					<th class="text-center" style="vertical-align: middle;">BNRI</th>
					<th class="text-center" style="vertical-align: middle;">TBNRI</th>
					<th class="text-center" style="vertical-align: middle;">Tanggal</th>
					<th class="text-center" style="vertical-align: middle;">Keterangan</th>
				</tr>
			</thead>
			<tbody id="akta-tbody">
			</tbody>
		</table>`)

		this.$layout_akta.find("#saham-layout").html(`
		<fieldset style="border: 1px solid #5e8ca8;padding: 2px">
			<legend style="padding-left: 2px;font-size: 12px;width: fit-content;">Saham</legend>		
			<table class="table table-bordered" style="font-size: 11px; margin: 0;">
				<thead style="background-color: #5e8ca8; color: white;">
					<tr>
						<th style="text-align: center;">No</th>
						<th style="text-align: center;">Nomor Akta</th>
						<th style="text-align: center;">Tanggal Akta</th>
						<th style="text-align: center;">Nama</th>
						<th style="text-align: center;">Lembar Saham</th>
						<th style="text-align: center;">Nilai Saham / Lembar</th>
						<th style="text-align: center;">Saham</th>
						<th style="text-align: center;">NPWP</th>
					</tr>
				</thead>
				<tbody id="saham-tbody">
				</tbody>
			</table>
		</fieldset>`);

		this.$layout_akta.find("#pengurus-layout").html(
		`<fieldset style="border: 1px solid #5e8ca8;padding: 2px">
			<legend style="padding-left: 2px;font-size: 12px;width: fit-content;">Susunan Pengurus dan Komisaris</legend>
			<table class="table table-bordered" style="font-size: 11px; margin: 0;">
				<thead style="background-color: #5e8ca8; color: white;">
					<tr>
						<th style="text-align: center;">No</th>
						<th style="text-align: center;">Nomor Akta</th>
						<th style="text-align: center;">Tanggal Akta</th>
						<th style="text-align: center;">Nama</th>
						<th style="text-align: center;">Jabatan</th>
						<th style="text-align: center;">Keterangan</th>
					</tr>
				</thead>
				<tbody id="pengurus-tbody">
				</tbody>
			</table>
		</fieldset>`);
	}

	render_table_data(){
		let me = this;
		let data = me.options.data;
		
		let $akta_tbody = this.$layout_akta.find("#akta-tbody");
		let $saham_tbody = this.$layout_akta.find("#saham-tbody");
		let $pengurus_tbody = this.$layout_akta.find("#pengurus-tbody");

		// Clear existing data
		$akta_tbody.empty();
		$saham_tbody.empty();
		$pengurus_tbody.empty();

		let akta_no = 1;
		let saham_no = 1;
		let pengurus_no = 1;

		// Loop through each akta
		Object.keys(data).forEach(function(nomor_akta) {
			let akta_data = data[nomor_akta];
			
			// Render Akta table
			if (akta_data.details && Object.keys(akta_data.details).length > 0) {
				let details = akta_data.details;
				let $row = $(`
					<tr>
						<td class="text-center">${akta_no}</td>
						<td class="text-center">${details.jenis_akta || ''}</td>
						<td class="text-center">${details.nomor_akta || ''}</td>
						<td class="text-center">${details.tanggal_akta ? frappe.datetime.str_to_user(details.tanggal_akta) : ''}</td>
						<td>${details.nama_notaris || ''}</td>
						<td class="text-center">${details.nomor_sk_kehakiman || ''}</td>
						<td class="text-center">${details.tanggal_sk_kehakiman ? frappe.datetime.str_to_user(details.tanggal_sk_kehakiman) : ''}</td>
						<td>${details.kedudukan || ''}</td>
						<td>${details.alamat || ''}</td>
						<td class="text-right">${details.modal_dasar ? format_currency(details.modal_dasar) : ''}</td>
						<td class="text-right">${details.modal_di_setor ? format_currency(details.modal_di_setor) : ''}</td>
						<td>${details.kegiatan_usaha || ''}</td>
						<td class="text-center">${details.bnri || ''}</td>
						<td class="text-center">${details.tbnri || ''}</td>
						<td>${details.tanggal || ''}</td>
						<td>${details.keterangan || ''}</td>
					</tr>
				`);
				
				// Add click event to row
				$row.on('click', function() {
					me.show_akta_dialog(nomor_akta, akta_data);
				});

				$akta_tbody.append($row);
				akta_no++;
			}

			// Render Saham table
			if (akta_data.saham && akta_data.saham.length > 0) {
				akta_data.saham.forEach(function(saham) {
					let $row = $(`
						<tr>
							<td class="text-center">${saham_no}</td>
							<td class="text-center">${nomor_akta}</td>
							<td class="text-center">${saham.tanggal_akta ? frappe.datetime.str_to_user(saham.tanggal_akta) : ''}</td>
							<td>${saham.nama || ''}</td>
							<td class="text-right">${saham.lembar_saham ? format_number(saham.lembar_saham) : ''}</td>
							<td class="text-right">${saham.nilai_saham ? format_currency(saham.nilai_saham) : ''}</td>
							<td class="text-right">${saham.saham_amount ? format_currency(saham.saham_amount) : ''}</td>
							<td class="text-center">${saham.npwp || ''}</td>
						</tr>
					`);
					$saham_tbody.append($row);
					saham_no++;
				});
			}

			// Render Pengurus table
			if (akta_data.pengurus && akta_data.pengurus.length > 0) {
				akta_data.pengurus.forEach(function(pengurus) {
					let $row = $(`
						<tr>
							<td class="text-center">${pengurus_no}</td>
							<td class="text-center">${nomor_akta}</td>
							<td class="text-center">${pengurus.tanggal_akta ? frappe.datetime.str_to_user(pengurus.tanggal_akta) : ''}</td>
							<td>${pengurus.nama || ''}</td>
							<td>${pengurus.designation || ''}</td>
							<td>${pengurus.note || ''}</td>
						</tr>
					`);
					$pengurus_tbody.append($row);
					pengurus_no++;
				});
			}
		});

		// Show message if no data
		if (akta_no === 1) {
			$akta_tbody.append('<tr><td colspan="14" class="text-center text-muted">No data available</td></tr>');
		}

		if (saham_no === 1) {
			$saham_tbody.append('<tr><td colspan="8" class="text-center text-muted">No data available</td></tr>');
		}

		if (pengurus_no === 1) {
			$pengurus_tbody.append('<tr><td colspan="6" class="text-center text-muted">No data available</td></tr>');
		}
	}

	show_akta_dialog(nomor_akta, akta_data) {
		let me = this;
		
		let dialog = new frappe.ui.Dialog({
			title: __('List Data', [nomor_akta]),
			size: 'large',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'file_list'
				},
			]
		});
		

		// Set HTML structure first
		dialog.fields_dict.file_list.$wrapper.html(`
		<fieldset style="border: 1px solid #5e8ca8;padding: 2px">
			<legend style="padding-left: 2px;font-size: 12px;width: fit-content;">Kriteria</legend>		
			<table class="table table-bordered" style="font-size: 11px; margin: 0;">
				<thead style="background-color: #5e8ca8; color: white;">
					<tr>
						<th>Kriteria</th>
						<th>Filename</th>
					</tr>
				</thead>
				<tbody id="kriteria-tbody">
				</tbody>
			</table>
		</fieldset>`);
		
		// Get the tbody element
		let $kriteria_tbody = dialog.fields_dict.file_list.$wrapper.find("#kriteria-tbody");
		
		// Render Kriteria table
		if (akta_data.kriteria && akta_data.kriteria.length > 0) {
			akta_data.kriteria.forEach(function(k) {
				let file_link = k.kriteria_file ? `<a href="${k.kriteria_file}" target="_blank">${k.kriteria_file}<a/>` : 'No file';
				
				let $row = $(`
					<tr>
						<td>${k.kriteria || ''}</td>
						<td>${file_link}</td>
					</tr>
				`);
				$kriteria_tbody.append($row);
			});
		} else {
			// Show message if no data
			$kriteria_tbody.append('<tr><td colspan="2" class="text-center text-muted">No data available</td></tr>');
		}

		dialog.show();
	}
}