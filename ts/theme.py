"""SMACE Brand Refresh 2026 — palette, font, Plotly template, CSS Streamlit.

Lo stile ricalca il Knowledge Hub aziendale (smace-knowledge-hub.netlify.app):
fondo cream, card bianche arrotondate, titoli Playfair, etichette JetBrains Mono
maiuscole, banda Deep Forest in testa alle pagine e login su fondo periwinkle.
"""
from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

# --- Palette (SMACE Brand Refresh 2026, come nel Knowledge Hub) -------------
DEEP_FOREST    = "#1A3C34"
ELECTRIC_LIME  = "#CCF656"
LIME_SOFT      = "#E4F6A8"
PERIWINKLE     = "#C7D2FF"
PERIWINKLE_DEEP = "#B3BAFA"
SAGE_GREEN     = "#4A7C6F"
LIGHT_SAGE     = "#E8EDE4"
WARM_BEIGE     = "#D9CFC2"
CREAM          = "#F5F2ED"
RICH_BLACK     = "#1A1A1E"
INK            = "#1A2420"
MUTED          = "#6E7B72"
LINE           = "#DDD8CC"
ROSSO          = "#B3412E"

CATEGORICAL = [
    DEEP_FOREST, ELECTRIC_LIME, PERIWINKLE, SAGE_GREEN,
    WARM_BEIGE, PERIWINKLE_DEEP, "#7BA59C", "#94A0E8",
]
SEQUENTIAL_FOREST = [LIGHT_SAGE, "#A8C2B6", SAGE_GREEN, DEEP_FOREST]

PLOTLY_TEMPLATE_NAME = "smace"

# logo SMACE (sagoma PNG usata come maschera, così prende il colore che serve)
_LOGO = Path(__file__).resolve().parent.parent / "static" / "logo_smace.png"
LOGO_URI = "data:image/png;base64," + base64.b64encode(_LOGO.read_bytes()).decode("ascii") if _LOGO.exists() else ""


