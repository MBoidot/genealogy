import pandas as pd
import json
import unicodedata

# -----------------------------
# Load CSV
# -----------------------------
df = pd.read_csv(
    "family_data_roles_union.csv", sep=";", encoding="utf-8-sig", dtype=str
)


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
# Clean IDs
# -----------------------------
for col in ["ID", "ID_pere", "ID_mere", "ID_Conjoint"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# -----------------------------
# Build people dictionary
# -----------------------------
people = {}

for _, row in df.iterrows():
    pid = int(row["ID"])

    people.setdefault(
        pid,
        {
            "id": pid,
            "name": f"{row['Prenom']} {row['Nom']}".strip(),
            "birth": row["Naissance"] if pd.notna(row["Naissance"]) else "",
            "death": row["Deces"] if pd.notna(row["Deces"]) else "",
            "gen_origin": row.get("Gen_Origin", row.get("Gen", "")),
            "gen": (
                int(row["Gen"].replace("'", "").strip()) if pd.notna(row["Gen"]) else 0
            ),
            "father_id": int(row["ID_pere"]) if pd.notna(row["ID_pere"]) else None,
            "mother_id": int(row["ID_mere"]) if pd.notna(row["ID_mere"]) else None,
            "unions": {},
        },
    )

    union_id = row.get("Union_ID")
    if pd.notna(union_id):
        people[pid]["unions"][union_id] = {
            "role": row.get("Role"),
            "remark": row.get("Remark"),
            "spouse_id": (
                int(row["ID_Conjoint"]) if pd.notna(row["ID_Conjoint"]) else None
            ),
            "children": [],
        }

# -----------------------------
# Populate children in unions
# -----------------------------
for _, row in df.iterrows():
    if row.get("Role") != "child" or pd.isna(row.get("Union_ID")):
        continue

    child_id = int(row["ID"])
    union_id = row["Union_ID"]

    for parent_id in [
        int(row["ID_pere"]) if pd.notna(row["ID_pere"]) else None,
        int(row["ID_mere"]) if pd.notna(row["ID_mere"]) else None,
    ]:
        if parent_id and union_id in people[parent_id]["unions"]:
            people[parent_id]["unions"][union_id]["children"].append(child_id)


# -----------------------------
# Recursive tree builder
# -----------------------------
def build_node(pid, visited=None):
    if visited is None:
        visited = set()
    if pid in visited:
        return None
    visited.add(pid)

    person = people[pid]

    node = {
        "id": pid,
        "name": person["name"],
        "birth": person["birth"],
        "death": person["death"],
        "gen": person["gen"],
        "gen_origin": person["gen_origin"],
        "children": [],
    }

    # Only unions where THIS person is a parent
    parent_unions = {
        uid: u for uid, u in person["unions"].items() if u["role"] == "parent"
    }

    num_unions = len(parent_unions)
    base_delta = 0.08

    for i, (union_id, union) in enumerate(parent_unions.items()):
        union_type = (
            "current"
            if union.get("remark") and "current" in union["remark"].lower()
            else "former"
        )

        # --- children ---
        children_nodes = []
        for child_id in union["children"]:
            child_node = build_node(child_id, visited.copy())
            if child_node:
                child_node["union_type"] = union_type
                children_nodes.append(child_node)

        # --- spouse ---
        spouse_id = union.get("spouse_id")
        offset = (i - (num_unions - 1) / 2) * base_delta

        if spouse_id and spouse_id in people:
            spouse = people[spouse_id]

            spouse_node = {
                "id": f"{pid}_{union_id}_{spouse_id}",  # union-specific
                "name": spouse["name"],
                "birth": spouse["birth"],
                "death": spouse["death"],
                "gen": spouse["gen"],
                "gen_origin": spouse["gen_origin"],
                "children": children_nodes,
                "isSpouse": True,
                "union_type": union_type,
                "xOffset": offset,
            }
            node["children"].append(spouse_node)

        elif children_nodes:
            # real unknown spouse (only if truly missing)
            node["children"].append(
                {
                    "id": f"{pid}_{union_id}_unknown",
                    "name": "(unknown spouse)",
                    "birth": "",
                    "death": "",
                    "gen": person["gen"],
                    "gen_origin": person["gen_origin"],
                    "children": children_nodes,
                    "isSpouse": True,
                    "union_type": union_type,
                    "xOffset": offset,
                }
            )

    return node


# -----------------------------
# Identify roots
# -----------------------------
roots = [
    pid
    for pid, p in people.items()
    if p["father_id"] is None and p["mother_id"] is None
]

trees = [build_node(pid) for pid in sorted(roots)]
root_tree = trees[0] if trees else {"name": "Family Tree", "children": []}

# -----------------------------
# Export JSON
# -----------------------------
with open("family_tree_with_unions.json", "w", encoding="utf-8") as f:
    json.dump(root_tree, f, ensure_ascii=False, indent=2)

with open("template.html", "r", encoding="utf-8") as f:
    html_template = f.read()

html_output = html_template.replace(
    "__DATA__", json.dumps(root_tree, ensure_ascii=False).replace("`", "\\`")
)

with open("family_tree_with_unions.html", "w", encoding="utf-8") as f:
    f.write(html_output)

print("✓ Created family_tree_with_unions.html")
