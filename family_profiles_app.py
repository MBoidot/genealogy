import os
import pandas as pd
from dash import Dash, html, dcc, Input, Output

# ============================================================
# CONFIG
# ============================================================

DATA_FILE = "family_data_roles_union.csv"
PHOTO_FOLDER = "photos"

# ============================================================
# LOAD DATA
# ============================================================

# Read CSV
# Separator is ';' according to your files

df = pd.read_csv(DATA_FILE, sep=";", dtype=str, encoding="utf-8-sig")

# Clean columns

df.columns = [c.strip() for c in df.columns]

# Replace NaN

df = df.fillna("")

# ============================================================
# KEEP ONLY UNIQUE PEOPLE
# ============================================================

# One person may appear multiple times because of unions/roles.
# Keep only one row per ID.

people_df = df.drop_duplicates(subset=["ID"])

# ============================================================
# FILTER GEN0 + GEN1
# ============================================================

# Your Gen field sometimes contains apostrophes.
# Example: '0 or '1


def clean_gen(g):
    try:
        return int(str(g).replace("'", "").strip())
    except:
        return -1


people_df["GEN_CLEAN"] = people_df["Gen"].apply(clean_gen)

visible_df = people_df[people_df["GEN_CLEAN"].isin([0, 1])]

# ============================================================
# BUILD PERSON LOOKUP
# ============================================================

people = {}

for _, row in people_df.iterrows():
    pid = row["ID"]

    people[pid] = {
        "id": pid,
        "prenom": row.get("Prenom", ""),
        "nom": row.get("Nom", ""),
        "name": f"{row.get('Prenom', '')} {row.get('Nom', '')}".strip(),
        "birth": row.get("Naissance", ""),
        "death": row.get("Deces", ""),
        "gen": row.get("Gen", ""),
        "gen_origin": row.get("Gen_Origin", ""),
        "father_id": row.get("ID_pere", ""),
        "mother_id": row.get("ID_mere", ""),
        "spouse_id": row.get("ID_Conjoint", ""),
        "remark": row.get("Remark", ""),
    }

# ============================================================
# HELPERS
# ============================================================


def get_person_name(pid):
    if pid in people:
        return people[pid]["name"]
    return ""


# ============================================================
# DASH APP
# ============================================================

app = Dash(__name__)

# ============================================================
# DROPDOWN OPTIONS
# ============================================================

person_options = []

for _, row in visible_df.sort_values(["GEN_CLEAN", "Nom", "Prenom"]).iterrows():
    label = f"Gen {row['GEN_CLEAN']} — {row['Prenom']} {row['Nom']}"

    person_options.append({"label": label, "value": row["ID"]})

# ============================================================
# APP LAYOUT
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
# PROFILE CALLBACK
# ============================================================


@app.callback(Output("profile-card", "children"), Input("person-dropdown", "value"))
def update_profile(person_id):

    if not person_id or person_id not in people:
        return html.Div("Personne introuvable")

    p = people[person_id]

    # ========================================================
    # PHOTO
    # ========================================================

    image_path = None

    # Expected filename format:
    # photos/123.jpg
    # photos/123.png

    possible_extensions = ["jpg", "jpeg", "png", "webp"]

    for ext in possible_extensions:
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
    # CHILDREN
    # ========================================================

    children = []

    for pid, pdata in people.items():

        if pdata["father_id"] == person_id or pdata["mother_id"] == person_id:
            children.append(pdata["name"])

    # ========================================================
    # PHOTO BLOCK
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
                "backgroundColor": "#dddddd",
                "borderRadius": "16px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "color": "#666",
                "fontSize": "20px",
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
                    html.H2(p["name"], style={"marginTop": "0", "fontSize": "36px"}),
                    html.H4(f"Génération : {p['gen']}"),
                    html.P([html.B("Naissance : "), p["birth"] or "Inconnue"]),
                    html.P([html.B("Décès : "), p["death"] or "—"]),
                    html.P(
                        [html.B("Origine de génération : "), p["gen_origin"] or "—"]
                    ),
                    html.P([html.B("Père : "), father_name or "—"]),
                    html.P([html.B("Mère : "), mother_name or "—"]),
                    html.P([html.B("Conjoint : "), spouse_name or "—"]),
                    html.Div(
                        [
                            html.B("Enfants :"),
                            (
                                html.Ul([html.Li(child) for child in children])
                                if children
                                else html.P("Aucun enfant")
                            ),
                        ]
                    ),
                    html.P([html.B("Remarque : "), p["remark"] or "—"]),
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
            "boxShadow": "0 4px 16px rgba(0,0,0,0.15)",
        },
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    app.run(jupyter_mode="external")