def register_plotly_template() -> None:
    layout = go.Layout(
        font=dict(family="DM Sans, system-ui, sans-serif", color=INK, size=13),
        title=dict(font=dict(family="Playfair Display, serif", color=DEEP_FOREST, size=18)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CATEGORICAL,
        xaxis=dict(gridcolor=LIGHT_SAGE, linecolor=LINE, zerolinecolor=LIGHT_SAGE, tickfont=dict(color=DEEP_FOREST)),
        yaxis=dict(gridcolor=LIGHT_SAGE, linecolor=LINE, zerolinecolor=LIGHT_SAGE, tickfont=dict(color=DEEP_FOREST)),
        # legenda sotto il grafico, con margine sufficiente a non tagliarla (rilievo AFC)
        legend=dict(font=dict(color=DEEP_FOREST), yanchor="top", y=-0.12, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=60, b=90),
    )
    pio.templates[PLOTLY_TEMPLATE_NAME] = go.layout.Template(layout=layout)
    pio.templates.default = PLOTLY_TEMPLATE_NAME


# --- Blocchi HTML ricorrenti -------------------------------------------------
def logo(colore: str = DEEP_FOREST, larghezza: int = 140, etichetta: str = "") -> str:
    """Logo SMACE con l'etichetta mono accanto, come in testa al Knowledge Hub."""
    altezza = round(larghezza * 88 / 512)
    marchio = (f'<span class="smc-logo" style="width:{larghezza}px;height:{altezza}px;background:{colore};'
               f'-webkit-mask-image:url({LOGO_URI});mask-image:url({LOGO_URI})"></span>')
    testo = f'<span class="smc-topname" style="color:{colore}">{escape(etichetta)}</span>' if etichetta else ""
    return f'<div class="smc-toplogo">{marchio}{testo}</div>'


def intestazione(etichetta: str, titolo: str, sottotitolo: str = "") -> str:
    """Banda Deep Forest di inizio pagina: etichetta lime, titolo Playfair bianco, sottotitolo."""
    sotto = f"<p>{escape(sottotitolo)}</p>" if sottotitolo else ""
    return (f'<div class="smc-hero"><div class="smc-hlabel">{escape(etichetta)}</div>'
            f"<h1>{escape(titolo)}</h1>{sotto}</div>")


def etichetta_sezione(testo: str) -> str:
    """Etichetta di sezione mono maiuscola con filetto, come "IN ORDINE DI IMPORTANZA"."""
    return f'<div class="smc-sec-label">{escape(testo)}</div>'


def chip(testo: str) -> str:
    """Stato di una commessa come pillola colorata, come gli stati delle card del Knowledge Hub."""
    classe = {"nei limiti": "ok", "vicino al plafond": "warn", "oltre plafond": "ko"}.get(testo, "neutro")
    return f'<span class="smc-chip smc-chip-{classe}">{escape(testo)}</span>'


# --- Streamlit CSS -----------------------------------------------------------
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,500;1,600&family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap');

:root {{
  --forest: {DEEP_FOREST};
  --lime: {ELECTRIC_LIME};
  --lime-soft: {LIME_SOFT};
  --periwinkle: {PERIWINKLE};
  --periwinkle-deep: {PERIWINKLE_DEEP};
  --sage: {SAGE_GREEN};
  --light-sage: {LIGHT_SAGE};
  --warm-beige: {WARM_BEIGE};
  --cream: {CREAM};
  --ink: {INK};
  --muted: {MUTED};
  --line: {LINE};
  --rosso: {ROSSO};
  --font-display: 'Playfair Display', Georgia, serif;
  --font-body: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace;
}}

html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button {{
  font-family: var(--font-body) !important;
}}
.stApp {{ background: var(--cream); color: var(--ink); }}
header[data-testid="stHeader"] {{ background: transparent; }}

h1, h2, h3, h4 {{
  font-family: var(--font-display) !important;
  color: var(--forest) !important;
  font-weight: 500 !important;
  letter-spacing: -0.01em;
}}
h1 {{ font-size: 2.4rem; }}
h2 {{ font-size: 1.6rem; }}
h3 {{ font-size: 1.25rem; }}
h4 {{ font-size: 1.1rem; }}

/* Logo + etichetta mono */
.smc-toplogo {{ display: flex; align-items: center; gap: 14px; margin-bottom: 6px; }}
.smc-logo {{ display: inline-block; -webkit-mask-size: contain; mask-size: contain;
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; }}
.smc-topname {{ font-family: var(--font-mono); font-size: 11px; letter-spacing: 1.76px; text-transform: uppercase; }}

/* Banda di intestazione */
.smc-hero {{
  background: var(--forest);
  border-radius: 18px;
  padding: 26px 28px 24px;
  margin: 0 0 18px;
}}
.smc-hero h1 {{ color: #fff !important; font-size: 2rem; margin: 4px 0 0; padding: 0; line-height: 1.15; }}
.smc-hero p {{ color: rgba(255,255,255,.78); margin: 8px 0 0; font-size: .95rem; }}
.smc-hlabel {{
  font-family: var(--font-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 2px; text-transform: uppercase; color: var(--lime);
}}

/* Etichetta di sezione con filetto */
.smc-sec-label {{
  display: flex; align-items: center; gap: 12px; margin: 18px 0 10px;
  font-family: var(--font-mono); font-size: 10px; font-weight: 600;
  letter-spacing: 1.8px; text-transform: uppercase; color: var(--sage);
}}
.smc-sec-label::after {{ content: ""; flex: 1; height: 1px; background: var(--line); }}

/* Titolo e sottotitolo delle card, come le sotto-aree del Knowledge Hub */
.smc-card-title {{ font-family: var(--font-display); font-size: 1.2rem; font-weight: 500; color: var(--forest); }}
.smc-card-sub {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}

/* Pillole di stato */
.smc-chip {{
  display: inline-block; padding: 4px 12px; border-radius: 20px;
  font-family: var(--font-mono); font-size: 10px; font-weight: 700;
  letter-spacing: .45px; text-transform: uppercase; color: var(--forest);
}}
.smc-chip-ok {{ background: var(--lime); }}
.smc-chip-warn {{ background: var(--lime-soft); }}
.smc-chip-ko {{ background: var(--rosso); color: #fff; }}
.smc-chip-neutro {{ background: var(--light-sage); color: var(--sage); }}

/* Sidebar */
section[data-testid="stSidebar"] {{ background: var(--forest); }}
section[data-testid="stSidebar"] * {{ color: var(--cream) !important; }}
section[data-testid="stSidebar"] .smc-topname,
section[data-testid="stSidebar"] .smc-sec-label {{ color: var(--lime) !important; }}
section[data-testid="stSidebar"] .smc-sec-label::after {{ background: rgba(255,255,255,.15); }}
section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p {{ color: rgba(245,242,237,.7) !important; }}
section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.15) !important; }}
section[data-testid="stSidebar"] button {{
  background: rgba(255,255,255,.1) !important; border: none !important;
}}

/* Card: contenitori con bordo, metriche, expander, tabelle, grafici */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]),
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"][class*="border"],
[data-testid="stMetric"],
div[data-testid="stExpander"] details,
[data-testid="stForm"] {{
  background: #fff !important;
  border: 1px solid var(--line) !important;
  border-radius: 15px !important;
  box-shadow: none !important;
}}
[data-testid="stMetric"] {{ padding: 14px 18px !important; }}
[data-testid="stForm"] {{ padding: 20px 22px !important; }}
[data-testid="stMetric"] > div {{ background: transparent !important; border: none !important; }}
[data-testid="stMetricLabel"] p {{
  color: var(--sage) !important;
  font-family: var(--font-mono) !important;
  font-size: 10px !important;
  font-weight: 600 !important;
  text-transform: uppercase;
  letter-spacing: 1.8px;
}}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] p {{
  color: var(--forest) !important;
  font-family: var(--font-display) !important;
  font-weight: 500 !important;
}}
[data-testid="stDataFrame"], [data-testid="stPlotlyChart"] {{
  background: #fff !important;
  border: 1px solid var(--line) !important;
  border-radius: 15px !important;
  overflow: hidden !important;
}}
[data-testid="stPlotlyChart"] {{ padding: 8px !important; }}

