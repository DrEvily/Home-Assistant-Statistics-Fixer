#!/usr/bin/env python3
# Home Assistant Statistics Fixer (SQLite) v10
# - monthly Start/End window, choose columns: sum/state/both
# - NEW: Preview & Diagnose render ONLY the columns selected in "Columns to adjust"
#        (if "both", they render both; else only the chosen one)
#
# Close Home Assistant before applying changes.

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "HA Statistics Fixer (SQLite) v10"
DEFAULT_TZ = "Europe/Berlin"

def log(msg, textbox):
    textbox.configure(state="normal")
    textbox.insert(tk.END, msg + "\n")
    textbox.see(tk.END)
    textbox.configure(state="disabled")

def pick_db_path(entry):
    path = filedialog.askopenfilename(
        title="Select home-assistant_v2.db",
        filetypes=[("SQLite DB", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")],
    )
    if path:
        entry.delete(0, tk.END)
        entry.insert(0, path)

def make_backup(db_path, textbox):
    try:
        if not os.path.isfile(db_path):
            raise FileNotFoundError("DB file not found")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{db_path}.{ts}.bak"
        shutil.copy2(db_path, backup_path)
        log(f"Backup created: {backup_path}", textbox)
        return backup_path
    except Exception as e:
        log(f"ERROR creating backup: {e}", textbox)
        return None

def parse_local(dt_str, tz_str):
    if not dt_str or not dt_str.strip():
        return None
    return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz_str))

def to_utc_forms(local_dt):
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    plain = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
    with_tz = plain + "+00:00"
    epoch = int(utc_dt.timestamp())
    return utc_dt, plain, with_tz, epoch

def ensure_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def get_metadata_id(conn, entity_id):
    cur = conn.cursor()
    cur.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?;", (entity_id,))
    row = cur.fetchone()
    return row[0] if row else None

def list_similar_ids(conn, entity_id):
    cur = conn.cursor()
    like = f"%{entity_id}%"
    cur.execute("SELECT id, statistic_id FROM statistics_meta WHERE statistic_id LIKE ? ORDER BY statistic_id;", (like,))
    return cur.fetchall()

def table_has_column(conn, table, column):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

def range_where_clause(use_ts, start_plain, start_tz, start_epoch, end_plain, end_tz, end_epoch):
    # half-open [start, end) when end provided, else >= start
    if use_ts:
        if end_epoch is None:
            return "metadata_id = ? AND start_ts >= ?", lambda mid: (mid, start_epoch)
        else:
            return "metadata_id = ? AND start_ts >= ? AND start_ts < ?", lambda mid: (mid, start_epoch, end_epoch)
    else:
        if end_plain is None:
            return "metadata_id = ? AND datetime(start) >= datetime(?)", lambda mid: (mid, start_plain)
        else:
            return "metadata_id = ? AND datetime(start) >= datetime(?) AND datetime(start) < datetime(?)", lambda mid: (mid, start_plain, end_plain)

def build_column_select(which_cols):
    if which_cols == "sum":
        return ("sum", ["sum"])
    elif which_cols == "state":
        return ("state", ["state"])
    else:  # both
        return ("state, sum", ["state", "sum"])

