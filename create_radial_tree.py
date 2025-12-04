import pandas as pd
import json
import unicodedata

# Load and clean data
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

# Clean Gen column (remove apostrophes and non-breaking spaces)
df["Gen"] = df["Gen"].str.replace("'", "").str.replace("\xa0", "").str.strip()
df["Gen"] = pd.to_numeric(df["Gen"], errors="coerce").fillna(0).astype(int)

# Create a mapping of ID to person
people = {}
for _, row in df.iterrows():
    pid = int(row["ID"])
    people[pid] = {
        "id": pid,
        "name": f"{row['Prenom']} {row['Nom']}".strip(),
        "birth": row["Naissance"] if pd.notna(row["Naissance"]) else "",
        "death": row["Deces"] if pd.notna(row["Deces"]) else "",
        "gen": row["Gen"],
        "father_id": int(row["ID_pere"]) if pd.notna(row["ID_pere"]) else None,
        "mother_id": int(row["ID_mere"]) if pd.notna(row["ID_mere"]) else None,
        "spouse_id": int(row["ID_Conjoint"]) if pd.notna(row["ID_Conjoint"]) else None,
    }


# Build tree structure (nested JSON)
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
    }

    # Find children
    children_ids = [
        p["id"]
        for p in people.values()
        if (p["father_id"] == person_id or p["mother_id"] == person_id)
    ]

    for child_id in sorted(children_ids):
        child_node = build_tree_node(child_id, visited.copy())
        if child_node:
            node["children"].append(child_node)

    return node


# Find roots (people without parents)
roots = [
    p["id"]
    for p in people.values()
    if p["father_id"] is None and p["mother_id"] is None
]

# Build trees for each root
trees = []
for root_id in sorted(roots):
    tree = build_tree_node(root_id)
    if tree:
        trees.append(tree)

# Use the first tree or combine them
if trees:
    root_tree = trees[0]
else:
    root_tree = {"name": "Family Tree", "children": []}

# Save as JSON
with open("family_tree.json", "w", encoding="utf-8") as f:
    json.dump(root_tree, f, ensure_ascii=False, indent=2)

print("✓ Created family_tree.json")

