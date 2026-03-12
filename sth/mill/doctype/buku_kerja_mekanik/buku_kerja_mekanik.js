frappe.ui.form.on('Buku Kerja Mekanik', {
    jam_mulai(frm) {
        calculate_total_jam(frm);
    },
    jam_selesai(frm) {
        calculate_total_jam(frm);
    }
});

function calculate_total_jam(frm) {
    const jam_mulai = frm.doc.jam_mulai;
    const jam_selesai = frm.doc.jam_selesai;

    if (!jam_mulai || !jam_selesai) return;

    // Parse time strings "HH:mm:ss"
    const [h1, m1, s1] = jam_mulai.split(':').map(Number);
    const [h2, m2, s2] = jam_selesai.split(':').map(Number);

    const start = h1 * 3600 + m1 * 60 + s1;
    const end   = h2 * 3600 + m2 * 60 + s2;

    let diff_seconds = end - start;

    // Handle overnight (e.g. start 23:00, end 01:00)
    if (diff_seconds < 0) diff_seconds += 24 * 3600;

    const hours   = Math.floor(diff_seconds / 3600);
    const minutes = Math.floor((diff_seconds % 3600) / 60);
    const seconds = diff_seconds % 60;

    // Format as HH:mm:ss or just set total hours as float
    const total_jam_str = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    const total_jam_float = Math.round((hours + minutes / 60 + seconds / 3600) * 10) / 10;

    // Use whichever fits your field type:
    // If total_jam is a Time/Data field → use total_jam_str
    // If total_jam is a Float/Int field  → use total_jam_float

    frm.set_value('total_jam', total_jam_float); // ← change to total_jam_str if needed
}