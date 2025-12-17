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
# Clean numeric IDs
# -----------------------------
for col in ["ID", "ID_pere", "ID_mere", "ID_Conjoint"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# -----------------------------
# Build people registry
# -----------------------------
people = {}
for _, row in df.iterrows():
    if pd.isna(row["ID"]):
        continue

    pid = int(row["ID"])
    people.setdefault(
        pid,
        {
            "id": pid,
            "name": f"{row.get('Prenom','')} {row.get('Nom','')}".strip(),
            "birth": row.get("Naissance", ""),
            "death": row.get("Deces", ""),
            "gen": int(row["Gen"].replace("'", "")) if pd.notna(row.get("Gen")) else 0,
            "gen_origin": row.get("Gen_Origin", ""),
            "father_id": int(row["ID_pere"]) if pd.notna(row.get("ID_pere")) else None,
            "mother_id": int(row["ID_mere"]) if pd.notna(row.get("ID_mere")) else None,
            "unions": {},
        },
    )

    # Register union ONLY for parents
    if row.get("Role") == "parent" and pd.notna(row.get("Union_ID")):
        uid = row["Union_ID"]
        people[pid]["unions"].setdefault(
            uid,
            {
                "union_id": uid,
                "spouse_id": (
                    int(row["ID_Conjoint"])
                    if pd.notna(row.get("ID_Conjoint"))
                    else None
                ),
                "remark": row.get("Remark", ""),
                "children": [],
            },
        )

# -----------------------------
# Attach children to unions
# -----------------------------
for _, row in df.iterrows():
    if row.get("Role") != "child":
        continue
    if pd.isna(row["ID"]) or pd.isna(row["Union_ID"]):
        continue

    cid = int(row["ID"])
    uid = row["Union_ID"]

    for parent_col in ["ID_pere", "ID_mere"]:
        if pd.notna(row.get(parent_col)):
            pid = int(row[parent_col])
            if pid in people and uid in people[pid]["unions"]:
                people[pid]["unions"][uid]["children"].append(cid)

# -----------------------------
# Detect former-union children
# -----------------------------
former_union_children = []
for cid, child_row in df[df["Role"] == "child"].iterrows():
    # Count parents who have this child in a union
    parent_ids = [
        int(child_row[c]) for c in ["ID_pere", "ID_mere"] if pd.notna(child_row[c])
    ]
    if len(parent_ids) == 1:
        pid = parent_ids[0]
        name = f"{child_row.get('Prenom','')} {child_row.get('Nom','')}".strip()
        former_union_children.append((pid, name, int(child_row["ID"])))

if former_union_children:
    print("⚡ Former-union children to reattach:")
    for pid, name, cid in former_union_children:
        print(f"Parent: {people[pid]['name']} (ID {pid}) → Child: {name}")

# -----------------------------
# Recursive tree builder
# -----------------------------
visited_global = set()  # global to prevent skipping children


def build_node(pid):
    if pid in visited_global:
        return None
    visited_global.add(pid)

    person = people.get(pid)
    if not person:
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

    unions = list(person["unions"].values())
    base_delta = 0.08

    for i, union in enumerate(unions):
        remark = (union["remark"] or "").lower()
        union_type = (
            "single_parent"
            if "single_parent" in remark
            else (
                "former"
                if "former" in remark
                else "union_no_children" if "union_no_children" in remark else "current"
            )
        )

        # Build children
        children_nodes = []
        for cid in union["children"]:
            child_node = build_node(cid)
            if child_node:
                child_node["union_type"] = union_type
                children_nodes.append(child_node)

        offset = (i - (len(unions) - 1) / 2) * base_delta
        spouse_id = union.get("spouse_id")

        # Build spouse / union node
        if spouse_id and spouse_id in people:
            sp = people[spouse_id]
            union_node = {
                "id": f"{pid}_{union['union_id']}",
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
            union_node = {
                "id": f"{pid}_{union['union_id']}",
                "name": "",
                "children": children_nodes,
                "isSpouse": True,
                "isSingleParent": True,
                "union_type": union_type,
                "xOffset": offset,
            }

        node["children"].append(union_node)

    return node


# -----------------------------
# Attach former-union children
# -----------------------------
for pid, name, cid in former_union_children:
    person = people[pid]
    if not person["unions"]:
        continue
    # Attach to first union that has a spouse
    for union in person["unions"].values():
        if union.get("spouse_id"):
            if cid not in union["children"]:
                union["children"].append(cid)
                print(
                    f"🔹 Attaching former-union child {name} to union of {person['name']}"
                )
            break

# -----------------------------
# Identify roots
# -----------------------------
roots = [
    pid
    for pid, p in people.items()
    if p["father_id"] is None and p["mother_id"] is None
]

trees = []
for pid in sorted(roots):
    n = build_node(pid)  # call build_node only once per root
    if n:
        trees.append(n)

root_tree = trees[0] if trees else {"name": "Family Tree", "children": []}

# -----------------------------
# Export JSON
# -----------------------------
with open("family_tree_with_unions.json", "w", encoding="utf-8") as f:
    json.dump(root_tree, f, ensure_ascii=False, indent=2)

# -----------------------------
# Generate HTML
# -----------------------------
with open("template.html", "r", encoding="utf-8") as f:
    html_template = f.read()

html_output = html_template.replace(
    "__DATA__", json.dumps(root_tree, ensure_ascii=False).replace("`", "\\`")
)

with open("family_tree_with_unions.html", "w", encoding="utf-8") as f:
    f.write(html_output)

print("✓ HTML generated correctly")