/* Testi secondari */
div[data-testid="stCaptionContainer"] p, .stCaption {{
  color: var(--muted) !important;
  font-size: 13px !important;
}}
hr {{ border-color: var(--line) !important; }}

/* Campi: bianchi, arrotondati, ombra leggera come la ricerca del Knowledge Hub */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {{
  background: #fff !important;
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
}}
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {{ background: #fff !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within {{
  border-color: var(--sage) !important;
  box-shadow: 0 6px 18px rgba(26,60,52,.10) !important;
}}

/* Pulsanti a pillola: primario lime, secondario bianco con filetto */
.stApp button[kind="secondary"], .stApp button[kind="primary"],
.stApp button[kind="secondaryFormSubmit"], .stApp button[kind="primaryFormSubmit"],
[data-testid="stDownloadButton"] button {{
  border-radius: 999px !important;
  font-weight: 600 !important;
}}
.stApp button[kind="primary"], .stApp button[kind="primaryFormSubmit"],
[data-testid="stDownloadButton"] button[kind="primary"] {{
  background: var(--lime) !important;
  color: var(--forest) !important;
  border: none !important;
}}
.stApp button[kind="primary"]:hover, .stApp button[kind="primaryFormSubmit"]:hover {{
  background: var(--forest) !important;
  color: var(--lime) !important;
}}
.stApp section.main button[kind="secondary"], .stApp [data-testid="stMain"] button[kind="secondary"] {{
  background: #fff !important;
  color: var(--forest) !important;
  border: 1px solid var(--line) !important;
}}
.stApp [data-testid="stMain"] button[kind="secondary"]:hover {{ border-color: var(--sage) !important; }}

/* Barra del plafond */
div[data-testid="stProgress"] div[role="progressbar"] > div {{ background: var(--light-sage) !important; border-radius: 99px; }}
div[data-testid="stProgress"] div[role="progressbar"] > div > div {{ background: var(--forest) !important; border-radius: 99px; }}
</style>
"""

# Solo nella pagina di accesso: fondo periwinkle come la home del Knowledge Hub
CSS_ACCESSO = f"""
<style>
.stApp {{ background: {PERIWINKLE} !important; }}
.smc-login h1 {{ font-size: 2.8rem; font-weight: 600 !important; text-align: center; margin: 28px 0 6px; }}
.smc-login h1 em {{
  font-style: italic;
  background: linear-gradient(transparent 62%, {ELECTRIC_LIME} 62%);
  padding: 0 4px;
}}
.smc-login p {{ text-align: center; color: {DEEP_FOREST}; margin-bottom: 18px; }}
div[data-testid="stCaptionContainer"] p {{ color: {DEEP_FOREST} !important; opacity: .7; }}
[data-testid="stMain"] div[data-baseweb="input"] {{
  border: 1.6px solid transparent !important;
  border-radius: 15px !important;
  box-shadow: 0 6px 18px rgba(26,60,52,.10) !important;
}}
</style>
"""
