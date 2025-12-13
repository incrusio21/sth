frappe.ui.form.on('Set Up BPJS PT', {
    refresh: function(frm) {
        // Disable add row button for the child table
        frm.fields_dict['set_up_bpjs_pt_table'].grid.cannot_add_rows = true;
        frm.refresh_field('set_up_bpjs_pt_table');
    },
    
    jenis_bpjs: function(frm) {
        if (frm.doc.jenis_bpjs) {
            // Clear existing rows
            frm.clear_table('set_up_bpjs_pt_table');
            
            // Fetch Program BPJS based on selected jenis_bpjs (alphabetically)
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Program BPJS',
                    filters: {
                        'jenis_bpjs': frm.doc.jenis_bpjs
                    },
                    fields: ['name'],
                    order_by: 'name desc'
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
						
						r.message.sort(function(a, b) {
                            return a.name.localeCompare(b.name, undefined, {sensitivity: 'base'});
                        });

                        let programs_to_process = r.message.length;
                        let programs_processed = 0;
                        
                        // For each Program BPJS found
                        r.message.forEach(function(program) {
                            // Fetch the details of each program including child table
                            frappe.call({
                                method: 'frappe.client.get',
                                args: {
                                    doctype: 'Program BPJS',
                                    name: program.name
                                },
                                callback: function(res) {
                                    if (res.message) {
                                        let program_doc = res.message;
                                        
                                        // Separate beban options
                                        let beban_karyawan_options = [];
                                        let beban_perusahaan_options = [];
                                        if (program_doc.beban) {
                                            program_doc.beban.forEach(function(beban) {

                                                if (beban.tipe_beban === 'Beban Karyawan') {
                                                    beban_karyawan_options.push(beban.nilai_beban);
                                                } else if (beban.tipe_beban === 'Beban Perusahaan') {
                                                    beban_perusahaan_options.push(beban.nilai_beban);
                                                }
                                            });
                                        }
                                        
                                        // Add row to child table
                                        let row = frm.add_child('set_up_bpjs_pt_table');
                                        row.nama_program = program_doc.name;
                                        
                                        // Set default beban_karyawan (first option or 0)
                                        if (beban_karyawan_options.length === 1) {
                                            row.beban_karyawan = beban_karyawan_options[0];
                                        } else if (beban_karyawan_options.length > 1) {
                                            row.beban_karyawan = beban_karyawan_options[0]; // Default to first
                                        }
                                        
                                        // Handle beban_perusahaan
                                        if (beban_perusahaan_options.length === 1) {
                                            // Only one option, set it directly
                                            row.beban_perusahaan = beban_perusahaan_options[0];
                                            programs_processed++;
                                            
                                            if (programs_processed === programs_to_process) {
                                                frm.refresh_field('set_up_bpjs_pt_table');
                                            }
                                        } else if (beban_perusahaan_options.length > 1) {
                                            // Multiple options, show popup
                                            show_beban_perusahaan_dialog(
                                                frm, 
                                                row, 
                                                program_doc.name, 
                                                beban_perusahaan_options,
                                                function() {
                                                    programs_processed++;
                                                    if (programs_processed === programs_to_process) {
                                                        frm.refresh_field('set_up_bpjs_pt_table');
                                                    }
                                                }
                                            );
                                        } else {
                                            programs_processed++;
                                            if (programs_processed === programs_to_process) {
                                                frm.refresh_field('set_up_bpjs_pt_table');
                                            }
                                        }
                                    }
                                }
                            });
                        });
                    } else {
                        frappe.msgprint(__('No Program BPJS found for selected Jenis BPJS'));
                    }
                }
            });
        }
    }
});

