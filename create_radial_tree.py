import pandas as pd
import json
import unicodedata

# -----------------------------
# Load and clean data
# -----------------------------
df = pd.read_csv("family_data.csv", sep=";", encoding="cp1252", dtype=str)


def normalize(name):
    name = str(name).strip().replace("\xa0", "")
    return "".join(
        c for c in unicodedata.normalize("NFD", name) if unicodedata.category(c) != "Mn"
    )


df.columns = [normalize(c) for c in df.columns]

# Clean ID columns
for col in ["ID", "ID_pere", "ID_mere", "ID_Conjoint"]:
    df[col] = df[col].str.strip().replace({"/": None, "?": None})
    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

# Keep prime in Gen, just strip spaces
df["Gen"] = df["Gen"].str.strip()
df["Gen_num"] = (
    pd.to_numeric(df["Gen"].str.replace("'", ""), errors="coerce").fillna(0).astype(int)
)

# -----------------------------
# Create mapping of ID to person
# -----------------------------
people = {}
for _, row in df.iterrows():
    pid = int(row["ID"])
    people[pid] = {
        "id": pid,
        "name": f"{row['Prenom']} {row['Nom']}".strip(),
        "birth": row["Naissance"] if pd.notna(row["Naissance"]) else "",
        "death": row["Deces"] if pd.notna(row["Deces"]) else "",
        "gen": row["Gen_num"],
        "father_id": int(row["ID_pere"]) if pd.notna(row["ID_pere"]) else None,
        "mother_id": int(row["ID_mere"]) if pd.notna(row["ID_mere"]) else None,
        "spouse_id": int(row["ID_Conjoint"]) if pd.notna(row["ID_Conjoint"]) else None,
    }


# -----------------------------
# Build tree structure
# -----------------------------
def build_tree_node(person_id, visited=None):
    if visited is None:
        visited = set()
    if person_id in visited:
        return None
    visited.add(person_id)

    person = people[person_id]
    node = {
        "name": person["name"],
        "id": person_id,
        "birth": person["birth"],
        "death": person["death"],
        "gen": person["gen"],
        "children": [],
        "isSpouse": False,
    }

    # Add children
    children_ids = [
        p["id"]
        for p in people.values()
        if p["father_id"] == person_id or p["mother_id"] == person_id
    ]
    for child_id in sorted(children_ids):
        child_node = build_tree_node(child_id, visited.copy())
        if child_node:
            node["children"].append(child_node)

    # Add spouse
    if person["spouse_id"] and person["spouse_id"] in people:
        spouse = people[person["spouse_id"]]
        if spouse["id"] not in visited:
            node["children"].append(
                {
                    "name": spouse["name"],
                    "id": spouse["id"],
                    "birth": spouse["birth"],
                    "death": spouse["death"],
                    "gen": spouse["gen"],
                    "children": [],
                    "isSpouse": True,
                }
            )

    return node


# -----------------------------
# Find roots
# -----------------------------
roots = [
    p["id"]
    for p in people.values()
    if p["father_id"] is None and p["mother_id"] is None
]

trees = []
for root_id in sorted(roots):
    tree = build_tree_node(root_id)
    if tree:
        trees.append(tree)

root_tree = trees[0] if trees else {"name": "Family Tree", "children": []}

# -----------------------------
# Save JSON
# -----------------------------
with open("family_tree.json", "w", encoding="utf-8") as f:
    json.dump(root_tree, f, ensure_ascii=False, indent=2)
print("✓ Created family_tree.json")


# -----------------------------
# HTML + D3 radial tree
# -----------------------------

# -----------------------------
# HTML + D3 radial tree with rotation slider and adaptive labels
# -----------------------------

