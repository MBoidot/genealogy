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
    # Track each union
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
    union_id = row.get("Union_ID")
    if pd.isna(union_id) or row.get("Role") != "child":
        continue
    pid = int(row["ID"])
    father_id = int(row["ID_pere"]) if pd.notna(row["ID_pere"]) else None
    mother_id = int(row["ID_mere"]) if pd.notna(row["ID_mere"]) else None
    for parent_id in [father_id, mother_id]:
        if parent_id and union_id in people[parent_id]["unions"]:
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

    for union in person["unions"].values():
        if union["role"] != "parent":
            continue
        union_type = (
            "current" if "current" in (union.get("remark") or "").lower() else "former"
        )
        for child_id in union["children"]:
            child_node = build_node(child_id, visited.copy())
            if child_node:
                # mark link type
                child_node["union_type"] = union_type
                node["children"].append(child_node)
        # Add spouse node
        spouse_id = union.get("spouse_id")
        if spouse_id and spouse_id in people:
            node["children"].append(
                {
                    "id": spouse_id,
                    "name": people[spouse_id]["name"],
                    "birth": people[spouse_id]["birth"],
                    "death": people[spouse_id]["death"],
                    "gen": people[spouse_id]["gen"],
                    "gen_origin": people[spouse_id]["gen_origin"],
                    "children": [],
                    "isSpouse": True,
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
trees = [build_node(root_id) for root_id in sorted(roots)]
root_tree = trees[0] if trees else {"name": "Family Tree", "children": []}

# -----------------------------
# Export JSON
# -----------------------------
with open("family_tree_with_unions.json", "w", encoding="utf-8") as f:
    json.dump(root_tree, f, ensure_ascii=False, indent=2)

# -----------------------------
# Generate HTML directly
# -----------------------------
html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Genealogy Radial Tree with Unions</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
#chart {{ width: 1200px; height: 1200px; margin: auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
.node circle {{ stroke-width: 2px; fill: white; }}
.node text {{ font-size: 12px; text-anchor: middle; dominant-baseline: middle; pointer-events: none; }}
.link {{ fill: none; stroke: #999; stroke-opacity: 0.5; }}
.link.former {{ stroke-dasharray: 4 2; }}
.tooltip {{ position: absolute; background: #333; color: white; padding: 6px 10px; border-radius: 4px; font-size: 12px; pointer-events: none; display: none; }}
</style>
</head>
<body>

<div id="chart"></div>
<div class="tooltip"></div>

<script>
const data = {json.dumps(root_tree)};

const width = 1200;
const height = 1200;
const radius = Math.min(width, height)/2 - 80;

const svg = d3.select("#chart")
    .append("svg")
    .attr("width", width)
    .attr("height", height);

const g = svg.append("g")
    .attr("transform", `translate(${{width/2}},${{height/2}})`);

const tooltip = d3.select(".tooltip");

const tree = d3.tree().size([2*Math.PI, radius]);
const root = d3.hierarchy(data, d => d.children);
tree(root);

// Links
g.selectAll(".link")
    .data(root.links())
    .join("path")
    .attr("class", d => "link" + (d.target.data.union_type === "former" ? " former" : ""))
    .attr("d", d3.linkRadial().angle(d => d.x).radius(d => d.y));

// Nodes
const nodes = g.selectAll(".node")
    .data(root.descendants())
    .join("g")
    .attr("class", "node")
    .attr("transform", d => `rotate(${{d.x * 180 / Math.PI - 90}}) translate(${{d.y}},0)`);

nodes.append("circle")
    .attr("r", d => d.data.isSpouse ? 4 : 6)
    .attr("stroke", "steelblue")
    .attr("stroke-width", 2);

nodes.append("text")
    .attr("dy", "0.31em")
    .text(d => d.data.name.split(' ')[0]);

// Tooltip
nodes.on("mouseenter", function(event,d){{
    tooltip.html(
        `<strong>${{d.data.name}}</strong><br/>
         Gen: ${{d.data.gen_origin}}<br/>
         Birth: ${{d.data.birth || ""}}<br/>
         Death: ${{d.data.death || ""}}`
    )
    .style("display","block")
    .style("left", (event.pageX+10)+"px")
    .style("top", (event.pageY-10)+"px");
}}).on("mouseleave", function(){{
    tooltip.style("display","none");
}});
</script>

</body>
</html>
"""


with open("family_tree_with_unions.html", "w", encoding="utf-8") as f:
    f.write(html_template)

print("✓ Created family_tree_with_unions.html with current/former union distinction")
