import os
import pandas as pd
from dash import Dash, html, dcc, Input, Output
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

DATA_FILE = "family_data_roles_union.csv"
PHOTO_FOLDER = "photos"

# ============================================================
# SAFE ID CLEANER
# ============================================================


def clean_id(x):
    return str(x).replace(".0", "").strip()


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(DATA_FILE, sep=";", dtype=str, encoding="utf-8-sig")

df.columns = [c.strip() for c in df.columns]

df = df.fillna("")
df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)

# Normalize IDs
for col in ["ID", "ID_pere", "ID_mere", "ID_Conjoint"]:
    if col in df.columns:
        df[col] = df[col].apply(clean_id)

# ============================================================
# PEOPLE TABLE
# ============================================================

people_df = df.drop_duplicates(subset=["ID"])


def clean_gen(g):
    try:
        return int(str(g).replace("'", "").strip())
    except:
        return -1


people_df["GEN_CLEAN"] = people_df["Gen"].apply(clean_gen)

visible_df = people_df[people_df["GEN_CLEAN"].isin([0, 1])]

# ============================================================
# LOOKUP DICTIONARY (INCLUDES NOTE NOW)
# ============================================================

people = {}

for _, row in people_df.iterrows():
    pid = clean_id(row["ID"])

    people[pid] = {
        "id": pid,
        "prenom": row.get("Prenom", ""),
        "nom": row.get("Nom", ""),
        "name": f"{row.get('Prenom', '')} {row.get('Nom', '')}".strip(),
        "birth": row.get("Naissance", ""),
        "death": row.get("Deces", ""),
        "gen": row.get("Gen", ""),
        "gen_origin": row.get("Gen_Origin", ""),
        "father_id": clean_id(row.get("ID_pere", "")),
        "mother_id": clean_id(row.get("ID_mere", "")),
        "spouse_id": clean_id(row.get("ID_Conjoint", "")),
        "note": row.get("Note", ""),  # ✅ ADDED HERE
        "remark": row.get("Remark", ""),
    }


def get_person_name(pid):
    return people.get(clean_id(pid), {}).get("name", "")


# ============================================================
# DASH APP
# ============================================================

app = Dash(__name__)

# ============================================================
# DROPDOWN
# ============================================================

person_options = []

for _, row in visible_df.sort_values(["GEN_CLEAN", "Nom", "Prenom"]).iterrows():
    pid = clean_id(row["ID"])
    label = f"Gen {row['GEN_CLEAN']} — {row['Prenom']} {row['Nom']}"

    person_options.append({"label": label, "value": pid})

# ============================================================
# LAYOUT
# ============================================================

app.layout = html.Div(
    [
        html.H1(
            "Famille — Fiches Personnages",
            style={"textAlign": "center", "marginBottom": "30px"},
        ),
        html.Div(
            [
                html.Label("Choisir une personne :"),
                dcc.Dropdown(
                    id="person-dropdown",
                    options=person_options,
                    value=person_options[0]["value"] if person_options else None,
                    clearable=False,
                    style={"width": "600px"},
                ),
            ],
            style={
                "display": "flex",
                "flexDirection": "column",
                "alignItems": "center",
                "marginBottom": "40px",
            },
        ),
        html.Div(id="profile-card"),
    ],
    style={
        "fontFamily": "Arial",
        "padding": "30px",
        "backgroundColor": "#f4f4f4",
        "minHeight": "100vh",
    },
)

# ============================================================
# CALLBACK
# ============================================================