html_template = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Genealogy Radial Tree</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
body { margin:0; padding:20px; font-family:Arial,sans-serif; background:#f5f5f5; display:flex; flex-direction:column; align-items:center; }
#chart { background:white; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.15); }
.tooltip { position:absolute; background:#333; color:white; padding:8px 12px; border-radius:4px; font-size:12px; pointer-events:none; display:none; z-index:1000; box-shadow:0 2px 8px rgba(0,0,0,0.3); }
.node circle { stroke-width:2px; }
.node text { font-size:12px; pointer-events:none; text-anchor:middle; dominant-baseline:middle; }
.node.dead circle { fill:white; }
.decade-ring { fill:none; stroke:#ccc; stroke-width:1px; stroke-dasharray:3,3; opacity:0.5; }
.decade-label { font-size:11px; fill:#999; pointer-events:none; }
.link { fill:none; stroke:#999; stroke-opacity:0.4; }
#slider-container { margin:20px; display:flex; align-items:center; gap:10px; font-size:14px; }
</style>
</head>
<body>

<div id="slider-container">
    <label for="rotation-slider">Rotate Tree:</label>
    <input type="range" id="rotation-slider" min="0" max="360" value="0">
</div>

<div id="chart"></div>
<div class="tooltip"></div>

<script>
const data = __DATA__;

const width = 1200;
const height = 1200;
const radius = Math.min(width, height)/2 - 80; // extra space

const svg = d3.select("#chart").append("svg").attr("width", width).attr("height", height);
const g = svg.append("g").attr("transform", `translate(${width/2},${height/2})`);
const tooltip = d3.select(".tooltip");

// Color scale by generation
const colorScale = d3.scaleOrdinal().domain([0,1,2,3,4]).range(["#FF6B6B","#4ECDC4","#45B7D1","#FFA07A","#98D8C8"]);

// Collect birth years
const birthDates = [];
function getAllPersons(node) {
    birthDates.push(node);
    if(node.children) node.children.forEach(getAllPersons);
}
getAllPersons(data);

const birthYears = birthDates.map(p => {
    if(p.birth && p.birth.trim()) {
        const parts = p.birth.trim().split('/');
        if(parts.length >= 3) return parseInt(parts[2]);
    }
    return null;
}).filter(y=>y!==null);

const minYear = Math.min(...birthYears);
const maxYear = Math.max(...birthYears);
const yearRange = maxYear - minYear || 1;

// Add decade rings
const decadeRings = g.append("g").attr("class","decade-rings");
for(let decade=Math.floor(minYear/10)*10; decade<=maxYear; decade+=10) {
    const decadeRadius = ((decade-minYear)/yearRange)*radius;
    if(decadeRadius>0 && decadeRadius<radius) {
        decadeRings.append("circle").attr("class","decade-ring").attr("r",decadeRadius);
        decadeRings.append("text").attr("class","decade-label").attr("x",0).attr("y",-decadeRadius)
            .attr("text-anchor","middle").attr("dominant-baseline","middle").text(decade);
    }
}

// Radius function
function getRadiusByBirth(birthStr) {
    if(!birthStr || !birthStr.trim()) return radius*0.5;
    const parts = birthStr.trim().split('/');
    if(parts.length >= 3) {
        const year = parseInt(parts[2]);
        if(!isNaN(year)) return ((year-minYear)/yearRange)*radius;
    }
    return radius*0.5;
}

// Tree layout
const tree = d3.tree().size([2*Math.PI,1]).separation((a,b)=>(a.parent===b.parent?2:3)/a.depth);
const root = d3.hierarchy(data);
tree(root);

// Assign radial positions and offsets
const spouseAngleDelta = 0.05;
root.each(node => {
    if(node.data.id===1 || node.data.id===2) {
        node.y = 0;
        node.xOffset = 0;
    } else {
        node.y = getRadiusByBirth(node.data.birth);
        node.xOffset = node.data.isSpouse ? spouseAngleDelta : 0;
    }
});

// Draw links
const linkElements = g.selectAll(".link").data(root.links()).join("path").attr("class","link")
    .attr("d", d3.linkRadial().angle(d=>d.x + (d.xOffset||0)).radius(d=>d.y));

// Draw nodes
const nodes = g.selectAll(".node").data(root.descendants()).join("g")
    .attr("class", d=>"node"+(d.data.death?" dead":""));

// Circle styling
nodes.append("circle")
    .attr("r", d => d.data.isSpouse ? 4.5 : (d.data.gen===0?10:(d.children?6:4.5)))
    .attr("fill","white")
    .attr("stroke", d => colorScale(d.data.gen))
    .attr("stroke-width", 2.5);

// Text
function estimateTextWidth(text,fontSize) { return text.length*fontSize*0.55+12; }
nodes.append("text")
    .attr("dy","0.31em")
    .text(d=> {
        if(d.data.id===1 || d.data.id===2) return d.data.name;
        return d.data.name.split(' ')[0];
    })
    .attr("font-weight",d=>d.data.gen===0?"bold":"normal")
    .attr("font-size",d=>d.data.gen===0?"14px":"12px");

// Tooltip
nodes.on("mouseenter", function(event,d) {
    let info=d.data.name;
    if(d.data.isSpouse) info += " (spouse)";
    info+=`<br/>Gen: ${d.data.gen}`;
    if(d.data.birth) info+=`<br/>b: ${d.data.birth}`;
    if(d.data.death) info+=`<br/>d: ${d.data.death}`;
    tooltip.html(info).style("left",(event.pageX+10)+"px").style("top",(event.pageY-10)+"px").style("display","block");
}).on("mouseleave",function(){ tooltip.style("display","none"); });


// Click to highlight descendants
nodes.on("click", function(event, d) {
    // Reset previous highlights
    nodes.select("circle").attr("stroke-width", 2.5).attr("stroke", d => colorScale(d.data.gen));
    nodes.select("text").attr("font-weight", d => d.data.gen===0 ? "bold" : "normal");
    linkElements.attr("stroke", "#999").attr("stroke-width", 1);

    // Get all descendants of the clicked node
    const descendants = d.descendants();

    // Highlight descendants
    descendants.forEach(node => {
        // Highlight node circle
        d3.select(nodes.filter(n => n === node).node()).select("circle")
            .attr("stroke-width", 4)
            .attr("stroke", "black");

        // Highlight text
        d3.select(nodes.filter(n => n === node).node()).select("text")
            .attr("font-weight", "bold");
    });

    // Highlight links connecting descendants
    linkElements
        .filter(l => descendants.includes(l.source) && descendants.includes(l.target))
        .attr("stroke", "black")   // make line black
        .attr("stroke-width", 2);  // thicker line
});

// Rotation slider
const slider = document.getElementById("rotation-slider");

function updateRotation(angleDeg) {
    const angleRad = angleDeg * Math.PI / 180;

    nodes.attr("transform", d => {
        if(d.data.gen === 0) {
            // Gen0 nodes at the center, horizontal
            return `translate(0,0)`;
        } else {
            const angle = d.x + (d.xOffset||0) + angleRad;
            return `rotate(${angle*180/Math.PI-90})translate(${d.y},0)`;
        }
    });

    linkElements.attr("d", d3.linkRadial().angle(d => d.x + (d.xOffset||0) + angleRad).radius(d => d.y));

    nodes.select("text").attr("transform", d => {
        if(d.data.id===1) return `translate(0,-28)`;
        if(d.data.id===2) return `translate(0,-12)`;
        if(d.data.gen===0) return `translate(0,-20)`; // center, horizontal

        const angle = d.x + (d.xOffset||0) + angleRad;
        const deg = angle * 180 / Math.PI - 90;

        const displayText = d.data.name.split(' ')[0];
        const fontSize = d.data.gen===0 ? 14 : 12;
        const offsetDist = estimateTextWidth(displayText,fontSize)/2;

        let x=offsetDist, y=deg>90 && deg<270 ? 4 : -4;
        let rotation = deg>90 && deg<270 ? 180 : 0;

        return `translate(${x},${y})rotate(${rotation})`;
    });
}

// Initialize
updateRotation(0);
slider.addEventListener("input", () => updateRotation(slider.value));

</script>
</body>
</html>
"""

# Insert JSON safely
html_final = html_template.replace("__DATA__", json.dumps(root_tree))

with open("family_tree.html", "w", encoding="utf-8") as f:
    f.write(html_final)

print("✓ family_tree.html created with rotation slider and adaptive labels")
