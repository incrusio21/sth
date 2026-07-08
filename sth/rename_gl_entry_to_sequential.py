import frappe

BATCH_SIZE = 5000

def execute():
    """
    One-time patch: renumber every GL Entry so the oldest record
    (by creation) becomes GL-00000001 and each subsequent entry
    increments by 1.

    Two-pass approach avoids name collisions:
      Pass 1 — current names  →  __GLP_<i>__  (temp, collision-safe)
      Pass 2 — __GLP_<i>__   →  GL-<i:08d>   (final names)
    """
    rows = frappe.db.sql(
        "SELECT name FROM `tabGL Entry` ORDER BY creation ASC, name ASC",
        as_dict=False,
    )

    if not rows:
        print("No GL Entry records found — nothing to do.")
        return

    total = len(rows)
    print(f"[GL Renumber] {total} records to process")

    # ── Pass 1: rename to temp names ─────────────────────────────────────────
    print("[GL Renumber] Pass 1: moving to temp names...")
    for batch_start in range(0, total, BATCH_SIZE):
        batch = rows[batch_start : batch_start + BATCH_SIZE]
        for i_rel, (old_name,) in enumerate(batch):
            i = batch_start + i_rel + 1          # 1-based absolute index
            frappe.db.sql(
                "UPDATE `tabGL Entry` SET name = %s WHERE name = %s",
                (f"__GLP_{i}__", old_name),
            )
        frappe.db.commit()
        print(f"  temp-named {min(batch_start + BATCH_SIZE, total)}/{total}")

    # ── Pass 2: rename to final GL-XXXXXXXX names ────────────────────────────
    print("[GL Renumber] Pass 2: assigning final names...")
    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        for i in range(batch_start + 1, batch_end + 1):
            frappe.db.sql(
                "UPDATE `tabGL Entry` SET name = %s WHERE name = %s",
                (f"GL-{i:08d}", f"__GLP_{i}__"),
            )
        frappe.db.commit()
        print(f"  renamed {batch_end}/{total}")

    # ── Sync series counter ───────────────────────────────────────────────────
    frappe.db.sql(
        """
        INSERT INTO `tabSeries` (name, current)
        VALUES ('GL-.', %(n)s)
        ON DUPLICATE KEY UPDATE current = %(n)s
        """,
        {"n": total},
    )
    frappe.db.commit()

    print(f"[GL Renumber] Done. {total} records renumbered. Series counter = {total}.")