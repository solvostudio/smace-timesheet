"""SMACE · Timesheet collaboratori — rendicontazione oraria a commesse mensili.

Ogni persona apre a inizio mese la sua commessa (es. "Mario · ottobre 2026"), ne fissa il
plafond secondo il suo contratto e dentro registra giorno, attività (testo libero) e ore.
L'unico admin vede tutto, gestisce le persone e approva a fine mese fuori dallo strumento.

Avvio locale: .venv/bin/streamlit run app.py --server.port 8511
Senza secrets lavora sui CSV in data/ e chiede solo con quale persona entrare.
Online legge da st.secrets: [utenti] (nome = "password") e [github] (repo, token, ramo).
"""
from __future__ import annotations

import calendar
import hmac
import io
import uuid
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ts.calcoli import num, ore_numeriche, riepilogo_mese, stato
from ts.store import ArchivioGitHub, ArchivioLocale
from ts.theme import CSS, DEEP_FOREST, SAGE_GREEN, register_plotly_template

DATI = Path(__file__).parent / "data"
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
ROSSO = "#B3412E"


# ------------------------------------------------------------------ archivio
def _segreti(chiave: str):
    try:
        return st.secrets[chiave]
    except Exception:
        return None


@st.cache_resource
def archivio():
    gh = _segreti("github")
    if gh:
        return ArchivioGitHub(gh["repo"], gh["token"], gh.get("ramo", "main"), gh.get("cartella", "data"))
    return ArchivioLocale(DATI)


@st.cache_data(ttl=60, show_spinner=False)
def leggi(nome: str) -> pd.DataFrame:
    return archivio().leggi(nome)


def scrivi(nome: str, fn, messaggio: str) -> None:
    archivio().modifica(nome, fn, messaggio)
    leggi.clear()


def aggiungi(nome: str, riga: dict, messaggio: str) -> None:
    scrivi(nome, lambda df: pd.concat([df, pd.DataFrame([riga])], ignore_index=True), messaggio)


# ------------------------------------------------------------------ util
def adesso() -> str:
    return datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M")


def etichetta_mese(m: str) -> str:
    a, n = m.split("-")
    return f"{MESI_IT[int(n) - 1]} {a}"


def elenco_mesi(commesse: pd.DataFrame) -> list[str]:
    """Dal mese prossimo indietro di 12, più eventuali mesi più vecchi con commesse."""
    oggi = date.today()
    base = [(oggi.year * 12 + oggi.month - 1) + 1 - i for i in range(14)]
    mesi = [f"{k // 12}-{k % 12 + 1:02d}" for k in base]
    extra = sorted({m for m in commesse["mese"] if m and m not in mesi}, reverse=True)
    return mesi + extra


def mese_corrente() -> str:
    return date.today().strftime("%Y-%m")


def limiti_mese(mese: str) -> tuple[date, date]:
    a, m = map(int, mese.split("-"))
    return date(a, m, 1), date(a, m, calendar.monthrange(a, m)[1])