@app.callback(Output("profile-card", "children"), Input("person-dropdown", "value"))
def update_profile(person_id):

    if not person_id:
        return html.Div("Personne introuvable")

    person_id = clean_id(person_id)

    if person_id not in people:
        return html.Div(f"Personne inconnue: {person_id}")

    p = people[person_id]

    # ========================================================
    # NOTE (NOW CLEAN FROM PEOPLE DICT)
    # ========================================================

    row_note = df.loc[df["ID"] == person_id, "Note"].values
    row_note = row_note[0] if len(row_note) > 0 else ""

    # ========================================================
    # PHOTO
    # ========================================================

    image_path = None
    for ext in ["jpg", "jpeg", "png", "webp"]:
        test_path = os.path.join(PHOTO_FOLDER, f"{person_id}.{ext}")
        if os.path.exists(test_path):
            image_path = test_path.replace("\\", "/")
            break

    # ========================================================
    # FAMILY LINKS
    # ========================================================

    father_name = get_person_name(p["father_id"])
    mother_name = get_person_name(p["mother_id"])
    spouse_name = get_person_name(p["spouse_id"])

    # ========================================================
    # CHILDREN (SORTED BY BIRTH DATE + SPOUSE LOGIC)
    # ========================================================

    children_rows = []

    for _, row in df.iterrows():

        remark = str(row.get("Remark", "")).lower().strip()
        if "child" not in remark:
            continue

        father_id = clean_id(row.get("ID_pere", ""))
        mother_id = clean_id(row.get("ID_mere", ""))

        if father_id != person_id and mother_id != person_id:
            continue

        child_name = (
            f"{row.get('Prenom','').strip()} {row.get('Nom','').strip()}".strip()
        )
        birth = row.get("Naissance", "").strip()

        other_parent_id = mother_id if father_id == person_id else father_id
        other_parent_name = get_person_name(other_parent_id)

        # Hide spouse duplication
        if other_parent_id == p["spouse_id"]:
            other_parent_name = ""

        children_rows.append(
            {"name": child_name, "birth": birth, "other_parent": other_parent_name}
        )

    def parse_date(d):
        try:
            return datetime.strptime(d, "%d/%m/%Y")
        except:
            return datetime.max

    children_rows = sorted(children_rows, key=lambda x: parse_date(x["birth"]))

    children = [
        f"{c['name']} ({c['birth'] or '??'})"
        + (f" — {c['other_parent']}" if c["other_parent"] else "")
        for c in children_rows
    ]

    # ========================================================
    # PHOTO
    # ========================================================

    if image_path:
        image_component = html.Img(
            src=image_path,
            style={
                "width": "240px",
                "borderRadius": "16px",
                "objectFit": "cover",
                "boxShadow": "0 4px 12px rgba(0,0,0,0.2)",
            },
        )
    else:
        image_component = html.Div(
            "Pas de photo",
            style={
                "width": "240px",
                "height": "320px",
                "backgroundColor": "#ddd",
                "borderRadius": "16px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
            },
        )

    # ========================================================
    # CARD
    # ========================================================

    return html.Div(
        [
            html.Div([image_component], style={"flex": "0 0 260px"}),
            html.Div(
                [
                    html.H2(p["name"], style={"fontSize": "36px"}),
                    html.H4(f"Génération : {p['gen']}"),
                    html.P([html.B("Naissance : "), p["birth"] or "Inconnue"]),
                    html.P([html.B("Décès : "), p["death"] or "—"]),
                    html.P([html.B("Père : "), father_name or "—"]),
                    html.P([html.B("Mère : "), mother_name or "—"]),
                    html.P([html.B("Conjoint : "), spouse_name or "—"]),
                    html.Div(
                        [
                            html.B("Enfants :"),
                            (
                                html.Ul([html.Li(c) for c in children])
                                if children
                                else html.P("Aucun enfant")
                            ),
                        ]
                    ),
                    html.P([html.B("Note : "), row_note or "—"]),  # ✅ FINAL FIX
                ],
                style={"flex": "1", "paddingLeft": "40px"},
            ),
        ],
        style={
            "display": "flex",
            "maxWidth": "1100px",
            "margin": "auto",
            "backgroundColor": "white",
            "padding": "40px",
            "borderRadius": "20px",
        },
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(jupyter_mode="external")
