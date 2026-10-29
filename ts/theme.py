"""SMACE Brand Refresh 2026 — palette, font, Plotly template, CSS Streamlit."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# --- Palette (SMACE Brand Refresh 2026) -------------------------------------
DEEP_FOREST    = "#1A3C34"
ELECTRIC_LIME  = "#CCF656"
PERIWINKLE     = "#C7D2FF"
PERIWINKLE_DEEP = "#B3BAFA"
SAGE_GREEN     = "#4A7C6F"
LIGHT_SAGE     = "#E8EDE4"
WARM_BEIGE     = "#D9CFC2"
CREAM          = "#F5F2ED"
RICH_BLACK     = "#1A1A1E"

CATEGORICAL = [
    DEEP_FOREST, ELECTRIC_LIME, PERIWINKLE, SAGE_GREEN,
    WARM_BEIGE, PERIWINKLE_DEEP, "#7BA59C", "#94A0E8",
]
SEQUENTIAL_FOREST = [LIGHT_SAGE, "#A8C2B6", SAGE_GREEN, DEEP_FOREST]

PLOTLY_TEMPLATE_NAME = "smace"


def register_plotly_template() -> None:
    layout = go.Layout(
        font=dict(family="DM Sans, system-ui, sans-serif", color=RICH_BLACK, size=13),
        title=dict(font=dict(family="Playfair Display, serif", color=DEEP_FOREST, size=18)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CATEGORICAL,
        xaxis=dict(gridcolor=LIGHT_SAGE, linecolor=SAGE_GREEN, zerolinecolor=LIGHT_SAGE, tickfont=dict(color=DEEP_FOREST)),
        yaxis=dict(gridcolor=LIGHT_SAGE, linecolor=SAGE_GREEN, zerolinecolor=LIGHT_SAGE, tickfont=dict(color=DEEP_FOREST)),
        # legenda sotto il grafico, con margine sufficiente a non tagliarla (rilievo AFC)
        legend=dict(font=dict(color=DEEP_FOREST), yanchor="top", y=-0.12, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=60, b=90),
    )
    pio.templates[PLOTLY_TEMPLATE_NAME] = go.layout.Template(layout=layout)
    pio.templates.default = PLOTLY_TEMPLATE_NAME


# --- Streamlit CSS -----------------------------------------------------------
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Playfair+Display:wght@400;500;700&display=swap');

:root {{
  --forest: {DEEP_FOREST};
  --lime: {ELECTRIC_LIME};
  --periwinkle: {PERIWINKLE};
  --periwinkle-deep: {PERIWINKLE_DEEP};
  --sage: {SAGE_GREEN};
  --light-sage: {LIGHT_SAGE};
  --warm-beige: {WARM_BEIGE};
  --cream: {CREAM};
  --rich-black: {RICH_BLACK};
}}

html, body, [class*="css"], .stApp {{
  font-family: 'DM Sans', system-ui, sans-serif !important;
  color: var(--rich-black);
}}

.stApp {{ background: var(--cream); }}

h1, h2, h3, h4 {{
  font-family: 'Playfair Display', serif !important;
  color: var(--forest) !important;
  font-weight: 500;
  letter-spacing: -0.01em;
}}
h1 {{ font-size: 2.4rem; }}
h2 {{ font-size: 1.6rem; }}
h3 {{ font-size: 1.25rem; }}

/* Sidebar */
section[data-testid="stSidebar"] {{
  background: var(--forest);
}}
section[data-testid="stSidebar"] * {{ color: var(--cream) !important; }}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
  color: var(--lime) !important;
  font-family: 'Playfair Display', serif !important;
}}

/* Metric cards — cornice sottile su cream */
[data-testid="stMetric"] {{
  background: transparent !important;
  border: 1px solid #A8C2B6 !important;
  border-radius: 8px !important;
  padding: 10px 14px !important;
  box-shadow: none !important;
}}
[data-testid="stMetric"] > div {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}}
div[data-testid="stMetricLabel"] p {{
  color: var(--sage) !important;
  font-size: 0.72rem !important;
  font-weight: 500 !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}
div[data-testid="stMetricValue"] {{
  color: var(--forest) !important;
  font-family: 'Playfair Display', serif !important;
  font-weight: 500 !important;
}}
div[data-testid="stMetricDelta"] {{ color: var(--sage) !important; }}

/* Captions */
div[data-testid="stCaptionContainer"] p,
.stCaption {{
  color: var(--sage) !important;
  text-transform: uppercase;
  font-size: 0.72rem !important;
  letter-spacing: 0.06em;
}}

/* Dividers */
hr {{ border-color: var(--light-sage) !important; }}

/* Buttons */
button[kind="secondary"], button[kind="primary"] {{
  border-radius: 999px !important;
  font-family: 'DM Sans', sans-serif !important;
}}
button[kind="primary"] {{
  background: var(--lime) !important;
  color: var(--forest) !important;
  border: none !important;
}}

/* Plotly chart container — cornice sottile su cream */
[data-testid="stPlotlyChart"] {{
  background: transparent !important;
  border: 1px solid #A8C2B6 !important;
  border-radius: 8px !important;
  padding: 8px !important;
  box-shadow: none !important;
  overflow: hidden !important;
  box-sizing: border-box !important;
}}
[data-testid="stPlotlyChart"] > div {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  overflow: hidden !important;
}}
[data-testid="stPlotlyChart"] .plot-container,
[data-testid="stPlotlyChart"] .plotly,
[data-testid="stPlotlyChart"] .svg-container {{
  overflow: hidden !important;
}}

/* Expander */
div[data-testid="stExpander"] {{
  border: 1px solid #A8C2B6 !important;
  border-radius: 8px !important;
  background: transparent !important;
}}

/* Dataframe (tabelle) — cornice sottile */
[data-testid="stDataFrame"] {{
  border: 1px solid #A8C2B6 !important;
  border-radius: 8px !important;
}}
</style>
"""
