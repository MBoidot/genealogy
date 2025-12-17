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
            "role": row.get("Role"),  # <--- add this
        },
    )

    union_id = row.get("Union_ID")
    if pd.notna(union_id) and row.get("Role") == "parent":
        people[pid]["unions"][union_id] = {
            "union_id": union_id,  # <<< add this line
            "spouse_id": (
                int(row["ID_Conjoint"]) if pd.notna(row.get("ID_Conjoint")) else None
            ),
            "remark": row.get("Remark", ""),
            "children": [],
        }

# -----------------------------
# Populate children in unions
# -----------------------------
for _, row in df.iterrows():
    if row.get("Role") != "child":
        continue

    pid = int(row["ID"])
    union_id = row.get("Union_ID")

    for parent_id in [row.get("ID_pere"), row.get("ID_mere")]:
        if pd.notna(parent_id):
            parent_id = int(parent_id)
            if union_id in people[parent_id]["unions"]:
                people[parent_id]["unions"][union_id]["children"].append(pid)


# -----------------------------
# Recursive tree builder
# -----------------------------
def build_node(pid, visited=None):
    if visited is None:
        visited = set()
    if pid in visited:
        return None
    visited.add(pid)

    person = people.get(pid)
    if person is None:
        return None

    node = {
        "id": pid,
        "name": person["name"],
        "birth": person["birth"],
        "death": person["death"],
        "gen": person["gen"],
        "gen_origin": person["gen_origin"],
        "children": [],
    }

    unions = list(person.get("unions", {}).values())
    base_delta = 0.08

    for i, union in enumerate(unions):
        remark = (union.get("remark") or "").lower()

        if "current" in remark:
            union_type = "current"
        elif "former" in remark:
            union_type = "former"
        elif "single_parent" in remark:
            union_type = "single_parent"
        else:
            union_type = "other"

        # -----------------------------
        # Build children
        # -----------------------------
        children_nodes = []
        for child_id in union.get("children", []):
            child_node = build_node(child_id, visited.copy())
            if child_node:
                child_node["union_type"] = union_type
                children_nodes.append(child_node)

        if not children_nodes:
            continue

        offset = (i - (len(unions) - 1) / 2) * base_delta
        spouse_id = union.get("spouse_id")

        # -----------------------------
        # UNION NODE (always)
        # -----------------------------
        if spouse_id and spouse_id in people:
            sp = people[spouse_id]
            union_node = {
                "id": f"{pid}_union_{union['union_id']}",
                "name": sp["name"],
                "birth": sp["birth"],
                "death": sp["death"],
                "gen": sp["gen"],
                "gen_origin": sp["gen_origin"],
                "children": children_nodes,
                "isSpouse": True,
                "union_type": union_type,
                "xOffset": offset,
            }
        else:
            # ✅ SINGLE-PARENT UNION ANCHOR
            union_node = {
                "id": f"{pid}_union_{union['union_id']}",
                "name": "",  # invisible anchor
                "children": children_nodes,
                "isSpouse": True,
                "isSingleParent": True,
                "union_type": union_type,
                "xOffset": offset,
            }

        node["children"].append(union_node)

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

# -----------------------------
# Generate final HTML
# -----------------------------
with open("template.html", "r", encoding="utf-8") as f:
    html_template = f.read()

json_data = json.dumps(root_tree, ensure_ascii=False)

html_output = html_template.replace("__DATA__", json_data.replace("`", "\\`"))

with open("family_tree_with_unions.html", "w", encoding="utf-8") as f:
    f.write(html_output)

print("✓ HTML generated")