# Update HTML with new data
html_template = (
    """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Genealogy Radial Tree</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        #chart {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        .tooltip {
            position: absolute;
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            display: none;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        .node circle {
            stroke-width: 2px;
        }
        .node text {
            font-size: 12px;
            pointer-events: none;
            text-anchor: middle;
            dominant-baseline: middle;
        }
        .node.dead circle {
            fill: white;
        }
        .decade-ring {
            fill: none;
            stroke: #ccc;
            stroke-width: 1px;
            stroke-dasharray: 3,3;
            opacity: 0.5;
        }
        .decade-label {
            font-size: 11px;
            fill: #999;
            pointer-events: none;
        }
        .link {
            fill: none;
            stroke: #999;
            stroke-opacity: 0.4;
        }
    </style>
</head>
<body>
    <div id="chart"></div>
    <div class="tooltip"></div>

    <script>
        // Data injected by Python script
        const data = """
    + json.dumps(root_tree)
    + """;

        const width = 1200;
        const height = 1200;
        const radius = Math.min(width, height) / 2 - 40;

        const svg = d3.select("#chart").append("svg")
            .attr("width", width)
            .attr("height", height);

        const g = svg.append("g")
            .attr("transform", `translate(${width / 2}, ${height / 2})`);

        const tooltip = d3.select(".tooltip");

        // Color scale by generation
        const colorScale = d3.scaleOrdinal()
            .domain([0, 1, 2, 3, 4])
            .range(["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]);

        // Parse birth dates and calculate radius by birth year
        const birthDates = [];
        const getAllPersons = (node) => {
            birthDates.push(node);
            node.children.forEach(getAllPersons);
        };
        getAllPersons(data);
        
        const birthYears = birthDates
            .map(p => {
                if (p.birth && p.birth.trim()) {
                    const parts = p.birth.trim().split('/');
                    if (parts.length >= 3) return parseInt(parts[2]);
                }
                return null;
            })
            .filter(y => y !== null);
        
        const minYear = Math.min(...birthYears);
        const maxYear = Math.max(...birthYears);
        const yearRange = maxYear - minYear || 1;
        
        // Add decade rings and vertical axis labels
        const decadeRings = g.append("g").attr("class", "decade-rings");
        
        for (let decade = Math.floor(minYear / 10) * 10; decade <= maxYear; decade += 10) {
            const decadeRadius = ((decade - minYear) / yearRange) * radius;
            if (decadeRadius > 0 && decadeRadius < radius) {
                decadeRings.append("circle")
                    .attr("class", "decade-ring")
                    .attr("r", decadeRadius);
                
                // Label on vertical axis (top), centered on the circle
                decadeRings.append("text")
                    .attr("class", "decade-label")
                    .attr("x", 0)
                    .attr("y", -decadeRadius)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "middle")
                    .text(decade);
            }
        }
        
        // Function to get radius by birth year
        const getRadiusByBirth = (birthStr) => {
            if (!birthStr || !birthStr.trim()) return radius * 0.5;
            const parts = birthStr.trim().split('/');
            if (parts.length >= 3) {
                const year = parseInt(parts[2]);
                if (!isNaN(year)) {
                    return ((year - minYear) / yearRange) * radius;
                }
            }
            return radius * 0.5;
        };

        // Create tree layout
        const tree = d3.tree()
            .size([2 * Math.PI, 1])
            .separation((a, b) => (a.parent === b.parent ? 2 : 3) / a.depth);

        const root = d3.hierarchy(data);
        tree(root);
        
        // Scale positions by birth year radius
        root.each(node => {
            node.y = getRadiusByBirth(node.data.birth);
        });

        // Draw links
        g.selectAll(".link")
            .data(root.links())
            .join("path")
            .attr("class", "link")
            .attr("d", d3.linkRadial()
                .source(d => [d.source.x, d.source.y])
                .target(d => [d.target.x, d.target.y]));

        // Draw nodes
        const nodes = g.selectAll(".node")
            .data(root.descendants())
            .join("g")
            .attr("class", d => "node" + (d.data.death ? " dead" : ""))
            .attr("transform", d => `rotate(${d.x * 180 / Math.PI - 90})translate(${d.y},0)`);

        nodes.append("circle")
            .attr("r", d => d.data.gen === 0 ? 10 : (d.children ? 6 : 4.5))
            .attr("fill", "white")
            .attr("stroke", d => d.data.death ? "#999" : colorScale(d.data.gen))
            .attr("stroke-width", 2.5);

        // Function to estimate text width for dynamic offset calculation
        const estimateTextWidth = (text, fontSize) => {
            const charWidth = fontSize * 0.55;
            return text.length * charWidth + 12;
        };

        nodes.append("text")
            .attr("dy", "0.31em")
            .text(d => {
                if (d.data.gen === 0) return d.data.name;
                return d.data.name.split(' ')[0];
            })
            .attr("text-anchor", "middle")
            .attr("font-weight", d => d.data.gen === 0 ? "bold" : "normal")
            .attr("font-size", d => d.data.gen === 0 ? "14px" : "12px")
            .attr("transform", d => {
                if (d.data.gen === 0) {
                    const parentRotation = d.x * 180 / Math.PI - 90;
                    return `rotate(${-parentRotation})translate(0,-20)`;
                }
                const displayText = d.data.name.split(' ')[0];
                const fontSize = 12;
                const offsetDist = estimateTextWidth(displayText, fontSize) / 2;
                const rotation = d.x > Math.PI ? 180 : 0;
                const yOffset = rotation === 0 ? -4 : 4;
                return `translate(${offsetDist},${yOffset})rotate(${rotation})`;
            })
            .style("font-size", d => d.data.gen === 0 ? "14px" : "12px")
            .style("font-weight", d => d.data.gen === 0 ? "bold" : "normal");

        // Add interactivity
        nodes.on("mouseenter", function(event, d) {
            let info = d.data.name;
            info += `<br/>Gen: ${d.data.gen}`;
            if (d.data.birth) info += `<br/>b: ${d.data.birth}`;
            if (d.data.death) info += `<br/>d: ${d.data.death}`;
            
            tooltip.html(info)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px")
                .style("display", "block");
        })
        .on("mouseleave", function() {
            tooltip.style("display", "none");
        });
        
    </script>
</body>
</html>
"""
)

with open("family_tree.html", "w", encoding="utf-8") as f:
    f.write(html_template)

print("✓ Updated family_tree.html")