def preview_changes(db_path, entity_id, start_local_str, end_local_str, tz_str, textbox, which_cols, include_short_term=False):
    try:
        if not os.path.isfile(db_path):
            raise FileNotFoundError("DB file not found")
        if not start_local_str:
            raise ValueError("Start timestamp required.")
        start_local = parse_local(start_local_str, tz_str)
        end_local = parse_local(end_local_str, tz_str) if end_local_str else None
        _, start_plain, start_tz, start_epoch = to_utc_forms(start_local)
        end_plain = end_tz = None; end_epoch = None
        if end_local:
            _, end_plain, end_tz, end_epoch = to_utc_forms(end_local)

        conn = ensure_connection(db_path)
        try:
            mid = get_metadata_id(conn, entity_id)
            if mid is None:
                log(f"Entity not found in statistics_meta: {entity_id}", textbox)
                sims = list_similar_ids(conn, entity_id)
                if sims:
                    log("Similar statistic_ids:", textbox)
                    for sid, name in sims:
                        log(f"  metadata_id={sid}  statistic_id={name}", textbox)
                return

            use_start_ts = table_has_column(conn, "statistics", "start_ts")
            log(f"Entity metadata_id: {mid}", textbox)
            log(f"Local START: {start_local_str} {tz_str}", textbox)
            if end_local:
                log(f"Local END (exclusive): {end_local_str} {tz_str}", textbox)
            if use_start_ts:
                log(f"UTC START epoch: {start_epoch}" + (f", END epoch: {end_epoch}" if end_epoch else ""), textbox)
            else:
                log(f"UTC START: {start_plain}" + (f", END: {end_plain}" if end_plain else ""), textbox)
            log(f"Using {'start_ts' if use_start_ts else 'start'} for comparisons.", textbox)
            log(f"Columns selected: {which_cols}", textbox)

            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM statistics WHERE metadata_id = ?;", (mid,))
            overall = cur.fetchone()[0]
            log(f"Total rows in `statistics` for this entity: {overall}", textbox)

            where_sql, params_fn = range_where_clause(use_start_ts, start_plain, start_tz, start_epoch, end_plain, end_tz, end_epoch)
            cur.execute(f"SELECT COUNT(*) FROM statistics WHERE {where_sql};", params_fn(mid))
            count_main = cur.fetchone()[0]
            log(f"Rows in `statistics` within range: {count_main}", textbox)

            # Select columns per choice
            col_sql, col_list = build_column_select(which_cols)
            sel_col = "start_ts" if use_start_ts else "start"
            order_col = "start_ts" if use_start_ts else "datetime(start)"
            cur.execute(f"""
                SELECT {sel_col}, {col_sql} FROM statistics
                WHERE {where_sql}
                ORDER BY {order_col} ASC
                LIMIT 10;
            """, params_fn(mid))
            rows = cur.fetchall()
            if rows:
                header = " | ".join(["time"] + col_list)
                log("First rows inside range (" + header + "):", textbox)
                for row in rows:
                    time_val = row[0]
                    vals = row[1:]
                    if use_start_ts:
                        iso = datetime.fromtimestamp(int(time_val), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")
                        log("  " + " | ".join([iso] + [str(v) for v in vals]), textbox)
                    else:
                        log("  " + " | ".join([str(time_val)] + [str(v) for v in vals]), textbox)
            else:
                log("No rows inside the selected range.", textbox)

            if include_short_term:
                use_st_ts = table_has_column(conn, "statistics_short_term", "start_ts")
                cur.execute("SELECT COUNT(*) FROM statistics_short_term WHERE metadata_id = ?;", (mid,))
                overall_st = cur.fetchone()[0]
                log(f"Total rows in `statistics_short_term` for this entity: {overall_st}", textbox)

                where_sql_st, params_fn_st = range_where_clause(use_st_ts, start_plain, start_tz, start_epoch, end_plain, end_tz, end_epoch)
                cur.execute(f"SELECT COUNT(*) FROM statistics_short_term WHERE {where_sql_st};", params_fn_st(mid))
                count_st = cur.fetchone()[0]
                log(f"Rows in `statistics_short_term` within range: {count_st}", textbox)

        finally:
            conn.close()

    except Exception as e:
        log(f"ERROR during preview: {e}", textbox)

def apply_correction(db_path, entity_id, start_local_str, end_local_str, tz_str, offset, textbox, which_cols, include_short_term=False):
    try:
        if not os.path.isfile(db_path):
            raise FileNotFoundError("DB file not found")
        if not start_local_str:
            raise ValueError("Start timestamp required.")
        start_local = parse_local(start_local_str, tz_str)
        end_local = parse_local(end_local_str, tz_str) if end_local_str else None
        _, start_plain, start_tz, start_epoch = to_utc_forms(start_local)
        end_plain = end_tz = None; end_epoch = None
        if end_local:
            _, end_plain, end_tz, end_epoch = to_utc_forms(end_local)

        backup = make_backup(db_path, textbox)
        if not backup:
            if not messagebox.askyesno("Proceed without backup?", "Backup could not be created. Proceed anyway?"):
                log("Aborted by user.", textbox)
                return

        conn = ensure_connection(db_path)
        try:
            mid = get_metadata_id(conn, entity_id)
            if mid is None:
                log(f"Entity not found in statistics_meta: {entity_id}", textbox)
                sims = list_similar_ids(conn, entity_id)
                if sims:
                    log("Similar statistic_ids:", textbox)
                    for sid, name in sims:
                        log(f"  metadata_id={sid}  statistic_id={name}", textbox)
                return

            use_start_ts = table_has_column(conn, "statistics", "start_ts")
            cur = conn.cursor()
            conn.execute("BEGIN;")

            where_sql, params_fn = range_where_clause(use_start_ts, start_plain, start_tz, start_epoch, end_plain, end_tz, end_epoch)

            cols = (["sum"] if which_cols=="sum" else ["state"] if which_cols=="state" else ["sum","state"])
            updated_main = {}
            for col in cols:
                cur.execute(f"UPDATE statistics SET {col} = {col} + ? WHERE {where_sql};", (offset, *params_fn(mid)))
                updated_main[col] = cur.rowcount

            updated_st = 0
            if include_short_term:
                use_st_ts = table_has_column(conn, "statistics_short_term", "start_ts")
                where_sql_st, params_fn_st = range_where_clause(use_st_ts, start_plain, start_tz, start_epoch, end_plain, end_tz, end_epoch)
                for col in cols:
                    cur.execute(f"UPDATE statistics_short_term SET {col} = {col} + ? WHERE {where_sql_st};", (offset, *params_fn_st(mid)))
                    updated_st += cur.rowcount

            conn.commit()
            rng = f"{start_local_str} → {end_local_str or '∞'} ({tz_str})"
            log(f"Applied offset {offset:+g} to {', '.join(cols)} for range {rng}.", textbox)
            log("Updated rows (statistics): " + (", ".join([f"{k}={v}" for k, v in updated_main.items()]) if updated_main else "0"), textbox)
            if include_short_term:
                log(f"Updated rows (statistics_short_term): {updated_st}", textbox)
            log("Restart Home Assistant and hard-refresh the UI to see changes.", textbox)

        except Exception as e:
            conn.rollback()
            log(f"ERROR during apply (rolled back): {e}", textbox)
        finally:
            conn.close()

    except Exception as e:
        log(f"ERROR during apply: {e}", textbox)

def diagnose(db_path, entity_id, start_local_str, end_local_str, tz_str, textbox, which_cols):
    try:
        if not os.path.isfile(db_path):
            raise FileNotFoundError("DB file not found")
        if not start_local_str:
            raise ValueError("Start timestamp required.")
        start_local = parse_local(start_local_str, tz_str)
        end_local = parse_local(end_local_str, tz_str) if end_local_str else None
        _, start_plain, start_tz, start_epoch = to_utc_forms(start_local)
        end_plain = end_tz = None; end_epoch = None
        if end_local:
            _, end_plain, end_tz, end_epoch = to_utc_forms(end_local)

        conn = ensure_connection(db_path)
        try:
            mid = get_metadata_id(conn, entity_id)
            log("=== Diagnose ===", textbox)
            if mid is None:
                log(f"Entity not found in statistics_meta: {entity_id}", textbox)
                sims = list_similar_ids(conn, entity_id)
                if sims:
                    log("Similar statistic_ids:", textbox)
                    for sid, name in sims:
                        log(f"  metadata_id={sid}  statistic_id={name}", textbox)
                return

            cur = conn.cursor()
            use_start_ts = table_has_column(conn, "statistics", "start_ts")
            log(f"Entity metadata_id: {mid}", textbox)
            log(f"Columns selected: {which_cols}", textbox)

            # Global range + last 5 (according to selection)
            col_sql, col_list = build_column_select(which_cols)
            if use_start_ts:
                cur.execute("SELECT MIN(start_ts), MAX(start_ts), COUNT(*) FROM statistics WHERE metadata_id = ?;", (mid,))
                mn, mx, cnt = cur.fetchone()
                mn_iso = datetime.fromtimestamp(int(mn), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00") if mn else None
                mx_iso = datetime.fromtimestamp(int(mx), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00") if mx else None
                log(f"Range in `statistics` (start_ts): min={mn_iso}, max={mx_iso}, total_rows={cnt}", textbox)
                head = " | ".join(["time"] + col_list)
                log("Last 5 rows overall (" + head + "):", textbox)
                cur.execute(f"SELECT start_ts, {col_sql} FROM statistics WHERE metadata_id = ? ORDER BY start_ts DESC LIMIT 5;", (mid,))
                for row in cur.fetchall():
                    iso = datetime.fromtimestamp(int(row[0]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")
                    vals = row[1:]
                    log("  " + " | ".join([iso] + [str(v) for v in vals]), textbox)
            else:
                cur.execute("SELECT MIN(start), MAX(start), COUNT(*) FROM statistics WHERE metadata_id = ?;", (mid,))
                mn, mx, cnt = cur.fetchone()
                log(f"Range in `statistics`: min={mn}, max={mx}, total_rows={cnt}", textbox)
                head = " | ".join(["time"] + col_list)
                log("Last 5 rows overall (" + head + "):", textbox)
                cur.execute(f"SELECT start, {col_sql} FROM statistics WHERE metadata_id = ? ORDER BY datetime(start) DESC LIMIT 5;", (mid,))
                for row in cur.fetchall():
                    log("  " + " | ".join([str(row[0])] + [str(v) for v in row[1:]]), textbox)

            # Boundary listings
            if use_start_ts:
                to_iso = lambda ts: datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")
                log(f"Local START: {start_local_str} {tz_str}", textbox)
                if end_local:
                    log(f"Local END (exclusive): {end_local_str} {tz_str}", textbox)
                log(f"UTC START epoch: {start_epoch}" + (f", END epoch: {end_epoch}" if end_epoch else ""), textbox)

                log("Rows just BEFORE start:", textbox)
                cur.execute(f"""
                    SELECT start_ts, {col_sql} FROM statistics
                    WHERE metadata_id = ? AND start_ts < ?
                    ORDER BY start_ts DESC LIMIT 5;
                """, (mid, start_epoch))
                for row in cur.fetchall():
                    log("  " + " | ".join([to_iso(row[0])] + [str(v) for v in row[1:]]), textbox)

                log("Rows IN RANGE:", textbox)
                if end_local:
                    cur.execute(f"""
                        SELECT start_ts, {col_sql} FROM statistics
                        WHERE metadata_id = ? AND start_ts >= ? AND start_ts < ?
                        ORDER BY start_ts ASC LIMIT 12;
                    """, (mid, start_epoch, end_epoch))
                else:
                    cur.execute(f"""
                        SELECT start_ts, {col_sql} FROM statistics
                        WHERE metadata_id = ? AND start_ts >= ?
                        ORDER BY start_ts ASC LIMIT 12;
                    """, (mid, start_epoch))
                for row in cur.fetchall():
                    log("  " + " | ".join([to_iso(row[0])] + [str(v) for v in row[1:]]), textbox)

                if end_local:
                    log("Rows just AFTER end:", textbox)
                    cur.execute(f"""
                        SELECT start_ts, {col_sql} FROM statistics
                        WHERE metadata_id = ? AND start_ts >= ?
                        ORDER BY start_ts ASC LIMIT 5;
                    """, (mid, end_epoch))
                    for row in cur.fetchall():
                        log("  " + " | ".join([to_iso(row[0])] + [str(v) for v in row[1:]]), textbox)

            else:
                log(f"Local START: {start_local_str} {tz_str}", textbox)
                if end_local:
                    log(f"Local END (exclusive): {end_local_str} {tz_str}", textbox)
                log(f"UTC START: {start_plain}" + (f", END: {end_plain}" if end_plain else ""), textbox)

                log("Rows just BEFORE start:", textbox)
                cur.execute(f"""
                    SELECT start, {col_sql} FROM statistics
                    WHERE metadata_id = ? AND datetime(start) < datetime(?)
                    ORDER BY datetime(start) DESC LIMIT 5;
                """, (mid, start_plain))
                for row in cur.fetchall():
                    log("  " + " | ".join([str(row[0])] + [str(v) for v in row[1:]]), textbox)

                log("Rows IN RANGE:", textbox)
                if end_local:
                    cur.execute(f"""
                        SELECT start, {col_sql} FROM statistics
                        WHERE metadata_id = ? AND datetime(start) >= datetime(?) AND datetime(start) < datetime(?)
                        ORDER BY datetime(start) ASC LIMIT 12;
                    """, (mid, start_plain, end_plain))
                else:
                    cur.execute(f"""
                        SELECT start, {col_sql} FROM statistics
                        WHERE metadata_id = ? AND datetime(start) >= datetime(?)
                        ORDER BY datetime(start) ASC LIMIT 12;
                    """, (mid, start_plain))
                for row in cur.fetchall():
                    log("  " + " | ".join([str(row[0])] + [str(v) for v in row[1:]]), textbox)

                if end_local:
                    log("Rows just AFTER end:", textbox)
                    cur.execute(f"""
                        SELECT start, {col_sql} FROM statistics
                        WHERE metadata_id = ? AND datetime(start) >= datetime(?)
                        ORDER BY datetime(start) ASC LIMIT 5;
                    """, (mid, end_plain))
                    for row in cur.fetchall():
                        log("  " + " | ".join([str(row[0])] + [str(v) for v in row[1:]]), textbox)

        finally:
            conn.close()

    except Exception as e:
        log(f"ERROR during diagnose: {e}", textbox)

def on_preview(entries, textbox, chk_short_term_var):
    db_path = entries["db_path"].get().strip()
    entity_id = entries["entity_id"].get().strip()
    start_ts = entries["start_local"].get().strip()
    end_ts = entries["end_local"].get().strip()
    tz_str = entries["tz"].get().strip() or DEFAULT_TZ
    which_cols = entries["which_cols"].get()
    include_st = bool(chk_short_term_var.get())
    if not (db_path and entity_id and start_ts):
        messagebox.showerror("Missing fields", "Please fill DB path, entity_id and START timestamp.")
        return
    preview_changes(db_path, entity_id, start_ts, end_ts, tz_str, textbox, which_cols, include_short_term=include_st)

def on_apply(entries, textbox, chk_short_term_var):
    db_path = entries["db_path"].get().strip()
    entity_id = entries["entity_id"].get().strip()
    start_ts = entries["start_local"].get().strip()
    end_ts = entries["end_local"].get().strip()
    tz_str = entries["tz"].get().strip() or DEFAULT_TZ
    offset_str = entries["offset"].get().strip()
    which_cols = entries["which_cols"].get()
    include_st = bool(chk_short_term_var.get())
    if not (db_path and entity_id and start_ts and offset_str):
        messagebox.showerror("Missing fields", "Please fill DB path, entity_id, START and offset.")
        return
    try:
        offset = float(offset_str.replace(",", "."))
    except ValueError:
        messagebox.showerror("Invalid offset", "Offset must be a number (kWh). Use negative to remove a positive jump.")
        return
    apply_correction(db_path, entity_id, start_ts, end_ts, tz_str, offset, textbox, which_cols, include_short_term=include_st)

def on_diagnose(entries, textbox):
    db_path = entries["db_path"].get().strip()
    entity_id = entries["entity_id"].get().strip()
    start_ts = entries["start_local"].get().strip()
    end_ts = entries["end_local"].get().strip()
    tz_str = entries["tz"].get().strip() or DEFAULT_TZ
    which_cols = entries["which_cols"].get()
    if not (db_path and entity_id and start_ts):
        messagebox.showerror("Missing fields", "Please fill DB path, entity_id and START timestamp.")
        return
    diagnose(db_path, entity_id, start_ts, end_ts, tz_str, textbox, which_cols)

def build_gui():
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("980x820")

    main = ttk.Frame(root, padding=12)
    main.pack(fill="both", expand=True)

    entries = {}

    ttk.Label(main, text="SQLite DB path (home-assistant_v2.db):").grid(row=0, column=0, sticky="w")
    e_db = ttk.Entry(main, width=80)
    e_db.grid(row=1, column=0, sticky="we", padx=(0, 8))
    ttk.Button(main, text="Browse…", command=lambda: pick_db_path(e_db)).grid(row=1, column=1, sticky="w")
    entries["db_path"] = e_db

    ttk.Label(main, text="Entity ID (e.g., sensor.pv_sg_meter_monthly):").grid(row=2, column=0, sticky="w", pady=(10,0))
    e_entity = ttk.Entry(main, width=60)
    e_entity.grid(row=3, column=0, sticky="we", padx=(0,8))
    entries["entity_id"] = e_entity

    ttk.Label(main, text="Local START (YYYY-MM-DD HH:MM):").grid(row=4, column=0, sticky="w", pady=(10,0))
    e_start = ttk.Entry(main, width=25)
    e_start.grid(row=5, column=0, sticky="w")
    e_start.insert(0, "2025-09-01 00:00")
    entries["start_local"] = e_start

    ttk.Label(main, text="Local END (exclusive, optional, YYYY-MM-DD HH:MM):").grid(row=4, column=1, sticky="w", pady=(10,0))
    e_end = ttk.Entry(main, width=25)
    e_end.grid(row=5, column=1, sticky="w")
    e_end.insert(0, "2025-10-01 00:00")
    entries["end_local"] = e_end

    ttk.Label(main, text="Timezone (IANA):").grid(row=6, column=0, sticky="w", pady=(10,0))
    e_tz = ttk.Entry(main, width=25)
    e_tz.grid(row=7, column=0, sticky="w")
    e_tz.insert(0, DEFAULT_TZ)
    entries["tz"] = e_tz

    ttk.Label(main, text="Correction offset (kWh):").grid(row=6, column=1, sticky="w", pady=(10,0))
    e_off = ttk.Entry(main, width=20)
    e_off.grid(row=7, column=1, sticky="w")
    entries["offset"] = e_off

    ttk.Label(main, text="Columns to adjust:").grid(row=6, column=2, sticky="w", pady=(10,0))
    which = ttk.Combobox(main, values=["sum", "state", "both"], state="readonly", width=10)
    which.current(0)  # default: sum
    which.grid(row=7, column=2, sticky="w")
    entries["which_cols"] = which

    chk_short_term_var = tk.IntVar(value=0)
    chk_short_term = ttk.Checkbutton(
        main, text="Also fix statistics_short_term", variable=chk_short_term_var
    )
    chk_short_term.grid(row=7, column=3, sticky="w", padx=(8, 0))

    btns = ttk.Frame(main)
    btns.grid(row=8, column=0, columnspan=4, sticky="w", pady=(12,6))
    ttk.Button(btns, text="Preview", command=lambda: on_preview(entries, txt, chk_short_term_var)).pack(side="left", padx=(0,8))
    ttk.Button(btns, text="Apply Correction", command=lambda: on_apply(entries, txt, chk_short_term_var)).pack(side="left", padx=(0,8))
    ttk.Button(btns, text="Diagnose", command=lambda: on_diagnose(entries, txt)).pack(side="left", padx=(0,8))

    ttk.Label(main, text="Log (shows no local time!):").grid(row=9, column=0, sticky="w", pady=(10,0))
    txt = tk.Text(main, height=28, width=140, state="disabled")
    txt.grid(row=10, column=0, columnspan=4, sticky="nsew")
    scroll = ttk.Scrollbar(main, orient="vertical", command=txt.yview)
    scroll.grid(row=10, column=4, sticky="ns")
    txt.configure(yscrollcommand=scroll.set)

    main.columnconfigure(0, weight=1)
    main.rowconfigure(10, weight=1)

    footer = ttk.Label(main, text="Close Home Assistant before applying. Undo by restoring the .bak created next to your DB.", foreground="gray")
    footer.grid(row=11, column=0, columnspan=4, sticky="w", pady=(8,0))

    return root

if __name__ == "__main__":
    root = build_gui()
    root.mainloop()