def ore_fmt(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")


# ------------------------------------------------------------------ accesso
def accesso(persone: pd.DataFrame) -> dict | None:
    if "utente" in st.session_state:
        return st.session_state["utente"]
    attive = persone[persone["attiva"] != "no"]
    utenti = _segreti("utenti")
    st.markdown("# SMACE · Timesheet")
    if utenti is None:
        nome = st.selectbox("Chi sei", list(attive["nome"]), index=None, placeholder="Scegli il tuo nome")
        st.caption("Modalità locale: nessuna password richiesta.")
        ok = nome is not None and st.button("Entra", type="primary")
    else:
        # online l'app è pubblica: niente elenco dei nomi, il nome si scrive
        scritto = st.text_input("Nome").strip().lower()
        nome = next((n for n in attive["nome"] if n.lower() == scritto), None)
        pw = st.text_input("Password", type="password")
        ok = bool(nome and pw and nome in utenti and hmac.compare_digest(pw, str(utenti[nome])))
        if scritto and pw and not ok:
            st.error("Nome o password errati.")
    if ok:
        ruolo = attive.loc[attive["nome"] == nome, "ruolo"].iloc[0]
        st.session_state["utente"] = {"nome": nome, "admin": ruolo == "admin"}
        st.rerun()
    return None


# ------------------------------------------------------------------ commessa
def barra_plafond(ore: float, plafond: float | None) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Ore registrate", ore_fmt(ore))
    c2.metric("Plafond", ore_fmt(plafond) if plafond is not None else "da definire")
    if plafond is None:
        c3.metric("Residuo", "—")
        return
    c3.metric("Residuo", ore_fmt(plafond - ore))
    st.progress(min(ore / plafond, 1.0) if plafond else 1.0)
    if ore > plafond:
        st.warning(f"Plafond superato di {ore_fmt(ore - plafond)} ore. Le ore restano registrate: "
                   "il superamento va confermato fuori da questo strumento.")


def ultimo_plafond(persona: str, commesse: pd.DataFrame) -> float | None:
    """Plafond della commessa più recente della persona, proposto come valore di partenza."""
    sue = commesse[commesse["persona"] == persona].sort_values("mese")
    return num(sue.iloc[-1]["plafond"]) if len(sue) else None


def periodo(mese: str) -> str:
    oggi = mese_corrente()
    return "in corso" if mese == oggi else ("chiusa" if mese < oggi else "futura")


def torna_all_elenco() -> None:
    if st.button("← Tutte le commesse"):
        st.session_state.pop("commessa", None)
        st.session_state.pop("nuova", None)
        st.rerun()


def elenco_commesse(utente: dict, persone, commesse, reg) -> None:
    st.markdown("## Commesse")
    c1, c2 = st.columns([3, 1])
    if utente["admin"]:
        scelta = c1.selectbox("Persona", ["Tutte"] + list(persone["nome"]))
        viste = commesse if scelta == "Tutte" else commesse[commesse["persona"] == scelta]
    else:
        viste = commesse[commesse["persona"] == utente["nome"]]
    c2.markdown("&nbsp;", unsafe_allow_html=True)
    if c2.button("Nuova commessa", type="primary", width="stretch"):
        st.session_state["nuova"] = True
        st.rerun()

    if viste.empty:
        st.caption("Nessuna commessa. A inizio mese si apre quella del mese con \"Nuova commessa\".")
        return
    ore = ore_numeriche(reg).groupby("commessa")["ore"].sum()
    for _, c in viste.sort_values(["mese", "persona"], ascending=[False, True]).iterrows():
        o, pl = float(ore.get(c["id"], 0.0)), num(c["plafond"])
        with st.container(border=True):
            a, b, d, e = st.columns([3, 2, 2, 1], vertical_alignment="center")
            a.markdown(f"**{c['persona']} · {etichetta_mese(c['mese'])}**  \n{periodo(c['mese'])}")
            b.markdown(f"{ore_fmt(o)} / {ore_fmt(pl)} ore")
            st_pl = stato(o, pl)
            d.markdown(f":red[{st_pl}]" if st_pl == "oltre plafond" else st_pl)
            if e.button("Apri", key=f"apri_{c['id']}", width="stretch"):
                st.session_state["commessa"] = c["id"]
                st.rerun()


def nuova_commessa(utente: dict, persone, commesse) -> None:
    torna_all_elenco()
    st.markdown("## Nuova commessa")
    if utente["admin"]:
        attive = list(persone.loc[persone["attiva"] != "no", "nome"])
        persona = st.selectbox("Persona", attive, index=attive.index(utente["nome"]) if utente["nome"] in attive else 0)
    else:
        persona = utente["nome"]
    occupati = set(commesse.loc[commesse["persona"] == persona, "mese"])
    mesi = [m for m in elenco_mesi(commesse) if m not in occupati]
    mese = st.selectbox("Mese", mesi, index=mesi.index(mese_corrente()) if mese_corrente() in mesi else 0,
                        format_func=etichetta_mese)
    st.caption("Si apre a inizio mese, con il plafond di ore previsto dal tuo contratto.")
    plafond = st.number_input("Plafond del mese (ore)", min_value=0.0, step=1.0,
                              value=ultimo_plafond(persona, commesse), placeholder="es. 26")
    if st.button(f"Apri commessa {persona} · {etichetta_mese(mese)}", type="primary", disabled=not plafond):
        nuovo_id = uuid.uuid4().hex[:8]
        aggiungi("commesse", {"id": nuovo_id, "persona": persona, "mese": mese,
                              "plafond": str(plafond), "aperta_il": adesso(), "aperta_da": utente["nome"]},
                 f"Commessa aperta: {persona} {mese}")
        st.session_state.pop("nuova", None)
        st.session_state["commessa"] = nuovo_id
        st.rerun()


def modifica_plafond(comm: pd.Series) -> None:
    with st.expander("Modifica plafond"):
        nuovo = st.number_input("Plafond del mese (ore)", min_value=0.0, step=1.0,
                                value=num(comm["plafond"]), key=f"pl_{comm['id']}")
        if st.button("Salva plafond", disabled=not nuovo or nuovo == num(comm["plafond"])):
            scrivi("commesse", lambda df: df.assign(plafond=df["plafond"].where(df["id"] != comm["id"], str(nuovo))),
                   f"Plafond {comm['persona']} {comm['mese']}: {nuovo}")
            st.rerun()


def dettaglio_commessa(comm: pd.Series, reg) -> None:
    torna_all_elenco()
    persona, mese = comm["persona"], comm["mese"]
    st.markdown(f"## Commessa {persona} · {etichetta_mese(mese)}")
    st.caption(f"{periodo(mese)} · aperta il {comm['aperta_il']} da {comm['aperta_da']}")
    mie = reg[reg["commessa"] == comm["id"]]
    barra_plafond(float(ore_numeriche(mie)["ore"].sum()), num(comm["plafond"]))
    modifica_plafond(comm)

    primo, ultimo = limiti_mese(mese)
    with st.form("nuove_ore", clear_on_submit=True):
        st.markdown("#### Registra ore")
        c1, c2, c3 = st.columns([1, 3, 1])
        giorno = c1.date_input("Giorno", value=min(max(date.today(), primo), ultimo),
                               min_value=primo, max_value=ultimo, format="DD/MM/YYYY")
        att = c2.text_input("Attività", placeholder="es. Chiusura contabile di settembre")
        ore = c3.number_input("Ore", min_value=0.5, max_value=24.0, value=1.0, step=0.5)
        note = st.text_input("Note (facoltative)")
        if st.form_submit_button("Registra", type="primary"):
            if not att.strip():
                st.error("Scrivi l'attività svolta.")
            else:
                aggiungi("registrazioni", {
                    "id": uuid.uuid4().hex[:8], "commessa": comm["id"], "persona": persona, "mese": mese,
                    "data": giorno.isoformat(), "attivita": att.strip(), "ore": str(ore),
                    "note": note.strip(), "inserita_il": adesso()},
                    f"{persona}: {ore_fmt(ore)} h il {giorno.isoformat()}")
                st.session_state["esito"] = f"Registrate {ore_fmt(ore)} ore il {giorno.strftime('%d/%m')}."
                st.rerun()
    if msg := st.session_state.pop("esito", None):
        st.success(msg)

    if mie.empty:
        st.caption("Nessuna ora registrata in questa commessa.")
        return
    tab = mie[["id", "data", "attivita", "ore", "note"]].sort_values("data").copy()
    tab["ore"] = tab["ore"].map(num)
    tab.insert(0, "elimina", False)
    ed = st.data_editor(tab, hide_index=True, width="stretch", disabled=list(tab.columns[1:]),
                        column_config={"id": None, "elimina": st.column_config.CheckboxColumn("Elimina"),
                                       "data": "Giorno", "attivita": "Attività", "ore": "Ore", "note": "Note"},
                        key=f"ed_{comm['id']}")
    da_togliere = set(ed.loc[ed["elimina"], "id"])
    if da_togliere and st.button(f"Elimina {len(da_togliere)} registrazioni selezionate"):
        scrivi("registrazioni", lambda df: df[~df["id"].isin(da_togliere)],
               f"{persona}: eliminate {len(da_togliere)} registrazioni ({mese})")
        st.rerun()



def vista_commesse(utente: dict, persone, commesse, reg) -> None:
    sel = st.session_state.get("commessa")
    comm = commesse[commesse["id"] == sel]
    if sel and len(comm) and (utente["admin"] or comm.iloc[0]["persona"] == utente["nome"]):
        dettaglio_commessa(comm.iloc[0], reg)
    elif st.session_state.get("nuova"):
        nuova_commessa(utente, persone, commesse)
    else:
        st.session_state.pop("commessa", None)
        elenco_commesse(utente, persone, commesse, reg)


# ------------------------------------------------------------------ riepilogo
def grafico_plafond(riep: pd.DataFrame) -> go.Figure:
    colori = [ROSSO if s == "oltre plafond" else DEEP_FOREST for s in riep["stato"]]
    fig = go.Figure()
    fig.add_bar(x=riep["persona"], y=riep["ore"], name="Ore", marker_color=colori)
    con_pl = riep.dropna(subset=["plafond"])
    fig.add_scatter(x=con_pl["persona"], y=con_pl["plafond"], name="Plafond", mode="markers",
                    marker=dict(symbol="line-ew-open", size=40, line=dict(width=3, color=SAGE_GREEN)))
    fig.update_layout(title="Ore contro plafond", height=360, showlegend=True)
    return fig


def excel_mese(riep, dettaglio) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        riep.to_excel(xw, sheet_name="Commesse", index=False)
        dettaglio.to_excel(xw, sheet_name="Dettaglio", index=False)
    return buf.getvalue()


def vista_riepilogo(utente: dict, persone, commesse, reg) -> None:
    st.markdown("## Riepilogo")
    mesi = elenco_mesi(commesse)
    mese = st.selectbox("Mese", mesi, index=mesi.index(mese_corrente()), format_func=etichetta_mese, key="mese_riep")
    if not utente["admin"]:
        reg = reg[reg["persona"] == utente["nome"]]
        persone = persone[persone["nome"] == utente["nome"]]
        commesse = commesse[commesse["persona"] == utente["nome"]]
    riep = riepilogo_mese(mese, reg, persone, commesse)

    c1, c2, c3 = st.columns(3)
    c1.metric("Ore totali", ore_fmt(riep["ore"].sum()))
    c2.metric("Commesse aperte", int((riep["stato"] != "commessa non aperta").sum()))
    c3.metric("Oltre plafond", int((riep["stato"] == "oltre plafond").sum()))

    if riep["ore"].sum() > 0:
        st.plotly_chart(grafico_plafond(riep), width="stretch")
    vista = riep.copy()
    for col in ("ore", "plafond", "residuo"):
        vista[col] = vista[col].map(ore_fmt)
    st.dataframe(vista.style.apply(
        lambda r: [f"color: {ROSSO}; font-weight: 600" if r["stato"] == "oltre plafond" else ""] * len(r), axis=1),
        hide_index=True, width="stretch")

    dettaglio = ore_numeriche(reg[reg["mese"] == mese]).sort_values(["persona", "data", "inserita_il"])
    dettaglio = dettaglio[["persona", "data", "attivita", "ore", "note", "inserita_il"]]
    with st.expander(f"Dettaglio registrazioni ({len(dettaglio)})"):
        st.dataframe(dettaglio, hide_index=True, width="stretch")
    st.download_button("Scarica Excel del mese", excel_mese(riep, dettaglio),
                       file_name=f"timesheet_smace_{mese}.xlsx", type="primary",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ------------------------------------------------------------------ impostazioni
def vista_impostazioni(persone, commesse) -> None:
    st.markdown("## Impostazioni")
    st.caption("Le password non stanno qui: si impostano nei secrets dell'app, una per persona.")

    st.markdown("### Persone")
    ed_p = st.data_editor(persone, num_rows="dynamic", hide_index=True, width="stretch", key="ed_persone",
                          column_config={"nome": "Nome",
                                         "ruolo": st.column_config.SelectboxColumn("Ruolo", options=["collaboratore", "admin"], required=True),
                                         "attiva": st.column_config.SelectboxColumn("Attiva", options=["sì", "no"], required=True)})
    if st.button("Salva persone"):
        if ed_p["nome"].duplicated().any() or (ed_p["nome"].str.strip() == "").any():
            st.error("Controlla la tabella: nomi vuoti o doppi.")
        else:
            scrivi("persone", lambda _: ed_p, "Impostazioni: persone")
            st.rerun()

    st.markdown("### Commesse")
    st.caption("Qui si corregge il plafond di una commessa già aperta.")
    tab = commesse.sort_values(["mese", "persona"], ascending=[False, True])
    ed_c = st.data_editor(tab, hide_index=True, width="stretch", key="ed_commesse",
                          disabled=["id", "persona", "mese", "aperta_il", "aperta_da"],
                          column_config={"id": None, "persona": "Persona", "mese": "Mese", "plafond": "Plafond (ore)",
                                         "aperta_il": "Aperta il", "aperta_da": "Aperta da"})
    if st.button("Salva plafond delle commesse"):
        if any(str(v).strip() and num(v) is None for v in ed_c["plafond"]):
            st.error("Plafond non numerico su qualche riga.")
        else:
            nuovi = dict(zip(ed_c["id"], ed_c["plafond"]))
            scrivi("commesse", lambda df: df.assign(plafond=df["id"].map(nuovi).fillna(df["plafond"])),
                   "Impostazioni: plafond commesse")
            st.rerun()


# ------------------------------------------------------------------ main
def main():
    st.set_page_config(page_title="SMACE · Timesheet", layout="wide", page_icon=":stopwatch:")
    register_plotly_template()
    st.markdown(CSS, unsafe_allow_html=True)
    # su Streamlit Cloud (repo montato in /mount/src) senza secrets l'app non deve aprirsi senza password
    if Path(__file__).resolve().parts[1:3] == ("mount", "src") and not (_segreti("utenti") and _segreti("github")):
        st.error("Configurazione incompleta: mancano i secrets dell'app.")
        st.stop()

    persone = leggi("persone")
    utente = accesso(persone)
    if utente is None:
        st.stop()
    commesse, reg = leggi("commesse"), leggi("registrazioni")

    st.sidebar.markdown("# SMACE")
    st.sidebar.markdown("### Timesheet")
    st.sidebar.caption(f"{utente['nome']}{' · admin' if utente['admin'] else ''}")
    viste = ["Commesse", "Riepilogo"] + (["Impostazioni"] if utente["admin"] else [])
    vista = st.sidebar.radio("Vista", viste, label_visibility="collapsed")
    st.sidebar.markdown("---")
    if st.sidebar.button("Esci"):
        st.session_state.clear()
        st.rerun()

    if vista == "Commesse":
        vista_commesse(utente, persone, commesse, reg)
    elif vista == "Riepilogo":
        vista_riepilogo(utente, persone, commesse, reg)
    else:
        vista_impostazioni(persone, commesse)


if __name__ == "__main__":
    main()
