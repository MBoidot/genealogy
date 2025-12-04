import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import colorsys

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
file_path = "family_data.csv"

base_hsl = {
    0: (0.58, 0.55, 0.40),  # teal
    1: (0.00, 0.65, 0.47),  # red
    2: (0.10, 0.70, 0.47),  # orange
    3: (0.33, 0.55, 0.45),  # green
    4: (0.66, 0.45, 0.50),  # indigo
}

DIMMED_L_BOOST = 0.25
VERTICAL_SPACING = 0.60  # decreased vertical spacing


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------
def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def brighten_hsl(h, s, l, amount=DIMMED_L_BOOST):
    l = min(1.0, l + amount)
    return hsl_to_hex(h, s, l)


def parse_date(date_str):
    if pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    if date_str in ["", "/", "-", "--"]:
        return None
    try:
        return pd.to_datetime(date_str, format="%d/%m/%Y")
    except:
        return None


def get_gen_color(gen_value, is_dead=False):
    gen_str = str(gen_value).strip()
    is_prime = gen_str.endswith("'")
    base_str = gen_str.replace("'", "")
    try:
        base_gen = int(base_str)
    except:
        base_gen = 0
    h, s, l = base_hsl.get(base_gen, (0.45, 0.5, 0.5))
    color = hsl_to_hex(h, s, l)
    if is_prime:
        color = brighten_hsl(h, s, l)
    if is_dead:
        return "#D3D3D3"
    return color


# -------------------------------------------------------------------
# LOAD CSV
# -------------------------------------------------------------------
df = pd.read_csv(file_path, sep=";", encoding="cp1252", dtype=str)
df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=False)

birth_col = [c for c in df.columns if "Naissance" in c][0]
death_col = [c for c in df.columns if "Déc" in c][0]
prenom_col = [c for c in df.columns if "Prénom" in c or "Prenom" in c][0]
nom_col = [c for c in df.columns if c.startswith("Nom")][0]
gen_col = [c for c in df.columns if c.startswith("Gen")][0]

for col in [birth_col, death_col]:
    df[col] = df[col].replace(["", " ", "--", "-", "/", "N/A", "NA", "None"], pd.NA)

df["Birth_Date"] = df[birth_col].apply(parse_date)
df["Death_Date"] = df[death_col].apply(parse_date)

df = df[df["Birth_Date"].notna()].copy()
df = df.sort_values("Birth_Date")

# -------------------------------------------------------------------
# CREATE PLOTLY FIGURE
# -------------------------------------------------------------------
fig = go.Figure()
annotations = []

for idx, (_, person) in enumerate(df.iterrows()):
    y = idx * VERTICAL_SPACING
    birth = person["Birth_Date"]
    death = person["Death_Date"]
    is_dead = pd.notna(death)
    bar_end = death if is_dead else datetime.now()

    gen_value = person[gen_col]
    line_color = get_gen_color(gen_value, is_dead=is_dead)
    marker_color = get_gen_color(gen_value, is_dead=False)

    prenom = person[prenom_col]
    nom = person[nom_col]
    full_name = f"{prenom} {nom}"

    # Lifespan line
    fig.add_trace(
        go.Scatter(
            x=[birth, bar_end],
            y=[y, y],
            mode="lines+markers",
            line=dict(color=line_color, width=2),
            marker=dict(color="white", line=dict(color=marker_color, width=1), size=6),
            hovertext=full_name,
            hoverinfo="text",
            showlegend=False,
        )
    )

    # Name annotation
    annotations.append(
        dict(
            x=birth.replace(year=birth.year - 1),
            y=y,
            xanchor="right",
            text=full_name,
            font=dict(color="lightgrey", size=6),
            showarrow=False,
        )
    )

# -------------------------------------------------------------------
# LAYOUT
# -------------------------------------------------------------------
fig.update_layout(
    title="Les Boidot - Timeline",
    width=1920,
    xaxis=dict(
        title="Year",
        showline=True,
        showgrid=True,
        gridcolor="lightgrey",
        gridwidth=0.5,
        linecolor="black",
        linewidth=2,
        mirror=True,
    ),
    yaxis=dict(
        showticklabels=False,
        showline=True,
        linecolor="black",
        linewidth=2,
        mirror=True,
    ),
    annotations=annotations,
    margin=dict(l=50, r=50, t=50, b=50),
    legend=dict(x=0, y=1, traceorder="normal", xanchor="left", yanchor="top"),
    height=VERTICAL_SPACING * len(df) * 15,
    plot_bgcolor="white",
    paper_bgcolor="white",
)

# Add custom legend manually
for gen in base_hsl.keys():
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=6, color=hsl_to_hex(*base_hsl[gen])),
            name=f"Gen {gen}",
        )
    )
fig.add_trace(
    go.Scatter(
        x=[None],
        y=[None],
        mode="markers",
        marker=dict(size=6, color="#BBBBBB"),
        name="Deceased",
    )
)

fig.show()
