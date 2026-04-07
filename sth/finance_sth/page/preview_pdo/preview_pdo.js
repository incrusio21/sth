frappe.require("/assets/sth/css/preview_pdo.css");

function formatCurrency(val) {
	return frappe.format(val || 0, { fieldtype: "Currency" });
}

function sum(arr, field) {
	return arr.reduce((total, row) => total + (row[field] || 0), 0);
}

function getMonthLabel(posting_date) {
	if (!posting_date) return "";
	let d = new Date(posting_date);
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function getMonthsFromData(data) {
	let monthSet = new Set();
	data.forEach(row => {
		if (row.posting_date) {
			monthSet.add(getMonthLabel(row.posting_date));
		}
	});
	return Array.from(monthSet).sort();
}

function filterByMonth(rows, month) {
	return rows.filter(row => getMonthLabel(row.posting_date) === month);
}

function renderMonthCols(months, rowData, estimateField, reviseField) {
	let html = "";
	months.forEach(month => {
		if (rowData && getMonthLabel(rowData.posting_date) === month) {
			html += `
				<td class="text-right">${formatCurrency(rowData[estimateField])}</td>
				<td class="text-right">${formatCurrency(rowData[reviseField])}</td>
				<td class="text-right">0</td>
				<td class="text-right">0</td>
			`;
		} else {
			html += `<td></td><td></td><td></td><td></td>`;
		}
	});
	return html;
}

function renderTotalCols(months, rows, estimateField, reviseField) {
	let html = "";
	months.forEach(month => {
		let monthRows = filterByMonth(rows, month);
		html += `
			<td class="text-right">${formatCurrency(sum(monthRows, estimateField))}</td>
			<td class="text-right">${formatCurrency(sum(monthRows, reviseField))}</td>
			<td class="text-right">0</td>
			<td class="text-right">0</td>
		`;
	});
	return html;
}

function renderEmptyCols(months) {
	let html = "";
	months.forEach(() => {
		html += `<td class="text-right">0</td><td class="text-right">0</td><td class="text-right">0</td><td class="text-right">0</td>`;
	});
	return html;
}

frappe.pages['preview-pdo'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Preview PDO',
		single_column: true
	});

	let container = $('<div>').appendTo(page.body);

	let params = frappe.utils.get_query_params();
	let pdo_name = params.pdo_name;

	frappe.call({
		method: "sth.api.get_pdo_detail_kas",
		args: { pdo_name: pdo_name },
		callback: function (r) {
			let data = r.message || [];
			let container = $(page.body);

			// =====================
			// BULAN DINAMIS DARI DATA
			// =====================
			let months = getMonthsFromData(data);

			// Current month = posting_date dari pdo_name yang dipilih
			let current_row = data.find(row => row.name === pdo_name);
			let currentLabel = current_row ? getMonthLabel(current_row.posting_date) : "";

			// Total kolom = 8 (kiri) + 4 per bulan
			const LEFT = 8;
			let totalCols = LEFT + (months.length * 4);

			let html = `<table class="table_main_content">`;

			// =====================
			// HEADER ROW 1 - LABEL BULAN
			// =====================
			html += `<tr><td colspan="${LEFT}"></td>`;
			months.forEach(month => {
				let label = month === currentLabel
					? `CURRENT MONTH - ${month}`
					: `PREVIOUS MONTH - ${month}`;
				html += `<td colspan="4" style="text-align: center;">${label}</td>`;
			});
			html += `</tr>`;

			// =====================
			// HEADER ROW 2 - ESTIMATE/REVISE/ACTUAL/VARIANCE
			// =====================
			html += `<tr><td colspan="${LEFT}"></td>`;
			months.forEach(() => {
				html += `
					<td>ESTIMATE UNIT</td>
					<td>ESTIMATE REVISE</td>
					<td>ACTUAL</td>
					<td>VARIANCE</td>
				`;
			});
			html += `</tr>`;

			// =====================
			// BEGINNING BALANCE | CASH ON HAND
			// =====================
			html += `<tr><td colspan="${LEFT}">BEGINNING BALANCE | CASH ON HAND</td>${renderEmptyCols(months)}</tr>`;

			// =====================
			// BEGINNING BALANCE | CASH IN BANK
			// =====================
			html += `<tr><td colspan="${LEFT}">BEGINNING BALANCE | CASH IN BANK</td>${renderEmptyCols(months)}</tr>`;

			// =====================
			// PENYESUAIAN SALDO KAS DAN BANK
			// =====================
			html += `<tr><td colspan="${LEFT}">PENYESUAIAN SALDO KAS DAN BANK</td>${renderEmptyCols(months)}</tr>`;

			// =====================
			// DANA CADANGAN
			// =====================
			html += `<tr><td colspan="${totalCols}">DANA CADANGAN</td></tr>`;

			// =====================
			// PLAFON KAS DAN BANK - dari get_pdo_detail_dana_cadangan
			// =====================
			html += `<tr><td colspan="${totalCols}">PLAFON KAS DAN BANK</td></tr>`;

			frappe.call({
				method: "sth.api.get_pdo_detail_dana_cadangan",
				args: { pdo_name: pdo_name },
				callback: function (r) {
					let dcData = r.message || [];

					// Split berdasarkan jenis: Kas dan Bank
					let kasRows = dcData.filter(row => row.jenis === "Kas");
					let bankRows = dcData.filter(row => row.jenis === "Bank");

					// ROW KAS - per bulan (tiap bulan ambil 1 row kas)
					kasRows.forEach(row => {
						html += `<tr>`;
						html += `<td colspan="${LEFT}">Kas</td>`;
						html += renderMonthCols(months, row, 'estimate_unit', 'estimate_revise');
						html += `</tr>`;
					});

					// ROW BANK - per bulan (tiap bulan ambil 1 row bank)
					bankRows.forEach(row => {
						html += `<tr>`;
						html += `<td colspan="${LEFT}">Bank</td>`;
						html += renderMonthCols(months, row, 'estimate_unit', 'estimate_revise');
						html += `</tr>`;
					});

					// TOTAL PLAFON KAS DAN BANK (Kas + Bank per bulan)
					html += `<tr style="font-weight:bold;"><td colspan="${LEFT}">TOTAL</td>`;
					months.forEach(month => {
						let kasMonth = filterByMonth(kasRows, month);
						let bankMonth = filterByMonth(bankRows, month);
						let totalEstimate = sum(kasMonth, 'estimate_unit') + sum(bankMonth, 'estimate_unit');
						let totalRevise = sum(kasMonth, 'estimate_revise') + sum(bankMonth, 'estimate_revise');
						html += `
							<td class="text-right">${formatCurrency(totalEstimate)}</td>
							<td class="text-right">${formatCurrency(totalRevise)}</td>
							<td class="text-right">0</td>
							<td class="text-right">0</td>
						`;
					});
					html += `</tr>`;

					// =====================
					// GROUPING DATA KAS
					// =====================
					let grouped = {};
					data.forEach(row => {
						if (!grouped[row.jenis_kas]) grouped[row.jenis_kas] = [];
						grouped[row.jenis_kas].push(row);
					});

					// =====================
					// EXPENSES HEADER
					// =====================
					html += `<tr><td colspan="${totalCols}"><b>EXPENSES</b></td></tr>`;

					// =====================
					// LOOP GROUP
					// =====================
					Object.keys(grouped).forEach(group => {
						let rows = grouped[group];

						// HEADER GROUP - total estimate per bulan
						html += `<tr><td colspan="${LEFT}"><b>${group}</b></td>${renderTotalCols(months, rows, 'estimate_unit', 'estimate_revise')}</tr>`;

						// HEADER KOLOM
						if (group === "TUNJANGAN PEMBANTU") {
							html += `
								<tr>
									<td colspan="4">Pengguna</td>
									<td colspan="4">Jabatan</td>
									${months.map(() => `<td></td><td></td><td></td><td></td>`).join('')}
								</tr>
							`;
						} else {
							html += `
								<tr>
									<td>Item Barang</td>
									<td>Satuan</td>
									<td>Qty</td>
									<td>Harga</td>
									<td>Qty Revisi</td>
									<td>Harga Revisi</td>
									<td colspan="2">Kebutuhan</td>
									${months.map(() => `<td></td><td></td><td></td><td></td>`).join('')}
								</tr>
							`;
						}

						// DETAIL ITEM
						rows.forEach(row => {
							html += `<tr>`;
							if (group === "TUNJANGAN PEMBANTU") {
								html += `<td colspan="4">${row.pengguna || ''}</td>`;
								html += `<td colspan="4">${row.jabatan || ''}</td>`;
							} else {
								html += `<td>${row.item_barang || ''}</td>`;
								html += `<td>${row.satuan || ''}</td>`;
								html += `<td>${row.qty || ''}</td>`;
								html += `<td>${formatCurrency(row.harga)}</td>`;
								html += `<td>${row.qty_revisi || 0}</td>`;
								html += `<td>${formatCurrency(row.harga_revisi)}</td>`;
								html += `<td colspan="2">${row.kebutuhan || ''}</td>`;
							}
							html += renderMonthCols(months, row, 'estimate_unit', 'estimate_revise');
							html += `</tr>`;
						});

						// TOTAL GROUP
						html += `<tr style="font-weight:bold;"><td colspan="${LEFT}">TOTAL</td>${renderTotalCols(months, rows, 'estimate_unit', 'estimate_revise')}</tr>`;
					});

					// =====================
					// BBM - PERTALITE/SOLAR
					// =====================
					html += `<tr><td colspan="${LEFT}"><b>BBM - PERTALITE/SOLAR</b></td>${renderEmptyCols(months)}</tr>`;
					html += `
						<tr>
							<td>Pengguna</td>
							<td>Jabatan</td>
							<td>Plafon</td>
							<td>Harga</td>
							<td>Plafon Revisi</td>
							<td>Harga Revisi</td>
							<td colspan="2">Keperluan</td>
							${months.map(() => `<td></td><td></td><td></td><td></td>`).join('')}
						</tr>
					`;

					frappe.call({
						method: "sth.api.get_pdo_detail_bahan_bakar",
						args: { pdo_name: pdo_name },
						callback: function (r) {
							let bbmData = r.message || [];

							bbmData.forEach(row => {
								html += `<tr>`;
								html += `<td>${row.pengguna || ''}</td>`;
								html += `<td>${row.jabatan || ''}</td>`;
								html += `<td>${row.plafon || ''}</td>`;
								html += `<td>${row.harga || ''}</td>`;
								html += `<td>${row.plafon_revisi || ''}</td>`;
								html += `<td>${row.harga_revisi || ''}</td>`;
								html += `<td colspan="2">${row.keperluan || ''}</td>`;
								html += renderMonthCols(months, row, 'estimate_unit', 'estimate_revise');
								html += `</tr>`;
							});

							// TOTAL BBM
							html += `<tr style="font-weight:bold;"><td colspan="${LEFT}">TOTAL</td>${renderTotalCols(months, bbmData, 'estimate_unit', 'estimate_revise')}</tr>`;

							// =====================
							// PERJALANAN DINAS
							// =====================
							html += `<tr><td colspan="${LEFT}"><b>PERJALANAN DINAS</b></td>${renderEmptyCols(months)}</tr>`;
							html += `
								<tr>
									<td>Pengguna</td>
									<td>No Polisi</td>
									<td>Jenis</td>
									<td>Hari Dinas</td>
									<td>Plafon</td>
									<td>Hari Dinas Revisi</td>
									<td>Plafon Revisi</td>
									<td>Keperluan</td>
									${months.map(() => `<td></td><td></td><td></td><td></td>`).join('')}
								</tr>
							`;

							frappe.call({
								method: "sth.api.get_pdo_detail_perjalanan_dinas",
								args: { pdo_name: pdo_name },
								callback: function (r) {
									let pdData = r.message || [];

									pdData.forEach(row => {
										html += `<tr>`;
										html += `<td>${row.pengguna || ''}</td>`;
										html += `<td>${row.no_polisi || ''}</td>`;
										html += `<td>${row.jenis || ''}</td>`;
										html += `<td>${row.hari_dinas || ''}</td>`;
										html += `<td>${row.plafon || ''}</td>`;
										html += `<td>${row.hari_dinas_revisi || ''}</td>`;
										html += `<td>${row.plafon_revisi || ''}</td>`;
										html += `<td>${row.keperluan || ''}</td>`;
										html += renderMonthCols(months, row, 'estimate_unit', 'estimate_revise');
										html += `</tr>`;
									});

									// TOTAL PERJALANAN DINAS
									html += `<tr style="font-weight:bold;"><td colspan="${LEFT}">TOTAL</td>${renderTotalCols(months, pdData, 'estimate_unit', 'estimate_revise')}</tr>`;

									html += `</table>`;
									container.html(html);
								}
							});
						}
					});
				}
			});
		}
	});
};