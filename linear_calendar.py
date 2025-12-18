import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import colorsys

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
FILE_PATH = "family_data.csv"
REFERENCE_YEAR = 2000
VERTICAL_SPACING = 0.6
DIMMED_L_BOOST = 0.25

BASE_HSL = {
    0: (0.58, 0.55, 0.40),  # teal
    1: (0.00, 0.65, 0.47),  # red
    2: (0.10, 0.70, 0.47),  # orange
    3: (0.33, 0.55, 0.45),  # green
    4: (0.66, 0.45, 0.50),  # indigo
}


# -------------------------------------------------------------------
# COLOR HELPERS
# -------------------------------------------------------------------
def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def brighten_hsl(h, s, l, amount=DIMMED_L_BOOST):
    return hsl_to_hex(h, s, min(1.0, l + amount))


def get_gen_color(gen_value, is_dead=False):
    gen_str = str(gen_value).strip()
    is_prime = gen_str.endswith("'")
    base_str = gen_str.replace("'", "")

    try:
        base_gen = int(base_str)
    except ValueError:
        base_gen = 0

    h, s, l = BASE_HSL.get(base_gen, (0.45, 0.5, 0.5))
    color = brighten_hsl(h, s, l) if is_prime else hsl_to_hex(h, s, l)

    return "#D3D3D3" if is_dead else color


# -------------------------------------------------------------------
# DATE PARSING
# -------------------------------------------------------------------
def parse_date(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value in ["", "-", "--", "/", "NA", "N/A"]:
        return None
    try:
        return pd.to_datetime(value, format="%d/%m/%Y")
    except Exception:
        return None


# -------------------------------------------------------------------
# LOAD & CLEAN DATA
# -------------------------------------------------------------------
df = pd.read_csv(FILE_PATH, sep=";", encoding="cp1252", dtype=str)
df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=False)

birth_col = next(c for c in df.columns if "Naissance" in c)
prenom_col = next(c for c in df.columns if "Prénom" in c or "Prenom" in c)
nom_col = next(c for c in df.columns if c.startswith("Nom"))
gen_col = next(c for c in df.columns if c.startswith("Gen"))

df["Birth_Date"] = df[birth_col].apply(parse_date)

df = df[df["Birth_Date"].notna()].copy()

# -------------------------------------------------------------------
# MAP BIRTHDAYS TO SINGLE CALENDAR YEAR
# -------------------------------------------------------------------
df["Calendar_Date"] = df["Birth_Date"].apply(lambda d: d.replace(year=REFERENCE_YEAR))

df = df.sort_values("Calendar_Date")

# -------------------------------------------------------------------
# CREATE FIGURE
# -------------------------------------------------------------------
fig = go.Figure()
annotations = []

for idx, (_, person) in enumerate(df.iterrows()):
    y = idx * VERTICAL_SPACING
    x = person["Calendar_Date"]

    gen_value = person[gen_col]

    full_name = f"{person[prenom_col]} {person[nom_col]}"

    # Birthday tick
    fig.add_trace(
        go.Scatter(
            x=[x, x],
            y=[y - 0.15, y + 0.15],
            mode="lines",
            line=dict(color=line_color, width=2),
            hovertext=full_name,
            hoverinfo="text",
            showlegend=False,
        )
    )

    # Center dot
    fig.add_trace(
        go.Scatter(
            x=[x],
            y=[y],
            mode="markers",
            marker=dict(
                size=6,
                color="white",
                line=dict(color=marker_color, width=1),
            ),
            hovertext=full_name,
            hoverinfo="text",
            showlegend=False,
        )
    )

    # Name annotation
    annotations.append(
        dict(
            x=x,
            y=y,
            xanchor="left",
            xshift=6,
            text=full_name,
            font=dict(size=6, color="lightgrey"),
            showarrow=False,
        )
    )

# -------------------------------------------------------------------
# LAYOUT
# -------------------------------------------------------------------
fig.update_layout(
    title="Les Boidot — Birthday Calendar",
    width=1920,
    height=int(len(df) * VERTICAL_SPACING * 15),
    xaxis=dict(
        range=[
            datetime(REFERENCE_YEAR, 1, 1),
            datetime(REFERENCE_YEAR, 12, 31),
        ],
        tickformat="%d %b",
        dtick="M1",
        showgrid=True,
        gridcolor="lightgrey",
        linecolor="black",
        linewidth=2,
        mirror=True,
        title="Day of year",
    ),
    yaxis=dict(
        showticklabels=False,
        showline=True,
        linecolor="black",
        linewidth=2,
        mirror=True,
    ),
    annotations=annotations,
    margin=dict(l=50, r=50, t=60, b=50),
    plot_bgcolor="white",
    paper_bgcolor="white",
)

# -------------------------------------------------------------------
# LEGEND
# -------------------------------------------------------------------
for gen, hsl in BASE_HSL.items():
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=6, color=hsl_to_hex(*hsl)),
            name=f"Gen {gen}",
        )
    )

fig.add_trace(
    go.Scatter(
        x=[None],
        y=[None],
        mode="markers",
        marker=dict(size=6, color="#D3D3D3"),
        name="Deceased",
    )
)

# -------------------------------------------------------------------
# SHOW
# -------------------------------------------------------------------
fig.show()
