import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import colorsys
import random
from collections import defaultdict
import numpy as np

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------
FILE_PATH = "family_data.csv"
REFERENCE_YEAR = 2000

LANE_HEIGHTS_ABOVE = [0.2, 0.6, 1.0, 1.4]
LANE_HEIGHTS_BELOW = LANE_HEIGHTS_ABOVE
OFFSET_AMOUNT = 0.15
GESTATION_DAYS = 274  # ~9 months

BINS = 12

BASE_HSL = {
    0: (0.58, 0.55, 0.40),
    1: (0.00, 0.65, 0.47),
    2: (0.10, 0.70, 0.47),
    3: (0.33, 0.55, 0.45),
    4: (0.66, 0.45, 0.50),
}


# -------------------------------------------------------------------
# COLOR HELPERS
# -------------------------------------------------------------------
def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def brighten_hsl(h, s, l, amount=0.25):
    return hsl_to_hex(h, s, min(1.0, l + amount))


def get_gen_color(gen_value):
    gen_str = str(gen_value).strip()
    is_prime = gen_str.endswith("'")
    base_str = gen_str.replace("'", "")
    try:
        base_gen = int(base_str)
    except:
        base_gen = 0
    h, s, l = BASE_HSL.get(base_gen, (0.45, 0.5, 0.5))
    return brighten_hsl(h, s, l) if is_prime else hsl_to_hex(h, s, l)


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
    except:
        return None


# -------------------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------------------
df = pd.read_csv(FILE_PATH, sep=";", encoding="cp1252", dtype=str)
df.columns = df.columns.str.strip().str.replace("\xa0", "", regex=False)

birth_col = next(c for c in df.columns if "Naissance" in c)
prenom_col = next(c for c in df.columns if "Prénom" in c or "Prenom" in c)
nom_col = next(c for c in df.columns if c.startswith("Nom"))
gen_col = next(c for c in df.columns if c.startswith("Gen"))

df["Birth_Date"] = df[birth_col].apply(parse_date)
df = df[df["Birth_Date"].notna()].copy()
df["Calendar_Date"] = df["Birth_Date"].apply(lambda d: d.replace(year=REFERENCE_YEAR))
df = df.sort_values("Calendar_Date").reset_index(drop=True)
df["day_of_year"] = df["Calendar_Date"].dt.dayofyear


# -------------------------------------------------------------------
# HISTOGRAM FUNCTION (no wrapping)
# -------------------------------------------------------------------
def simple_hist(days, bins=BINS, max_height=1.7):
    hist, bin_edges = np.histogram(days, bins=bins, range=(0, 365))
    hist = hist / hist.max() * max_height
    # bin centers
    bin_centers = [
        (bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)
    ]
    bin_dates = [
        datetime(REFERENCE_YEAR, 1, 1) + timedelta(days=int(d)) for d in bin_centers
    ]
    return hist, bin_dates


# Birthday distribution
birthday_hist, birthday_dates = simple_hist(
    df["day_of_year"], bins=BINS, max_height=max(LANE_HEIGHTS_ABOVE)
)

# Conception distribution (shifted by 9 months)
concept_day_of_year = (df["day_of_year"] - GESTATION_DAYS) % 365
concept_hist, concept_dates = simple_hist(
    concept_day_of_year, bins=BINS, max_height=max(LANE_HEIGHTS_ABOVE)
)

# -------------------------------------------------------------------
# FIGURE INIT
# -------------------------------------------------------------------
fig = go.Figure()

# Birthday distribution
fig.add_trace(
    go.Scatter(
        x=birthday_dates,
        y=birthday_hist,
        fill="tozeroy",  # fill from zero
        fillcolor="rgba(150,200,255,0.3)",
        line=dict(color="rgba(0,0,0,0)", shape="linear"),  # no spline
        hoverinfo="skip",
        showlegend=False,
    )
)

# Conception distribution (shifted by 9 months)
fig.add_trace(
    go.Scatter(
        x=concept_dates,
        y=concept_hist,
        fill="tozeroy",  # fill from zero
        fillcolor="rgba(255,150,150,0.3)",
        line=dict(color="rgba(0,0,0,0)", shape="linear"),
        hoverinfo="skip",
        showlegend=False,
    )
)

# -------------------------------------------------------------------
# SAME-DAY BIRTHDAYS OFFSET
# -------------------------------------------------------------------
same_day_counts = defaultdict(int)


def get_x_offset(date):
    count = same_day_counts[date]
    same_day_counts[date] += 1
    shift = 0.8 * ((count % 2) * 2 - 1)
    return timedelta(days=shift)


# -------------------------------------------------------------------
# STEMS, DOTS, LABELS
# -------------------------------------------------------------------
for idx, person in df.iterrows():
    base_x = person["Calendar_Date"]
    x_shift = get_x_offset(base_x)
    x = base_x + x_shift

    direction = 1 if idx % 2 == 0 else -1
    lane_idx = (idx // 2) % 4
    base_y = (
        LANE_HEIGHTS_ABOVE[lane_idx] if direction > 0 else LANE_HEIGHTS_BELOW[lane_idx]
    )

    offset = random.uniform(-OFFSET_AMOUNT, OFFSET_AMOUNT)
    y = direction * (base_y + offset)

    color = get_gen_color(person[gen_col])
    full_name = f"{person[prenom_col]} {person[nom_col]}"
    date_label = base_x.strftime("%d %B")
    hover_text = f"<b>{full_name}</b><br>{date_label}"

    # Stem
    fig.add_trace(
        go.Scatter(
            x=[x, x],
            y=[0, y],
            mode="lines",
            line=dict(color=color, width=2),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Dot
    fig.add_trace(
        go.Scatter(
            x=[x],
            y=[y],
            mode="markers",
            marker=dict(size=7, color="white", line=dict(color=color, width=1.5)),
            hovertext=hover_text,
            hoverinfo="text",
            showlegend=False,
        )
    )

    # Label
    fig.add_annotation(
        x=x,
        y=y,
        text=full_name,
        xanchor="center",
        yanchor="bottom" if y > 0 else "top",
        yshift=6 if y > 0 else -6,
        font=dict(size=12, color="black"),
        showarrow=False,
    )

# -------------------------------------------------------------------
# BASE LINE
# -------------------------------------------------------------------
fig.add_shape(
    type="line",
    x0=datetime(REFERENCE_YEAR, 1, 1),
    x1=datetime(REFERENCE_YEAR, 12, 31),
    y0=0,
    y1=0,
    line=dict(color="black", width=2),
)

# -------------------------------------------------------------------
# LAYOUT
# -------------------------------------------------------------------
x_min = datetime(REFERENCE_YEAR, 1, 1) - timedelta(days=10)
x_max = datetime(REFERENCE_YEAR, 12, 31) + timedelta(days=10)
max_h = max(LANE_HEIGHTS_ABOVE + LANE_HEIGHTS_BELOW) + 0.4

fig.update_layout(
    title="Les Boidot — Birthday Calendar",
    width=1920,
    height=900,
    xaxis=dict(
        range=[x_min, x_max],
        tickformat="%d %b",
        dtick="M1",
        showgrid=False,
        showline=False,
        zeroline=False,
    ),
    yaxis=dict(
        range=[-max_h, max_h],
        showgrid=False,
        showline=False,
        zeroline=False,
        showticklabels=False,
    ),
    margin=dict(l=40, r=40, t=60, b=40),
    plot_bgcolor="white",
    paper_bgcolor="white",
)

fig.show()
