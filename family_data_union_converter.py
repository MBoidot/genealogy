import pandas as pd
import unicodedata
import os
import re

# -----------------------------
# Load CSV automatically
# -----------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, "family_data.csv")

if not os.path.exists(file_path):
    raise FileNotFoundError(f"{file_path} not found.")

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

# -----------------------------
# Keep original parent IDs
# -----------------------------
df["ID_pere_original"] = df.get("ID_pere", "").copy()
df["ID_mere_original"] = df.get("ID_mere", "").copy()


# Extract digits only for tree construction
def digits_only_series(s):
    s = s.fillna("").astype(str).str.strip()
    digits = s.str.extract(r"(\d+)")[0]
    return pd.to_numeric(digits, errors="coerce")


df["ID_pere"] = digits_only_series(df["ID_pere"])
df["ID_mere"] = digits_only_series(df["ID_mere"])
df["ID_Conjoint"] = digits_only_series(df["ID_Conjoint"])
df["ID"] = digits_only_series(df["ID"])

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

# From children (two parents)
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


def get_children(p1, p2):
    """Return children with digit-only parent IDs"""
    return df[
        ((df["ID_pere"] == p1) & (df["ID_mere"] == p2))
        | ((df["ID_pere"] == p2) & (df["ID_mere"] == p1))
    ]


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
    children = get_children(p1, p2)

    # --- Parents ---
    for pid, spouse_id in [(p1, p2), (p2, p1)]:
        parent = people.get(pid)
        if parent is None:
            continue
        r = parent.to_dict()
        r["ID_Conjoint"] = spouse_id
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
# Single-parent unions
# -----------------------------
single_union_counter = 10000

for _, row in df.iterrows():
    cid = row.get("ID")
    if not is_valid(cid):
        continue

    father = row.get("ID_pere")
    mother = row.get("ID_mere")

    # exactly ONE known parent
    parent_ids = [p for p in [father, mother] if is_valid(p)]
    if len(parent_ids) != 1:
        continue

    parent_id = int(parent_ids[0])
    child_id = int(cid)

    union_id = f"US{single_union_counter}"
    single_union_counter += 1

    # --- Parent row ---
    parent = people.get(parent_id)
    if parent is not None:
        r = parent.to_dict()
        r["Union_ID"] = union_id
        r["Role"] = "parent"
        r["Remark"] = "single_parent"
        r["ID_Conjoint"] = None
        rows.append(r)

    # --- Child row ---
    c = row.to_dict()
    c["Union_ID"] = union_id
    c["Role"] = "child"
    c["Remark"] = "single_parent"
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
    remark = (
        "no_parents"
        if not is_valid(row.get("ID_pere")) and not is_valid(row.get("ID_mere"))
        else "single_parent"
    )
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
df_expanded["Gen"] = (
    df_expanded["Gen_Origin"].str.extract(r"(\d+)").astype(float).fillna(0).astype(int)
)

# -----------------------------
# Export
# -----------------------------
export_filename = "family_data_roles_union.csv"
export_path = os.path.join(script_dir, export_filename)

df_expanded.to_csv(export_path, sep=";", index=False, encoding="utf-8-sig")

print(f"✓ Expanded CSV saved to {export_path}")