// Function to show dialog for selecting beban_perusahaan
function show_beban_perusahaan_dialog(frm, row, program_name, options, callback) {
    let dialog_options = options.map(function(val) {
        return {
            label: (val) + '%',
            value: val
        };
    });
    
    let d = new frappe.ui.Dialog({
        title: __('Select Beban Perusahaan for {0}', [program_name]),
        fields: [
            {
                label: __('Multiple options available for Beban Perusahaan. Please select one:'),
                fieldname: 'info',
                fieldtype: 'HTML',
                options: '<p style="color: #666; margin-bottom: 10px;">Program: <strong>' + program_name + '</strong></p>'
            },
            {
                label: 'Beban Perusahaan',
                fieldname: 'beban_value',
                fieldtype: 'Select',
                options: dialog_options.map(opt => opt.label).join('\n'),
                reqd: 1,
                default: dialog_options[0].label
            }
        ],
        primary_action_label: __('Select'),
        primary_action: function(values) {
            // Find the selected option value
            let selected_option = dialog_options.find(
                opt => opt.label === values.beban_value
            );
            
            if (selected_option) {
                row.beban_perusahaan = selected_option.value;
                frm.refresh_field('set_up_bpjs_pt_table');
            }
            
            d.hide();
            if (callback) callback();
        }
    });
    
    d.show();
}

// Handle child table field clicks for manual changes
frappe.ui.form.on('Set Up BPJS PT Table', {
    beban_perusahaan: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // Only show dialog if field is clicked/changed after initial load
        if (row.nama_program && row.beban_perusahaan !== undefined) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Program BPJS',
                    name: row.nama_program
                },
                callback: function(r) {
                    if (r.message) {
                        let program_doc = r.message;
                        let beban_perusahaan_options = [];
                        
                        if (program_doc.beban_perusahaan) {
                            program_doc.beban_perusahaan.forEach(function(beban) {
                                if (beban.tipe_beban === 'Beban Perusahaan') {
                                    beban_perusahaan_options.push({
                                        label: (beban.nilai_beban * 100) + '%',
                                        value: beban.nilai_beban
                                    });
                                }
                            });
                        }
                        
                        if (beban_perusahaan_options.length > 1) {
                            let d = new frappe.ui.Dialog({
                                title: __('Select Beban Perusahaan for {0}', [row.nama_program]),
                                fields: [
                                    {
                                        label: 'Beban Perusahaan',
                                        fieldname: 'beban_value',
                                        fieldtype: 'Select',
                                        options: beban_perusahaan_options.map(opt => opt.label).join('\n'),
                                        reqd: 1,
                                        default: beban_perusahaan_options[0].label
                                    }
                                ],
                                primary_action_label: __('Select'),
                                primary_action: function(values) {
                                    let selected_option = beban_perusahaan_options.find(
                                        opt => opt.label === values.beban_value
                                    );
                                    
                                    if (selected_option) {
                                        frappe.model.set_value(cdt, cdn, 'beban_perusahaan', selected_option.value);
                                    }
                                    
                                    d.hide();
                                }
                            });
                            
                            d.show();
                        }
                    }
                }
            });
        }
    },
    
    beban_karyawan: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (row.nama_program && row.beban_karyawan !== undefined) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Program BPJS',
                    name: row.nama_program
                },
                callback: function(r) {
                    if (r.message) {
                        let program_doc = r.message;
                        let beban_karyawan_options = [];
                        
                        if (program_doc.beban_perusahaan) {
                            program_doc.beban_perusahaan.forEach(function(beban) {
                                if (beban.tipe_beban === 'Beban Karyawan') {
                                    beban_karyawan_options.push({
                                        label: (beban.nilai_beban * 100) + '%',
                                        value: beban.nilai_beban
                                    });
                                }
                            });
                        }
                        
                        if (beban_karyawan_options.length > 1) {
                            let d = new frappe.ui.Dialog({
                                title: __('Select Beban Karyawan for {0}', [row.nama_program]),
                                fields: [
                                    {
                                        label: 'Beban Karyawan',
                                        fieldname: 'beban_value',
                                        fieldtype: 'Select',
                                        options: beban_karyawan_options.map(opt => opt.label).join('\n'),
                                        reqd: 1,
                                        default: beban_karyawan_options[0].label
                                    }
                                ],
                                primary_action_label: __('Select'),
                                primary_action: function(values) {
                                    let selected_option = beban_karyawan_options.find(
                                        opt => opt.label === values.beban_value
                                    );
                                    
                                    if (selected_option) {
                                        frappe.model.set_value(cdt, cdn, 'beban_karyawan', selected_option.value);
                                    }
                                    
                                    d.hide();
                                }
                            });
                            
                            d.show();
                        }
                    }
                }
            });
        }
    }
});