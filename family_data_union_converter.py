import pandas as pd
import unicodedata
import tkinter as tk
from tkinter import filedialog
import os
import re

# -----------------------------
# Select CSV file
# -----------------------------
root = tk.Tk()
root.withdraw()

file_path = filedialog.askopenfilename(
    title="Select family CSV file", filetypes=[("CSV files", "*.csv")]
)
if not file_path:
    raise SystemExit("No file selected.")

# -----------------------------
# Load CSV
# -----------------------------
df = pd.read_csv(file_path, sep=";", encoding="cp1252", dtype=str)


# -----------------------------
# Normalize column names
# -----------------------------
def normalize(name):
    name = str(name).strip().replace("\xa0", "")
    return "".join(
        c for c in unicodedata.normalize("NFD", name) if unicodedata.category(c) != "Mn"
    )


df.columns = [normalize(c) for c in df.columns]

# -----------------------------
# Clean ID columns
# -----------------------------
ID_COLS = ["ID", "ID_pere", "ID_mere", "ID_Conjoint"]

for col in ID_COLS:
    if col in df.columns:
        df[col] = (
            df[col].astype(str).str.strip().replace({"/": None, "?": None, "nan": None})
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Ensure Note exists
if "Note" not in df.columns:
    df["Note"] = ""


# -----------------------------
# Helpers
# -----------------------------
def is_valid(x):
    return x is not None and not pd.isna(x)


people = {int(row["ID"]): row for _, row in df.iterrows() if is_valid(row.get("ID"))}

# -----------------------------
# Detect unions
# -----------------------------
union_map = {}
union_counter = 1

# From children
for _, row in df.iterrows():
    p = row.get("ID_pere")
    m = row.get("ID_mere")
    if is_valid(p) and is_valid(m):
        key = tuple(sorted([int(p), int(m)]))
        if key not in union_map:
            union_map[key] = f"U{union_counter}"
            union_counter += 1

# From explicit spouses
for _, row in df.iterrows():
    pid = row.get("ID")
    cid = row.get("ID_Conjoint")
    if is_valid(pid) and is_valid(cid):
        key = tuple(sorted([int(pid), int(cid)]))
        if key not in union_map:
            union_map[key] = f"U{union_counter}"
            union_counter += 1

# -----------------------------
# Expand table
# -----------------------------
expanded_cols = list(df.columns) + ["Union_ID", "Role", "Remark"]
rows = []

for (p1, p2), union_id in union_map.items():
    p1 = int(p1)
    p2 = int(p2)

    p1_row = people.get(p1)
    p2_row = people.get(p2)

    # Determine current vs former
    is_current = (
        p1_row is not None
        and p2_row is not None
        and is_valid(p1_row.get("ID_Conjoint"))
        and is_valid(p2_row.get("ID_Conjoint"))
        and int(p1_row["ID_Conjoint"]) == p2
        and int(p2_row["ID_Conjoint"]) == p1
    )

    union_status = "current_union" if is_current else "former_union"

    # Children
    children = df[
        ((df["ID_pere"] == p1) & (df["ID_mere"] == p2))
        | ((df["ID_pere"] == p2) & (df["ID_mere"] == p1))
    ]

    # --- Parents ---
    for pid, spouse_id in [(p1, p2), (p2, p1)]:
        parent = people.get(pid)
        if parent is None:
            continue

        r = parent.to_dict()
        r["ID_Conjoint"] = spouse_id  # ✅ CRITICAL FIX
        r["Union_ID"] = union_id
        r["Role"] = "parent"
        r["Remark"] = union_status if len(children) else "union_no_children"
        rows.append(r)

    # --- Children ---
    for _, child in children.iterrows():
        c = child.to_dict()
        c["Union_ID"] = union_id
        c["Role"] = "child"
        c["Remark"] = "child"
        rows.append(c)

# -----------------------------
# Singles
# -----------------------------
used_ids = {int(r["ID"]) for r in rows if is_valid(r.get("ID"))}

for _, row in df.iterrows():
    pid = row.get("ID")
    if not is_valid(pid) or int(pid) in used_ids:
        continue

    r = row.to_dict()
    if not is_valid(row.get("ID_pere")) and not is_valid(row.get("ID_mere")):
        remark = "no_parents"
    else:
        remark = "single_parent"

    r.update({"Union_ID": "", "Role": "single", "Remark": remark})
    rows.append(r)

# -----------------------------
# Finalize dataframe
# -----------------------------
df_expanded = pd.DataFrame(rows, columns=expanded_cols).drop_duplicates()

# -----------------------------
# Gen / Gen_Origin
# -----------------------------
df_expanded["Gen_Origin"] = df_expanded["Gen"].astype(str).str.strip()


def extract_gen(val):
    if pd.isna(val):
        return 0
    m = re.search(r"\d+", str(val))
    return int(m.group()) if m else 0


df_expanded["Gen"] = df_expanded["Gen_Origin"].apply(extract_gen)

# -----------------------------
# Export
# -----------------------------
export_filename = "family_data_roles_union.csv"
script_dir = os.path.dirname(os.path.abspath(__file__))
export_path = os.path.join(script_dir, export_filename)

df_expanded.to_csv(export_path, sep=";", index=False, encoding="utf-8-sig")

print(f"✓ Expanded CSV saved to {export_path}")
