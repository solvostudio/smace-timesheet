"""SMACE · Timesheet collaboratori — rendicontazione oraria a commesse mensili.

Ogni persona apre a inizio mese la sua commessa (es. "Mario · ottobre 2026"), ne fissa il
plafond secondo il suo contratto (o la segna a forfait, senza plafond) e dentro registra giorno,
attività (testo libero) e ore, più le spese da rimborsare, che l'admin approva e segna come rimborsate.
L'unico admin vede tutto, gestisce le persone e approva a fine mese fuori dallo strumento.

Avvio locale: .venv/bin/streamlit run app.py --server.port 8511
Senza secrets lavora sui CSV in data/ e chiede solo con quale persona entrare.
Online legge da st.secrets: [utenti] (nome = "password") e [github] (repo, token, ramo).
"""
from __future__ import annotations

import calendar
import hmac
import importlib
import io
import uuid
from datetime import date, datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ts.calcoli
import ts.store
import ts.theme

# dopo un push Streamlit Cloud riesegue app.py ma tiene in memoria i vecchi moduli di ts/:
# ricaricarli qui evita di dover riavviare l'app a mano a ogni pubblicazione
for _modulo in (ts.store, ts.calcoli, ts.theme):
    importlib.reload(_modulo)

from ts.calcoli import (STATI_SPESA, commessa_di, importi, num, ore_numeriche, riepilogo_mese, spese_valide, stato,
                        tipo_di)
from ts.store import ArchivioGitHub, ArchivioLocale
from ts.theme import (CSS, CSS_ACCESSO, CREAM, DEEP_FOREST, PLOTLY_TEMPLATE_NAME, ROSSO, SAGE_GREEN, chip,
                      etichetta_sezione, intestazione, logo, register_plotly_template)

DATI = Path(__file__).parent / "data"
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


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
    # le tabelle modificabili ripartono dai dati nuovi, senza modifiche in sospeso
    st.session_state["versione"] = st.session_state.get("versione", 0) + 1


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


def mese_breve(m: str) -> str:
    """'2026-11' → 'nov 2026'."""
    a, n = m.split("-")
    return f"{MESI_IT[int(n) - 1][:3]} {a}"


def mese_corrente() -> str:
    return date.today().strftime("%Y-%m")


def limiti_mese(mese: str) -> tuple[date, date]:
    a, m = map(int, mese.split("-"))
    return date(a, m, 1), date(a, m, calendar.monthrange(a, m)[1])


def ore_fmt(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",0")


def ore_hm(v) -> str:
    """Ore in ore e minuti: 1.5 → '1 h 30', 2 → '2 h', 0.5 → '30 min', -1.5 → '−1 h 30'."""
    if v is None or pd.isna(v):
        return "—"
    segno, minuti = ("−" if v < 0 else ""), round(abs(v) * 60)
    h, m = divmod(minuti, 60)
    if not h:
        return f"{segno}{m} min" if m else "0 h"
    return f"{segno}{h} h" + (f" {m:02d}" if m else "")


def ora_tendina(v: float) -> str:
    """Voce della tendina delle ore: 1.5 → '1:30', 0 → 'nessuna' (a forfait)."""
    if not v:
        return "nessuna"
    h, m = divmod(round(v * 60), 60)
    return f"{h}:{m:02d}"


def ore_da_tendina(voce) -> float | None:
    """Inverso di ora_tendina: '1:30' → 1.5, 'nessuna' → 0."""
    voce = str(voce or "").strip()
    if voce == "nessuna":
        return 0.0
    try:
        h, m = voce.split(":")
        return int(h) + int(m) / 60
    except ValueError:
        return None


def opzioni_ore(minime: float) -> list[float]:
    """Mezz'ore da 0:30 a 24:00; a forfait anche 0, cioè attività senza ore."""
    return ([0.0] if minime == 0 else []) + [i / 2 for i in range(1, 49)]


def euro_fmt(v) -> str:
    """1234.5 → '1.234,50 €'."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def quante(n: float, singolare: str, plurale: str) -> str:
    """quante(1, "ora", "ore") → '1 ora', quante(2.5, "ora", "ore") → '2,5 ore'."""
    return f"{ore_fmt(n)} {singolare if n == 1 else plurale}"


def data_it(s) -> str:
    """'2026-11-03' → '03/11/2026', '2026-11-03 11:43' → '03/11/2026 11:43'."""
    s = str(s)
    try:
        return datetime.fromisoformat(s).strftime("%d/%m/%Y %H:%M" if len(s) > 10 else "%d/%m/%Y")
    except ValueError:
        return s


def come_date(col: pd.Series) -> pd.Series:
    return pd.to_datetime(col, errors="coerce").dt.date


# ------------------------------------------------------------------ accesso
def accesso(persone: pd.DataFrame) -> dict | None:
    if "utente" in st.session_state:
        return st.session_state["utente"]
    attive = persone[persone["attiva"] != "no"]
    utenti = _segreti("utenti")
    st.markdown(CSS_ACCESSO, unsafe_allow_html=True)
    st.markdown(logo(etichetta="Timesheet collaboratori"), unsafe_allow_html=True)
    st.markdown('<div class="smc-login"><h1>Il timesheet di <em>SMACE</em></h1>'
                "<p>Le tue ore del mese, commessa per commessa.</p></div>", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        return _form_accesso(attive, utenti)


def _form_accesso(attive: pd.DataFrame, utenti) -> dict | None:
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
def barra_plafond(ore: float, plafond: float | None, tipo: str = "ore") -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Ore registrate", ore_hm(ore))
    if tipo == "forfait":
        c2.metric("Contratto", "Forfait")
        c3.metric("Plafond", "—")
        return
    c2.metric("Plafond", ore_hm(plafond) if plafond is not None else "da definire")
    if plafond is None:
        c3.metric("Residuo", "—")
        return
    c3.metric("Residuo", ore_hm(plafond - ore))
    st.progress(min(ore / plafond, 1.0) if plafond else 1.0)
    if ore > plafond:
        st.warning(f"Plafond superato di {ore_hm(ore - plafond)}. Le ore restano registrate: "
                   "il superamento va confermato fuori da questo strumento.")


def ultima_commessa(persona: str, commesse: pd.DataFrame) -> pd.Series | None:
    """Commessa più recente della persona: tipo e plafond si ripropongono come valori di partenza."""
    sue = commesse[commesse["persona"] == persona].sort_values("mese")
    return sue.iloc[-1] if len(sue) else None


TIPI = {"ore": "A ore, con plafond", "forfait": "A forfait"}


def periodo(mese: str) -> str:
    oggi = mese_corrente()
    return "in corso" if mese == oggi else ("chiusa" if mese < oggi else "futura")


def torna_all_elenco() -> None:
    if st.button("← Tutte le commesse"):
        st.session_state.pop("commessa", None)
        st.session_state.pop("nuova", None)
        st.rerun()


def elenco_commesse(utente: dict, persone, commesse, reg) -> None:
    st.markdown(intestazione("Timesheet · Commesse", "Commesse",
                             "Una commessa per persona e per mese, con il plafond di ore del contratto."),
                unsafe_allow_html=True)
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
    if not utente["admin"] and commessa_di(utente["nome"], mese_corrente(), commesse) is None:
        with st.container(border=True):
            a, b = st.columns([3, 1], vertical_alignment="center")
            a.markdown(f'<div class="smc-card-title">Non hai ancora aperto la commessa di '
                       f'{etichetta_mese(mese_corrente())}</div><div class="smc-card-sub">'
                       "Aprila con il plafond del tuo contratto per iniziare a registrare le ore.</div>",
                       unsafe_allow_html=True)
            if b.button("Apri commessa", type="primary", width="stretch", key="apri_mese"):
                st.session_state["nuova"] = True
                st.rerun()

    if viste.empty:
        st.caption("Nessuna commessa. A inizio mese si apre quella del mese con \"Nuova commessa\".")
        return
    ore = ore_numeriche(reg).groupby("commessa")["ore"].sum()
    st.markdown(etichetta_sezione("Dalla più recente"), unsafe_allow_html=True)
    for _, c in viste.sort_values(["mese", "persona"], ascending=[False, True]).iterrows():
        o, pl, tipo = float(ore.get(c["id"], 0.0)), num(c["plafond"]), tipo_di(c)
        with st.container(border=True):
            a, b, d, e = st.columns([3, 2, 2, 1], vertical_alignment="center")
            a.markdown(f'<div class="smc-card-title">{escape(c["persona"])} · {etichetta_mese(c["mese"])}</div>'
                       f'<div class="smc-card-sub">{periodo(c["mese"])}</div>', unsafe_allow_html=True)
            b.markdown(ore_hm(o) if tipo == "forfait" else f"{ore_hm(o)} / {ore_hm(pl)}")
            d.markdown(chip(stato(o, pl, tipo)), unsafe_allow_html=True)
            if e.button("Apri", key=f"apri_{c['id']}", width="stretch"):
                st.session_state["commessa"] = c["id"]
                st.rerun()


def nuova_commessa(utente: dict, persone, commesse) -> None:
    torna_all_elenco()
    st.markdown(intestazione("Timesheet · Commesse", "Nuova commessa"), unsafe_allow_html=True)
    if utente["admin"]:
        attive = list(persone.loc[persone["attiva"] != "no", "nome"])
        persona = st.selectbox("Persona", attive, index=attive.index(utente["nome"]) if utente["nome"] in attive else 0)
    else:
        persona = utente["nome"]
    occupati = set(commesse.loc[commesse["persona"] == persona, "mese"])
    mesi = [m for m in elenco_mesi(commesse) if m not in occupati]
    mese = st.selectbox("Mese", mesi, index=mesi.index(mese_corrente()) if mese_corrente() in mesi else 0,
                        format_func=etichetta_mese)
    ultima = ultima_commessa(persona, commesse)
    tipo = st.radio("Tipo di contratto", list(TIPI), format_func=TIPI.get, horizontal=True,
                    index=list(TIPI).index(tipo_di(ultima)))
    if tipo == "forfait":
        st.caption("A forfait non c'è plafond: registri le attività svolte, le ore sono facoltative.")
        plafond = None
    else:
        st.caption("Si apre a inizio mese, con il plafond di ore previsto dal tuo contratto.")
        plafond = st.number_input("Plafond del mese (ore)", min_value=0.0, step=1.0,
                                  value=num(ultima["plafond"]) if ultima is not None else None,
                                  placeholder="es. 26")
    if st.button(f"Apri commessa {persona} · {etichetta_mese(mese)}", type="primary",
                 disabled=tipo == "ore" and not plafond):
        nuovo_id = uuid.uuid4().hex[:8]
        aggiungi("commesse", {"id": nuovo_id, "persona": persona, "mese": mese, "tipo": tipo,
                              "plafond": str(plafond) if plafond else "", "aperta_il": adesso(),
                              "aperta_da": utente["nome"]},
                 f"Commessa aperta: {persona} {mese}")
        st.session_state.pop("nuova", None)
        st.session_state["commessa"] = nuovo_id
        st.rerun()


def modifica_commessa(comm: pd.Series) -> None:
    with st.expander("Tipo e plafond"):
        tipo = st.radio("Tipo di contratto", list(TIPI), format_func=TIPI.get, horizontal=True,
                        index=list(TIPI).index(tipo_di(comm)), key=f"tipo_{comm['id']}")
        nuovo = None
        if tipo == "ore":
            nuovo = st.number_input("Plafond del mese (ore)", min_value=0.0, step=1.0,
                                    value=num(comm["plafond"]), key=f"pl_{comm['id']}")
        invariata = tipo == tipo_di(comm) and nuovo == num(comm["plafond"])
        if st.button("Salva", disabled=invariata or (tipo == "ore" and not nuovo)):
            valori = [tipo, str(nuovo) if nuovo else ""]

            def applica(df: pd.DataFrame) -> pd.DataFrame:
                df = df.copy()
                df.loc[df["id"] == comm["id"], ["tipo", "plafond"]] = valori
                return df

            scrivi("commesse", applica, f"Commessa {comm['persona']} {comm['mese']}: {tipo} {valori[1]}")
            st.rerun()


def dettaglio_commessa(comm: pd.Series, reg, spese) -> None:
    torna_all_elenco()
    persona, mese = comm["persona"], comm["mese"]
    st.markdown(intestazione(f"Commessa · {periodo(mese)}", f"{persona} · {etichetta_mese(mese)}",
                             f"Aperta il {data_it(comm['aperta_il'])} da {comm['aperta_da']}"), unsafe_allow_html=True)
    mie = reg[reg["commessa"] == comm["id"]]
    barra_plafond(float(ore_numeriche(mie)["ore"].sum()), num(comm["plafond"]), tipo_di(comm))
    modifica_commessa(comm)
    calendario_mese(mie, mese)
    registra_ore(comm, reg)
    if msg := st.session_state.pop("esito", None):
        st.success(msg)
    ore_registrate(comm, mie)
    spese_commessa(comm, spese[spese["commessa"] == comm["id"]])


def ore_minime(comm: pd.Series) -> float:
    """A forfait le ore sono facoltative (0 = solo attività)."""
    return 0.0 if tipo_di(comm) == "forfait" else 0.5


def registra_ore(comm: pd.Series, reg: pd.DataFrame) -> None:
    persona, mese = comm["persona"], comm["mese"]
    primo, ultimo = limiti_mese(mese)
    minime = ore_minime(comm)
    with st.form("nuove_ore", clear_on_submit=True):
        st.markdown(etichetta_sezione("Registra attività" if minime == 0 else "Registra ore"), unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 3, 1])
        giorno = c1.date_input("Giorno", value=min(max(date.today(), primo), ultimo),
                               min_value=primo, max_value=ultimo, format="DD/MM/YYYY")
        att = c2.selectbox("Attività", attivita_recenti(persona, reg), index=None, accept_new_options=True,
                           placeholder="Scrivi l'attività o scegline una già usata")
        scelte = opzioni_ore(minime)
        ore = c3.selectbox("Ore" + (" (facoltative)" if minime == 0 else ""), scelte, format_func=ora_tendina,
                           index=scelte.index(0.0 if minime == 0 else 1.0))
        note = st.text_input("Note (facoltative)")
        if st.form_submit_button("Registra", type="primary"):
            if not (att or "").strip():
                st.error("Scrivi l'attività svolta.")
                return
            aggiungi("registrazioni", {
                "id": uuid.uuid4().hex[:8], "commessa": comm["id"], "persona": persona, "mese": mese,
                "data": giorno.isoformat(), "attivita": att.strip(), "ore": str(ore),
                "note": note.strip(), "inserita_il": adesso()},
                f"{persona}: {ore_fmt(ore)} h il {giorno.isoformat()}")
            st.session_state["esito"] = (f"Registrata l'attività del {giorno.strftime('%d/%m')}." if not ore else
                                         f"Registrate {ore_hm(ore)} il {giorno.strftime('%d/%m')}.")
            st.rerun()


def ore_registrate(comm: pd.Series, mie: pd.DataFrame) -> None:
    if mie.empty:
        st.caption("Nessuna attività registrata in questa commessa.")
        return
    primo, ultimo = limiti_mese(comm["mese"])
    st.markdown(etichetta_sezione("Attività registrate"), unsafe_allow_html=True)
    st.caption("Per correggere una riga modificala direttamente nella tabella e premi \"Salva modifiche\".")
    tab = tabella_registrazioni(mie)
    # le voci della tendina più eventuali valori vecchi fuori dalle mezz'ore, perché restino visibili
    voci = list(dict.fromkeys([ora_tendina(v) for v in opzioni_ore(ore_minime(comm))] + list(tab["ore"])))
    ed = st.data_editor(tab, hide_index=True, width="stretch", disabled=["id"],
                        column_config={
                            "id": None,
                            "elimina": st.column_config.CheckboxColumn("Elimina", width="small"),
                            "data": st.column_config.DateColumn("Giorno", format="DD/MM/YYYY", required=True,
                                                                min_value=primo, max_value=ultimo),
                            "attivita": st.column_config.TextColumn("Attività", required=True, width="large"),
                            "ore": st.column_config.SelectboxColumn("Ore", options=voci, required=True),
                            "note": st.column_config.TextColumn("Note")},
                        key=f"ed_{comm['id']}_{st.session_state.get('versione', 0)}")
    salva_modifiche(comm, tab, ed)
    conferma_eliminazione(comm, mie, ed)


def attivita_recenti(persona: str, reg: pd.DataFrame, quante: int = 30) -> list[str]:
    """Attività già scritte dalla persona, dalla più recente: si scelgono invece di riscriverle."""
    sue = reg[reg["persona"] == persona].sort_values("inserita_il", ascending=False)
    return list(dict.fromkeys(a.strip() for a in sue["attivita"] if a.strip()))[:quante]


def tabella_registrazioni(mie: pd.DataFrame) -> pd.DataFrame:
    tab = mie[["id", "data", "attivita", "ore", "note"]].sort_values(["data"]).copy()
    tab["data"] = come_date(tab["data"])
    tab["ore"] = tab["ore"].map(lambda v: ora_tendina(num(v) or 0.0))
    tab.insert(0, "elimina", False)
    return tab.reset_index(drop=True)


CAMPI_REG = ["data", "attivita", "ore", "note"]


def righe_modificate(prima: pd.DataFrame, dopo: pd.DataFrame) -> pd.DataFrame:
    a = prima.set_index("id")[CAMPI_REG].fillna("").astype(str)
    b = dopo.set_index("id")[CAMPI_REG].fillna("").astype(str)
    diverse = (a != b.loc[a.index]).any(axis=1)
    return dopo[dopo["id"].isin(diverse[diverse].index)]


def salva_modifiche(comm: pd.Series, prima: pd.DataFrame, dopo: pd.DataFrame) -> None:
    mod = righe_modificate(prima, dopo)
    if mod.empty:
        return
    primo, ultimo = limiti_mese(comm["mese"])
    minime = ore_minime(comm)
    errori = [r for _, r in mod.iterrows()
              if not str(r["attivita"] or "").strip() or ore_da_tendina(r["ore"]) is None
              or not minime <= ore_da_tendina(r["ore"]) <= 24
              or pd.isna(r["data"]) or not primo <= r["data"] <= ultimo]
    if errori:
        st.error(f"Controlla le righe modificate: servono giorno del mese, attività e ore "
                 f"(tra {ora_tendina(minime)} e 24:00).")
        return
    if st.button(f"Salva modifiche ({quante(len(mod), 'riga', 'righe')})", type="primary"):
        nuovi = {r["id"]: [r["data"].isoformat(), str(r["attivita"]).strip(), str(ore_da_tendina(r["ore"])),
                           str(r["note"] or "").strip()] for _, r in mod.iterrows()}

        def applica(df: pd.DataFrame) -> pd.DataFrame:
            df = df.copy()
            for i, valori in nuovi.items():
                df.loc[df["id"] == i, CAMPI_REG] = valori
            return df

        scrivi("registrazioni", applica, f"{comm['persona']}: modificate {len(nuovi)} registrazioni ({comm['mese']})")
        st.session_state["esito"] = "Modifiche salvate."
        st.rerun()


def conferma_eliminazione(comm: pd.Series, mie: pd.DataFrame, ed: pd.DataFrame) -> None:
    da_togliere = sorted(ed.loc[ed["elimina"], "id"])
    if not da_togliere:
        st.session_state.pop("da_eliminare", None)
        return
    if st.session_state.get("da_eliminare") != da_togliere:
        if st.button(f"Elimina {quante(len(da_togliere), 'registrazione selezionata', 'registrazioni selezionate')}"):
            st.session_state["da_eliminare"] = da_togliere
            st.rerun()
        return
    ore = ore_numeriche(mie[mie["id"].isin(da_togliere)])["ore"].sum()
    st.warning(f"Stai per eliminare {quante(len(da_togliere), 'registrazione', 'registrazioni')} "
               f"({ore_hm(ore)}). "
               "L'operazione non si può annullare.")
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Sì, elimina", type="primary", width="stretch"):
        scrivi("registrazioni", lambda df: df[~df["id"].isin(da_togliere)],
               f"{comm['persona']}: eliminate {len(da_togliere)} registrazioni ({comm['mese']})")
        st.session_state.pop("da_eliminare", None)
        st.session_state["esito"] = ("Eliminata 1 registrazione." if len(da_togliere) == 1
                                     else f"Eliminate {len(da_togliere)} registrazioni.")
        st.rerun()
    if c2.button("Annulla", width="stretch"):
        st.session_state.pop("da_eliminare", None)
        st.session_state["versione"] = st.session_state.get("versione", 0) + 1  # toglie le spunte
        st.rerun()


def calendario_mese(mie: pd.DataFrame, mese: str) -> None:
    """Griglia lun-dom del mese: in lime i giorni con attività registrate, per vedere subito quelli dimenticati."""
    a, m = map(int, mese.split("-"))
    ore = ore_numeriche(mie).groupby("data")["ore"].sum()  # a forfait un giorno può avere attività a 0 ore
    celle = [f'<div class="smc-cal-h">{g}</div>' for g in ("lun", "mar", "mer", "gio", "ven", "sab", "dom")]
    for settimana in calendar.Calendar().monthdatescalendar(a, m):
        for g in settimana:
            if g.month != m:
                celle.append('<div class="smc-cal-d fuori"></div>')
                continue
            h = ore.get(g.isoformat())
            classi = " ".join(["smc-cal-d"] + ["piena"] * (h is not None) + ["weekend"] * (g.weekday() >= 5)
                              + ["oggi"] * (g == date.today()))
            celle.append(f'<div class="{classi}"><span>{g.day}</span><b>{ore_hm(h) if h else ""}</b></div>')
    giorni = len(ore)
    st.markdown(etichetta_sezione(f"Giorni del mese · {giorni} con attività registrate")
                + f'<div class="smc-cal">{"".join(celle)}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ spese
CATEGORIE = ["Viaggio e trasporti", "Vitto", "Alloggio", "Materiali", "Altro"]


def tabella_spese(spese: pd.DataFrame, con_persona: bool = False) -> str:
    """Spese come tabella HTML, con lo stato a pillola."""
    colonne = (["Persona"] if con_persona else []) + ["Giorno", "Categoria", "Descrizione", "Riferimento",
                                                     "Importo", "Stato"]
    testa = "".join(f'<th class="{"num" if c == "Importo" else ""}">{c}</th>' for c in colonne)
    righe = "".join(
        "<tr>" + (f"<td>{escape(r.persona)}</td>" if con_persona else "")
        + f"<td>{data_it(r.data)}</td><td>{escape(r.categoria)}</td><td>{escape(r.descrizione)}</td>"
        f"<td>{escape(r.riferimento)}</td><td class=\"num\">{euro_fmt(r.importo)}</td><td>{chip(r.stato)}</td></tr>"
        for r in importi(spese).sort_values("data").itertuples())
    return f'<table class="smc-table"><thead><tr>{testa}</tr></thead><tbody>{righe}</tbody></table>'


def spese_commessa(comm: pd.Series, sue: pd.DataFrame) -> None:
    """Spese da rimborsare della commessa: le inserisce il collaboratore, le approva l'admin."""
    st.markdown(etichetta_sezione("Spese da rimborsare"), unsafe_allow_html=True)
    with st.form("nuova_spesa", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1.6, 1.4])
        giorno = c1.date_input("Giorno", value=date.today(), format="DD/MM/YYYY")
        categoria = c2.selectbox("Categoria", CATEGORIE)
        # parte vuoto: scrivendo su "0,00" le cifre finivano in coda (0,00125)
        importo = c3.number_input("Importo (€)", min_value=0.0, step=1.0, format="%.2f", value=None,
                                  placeholder="es. 18,60")
        c4, c5 = st.columns([3, 2])
        descrizione = c4.text_input("Descrizione", placeholder="es. treno Milano-Ferrara per evento")
        riferimento = c5.text_input("Riferimento giustificativo (facoltativo)", placeholder="es. scontrino n. 123")
        if st.form_submit_button("Aggiungi spesa", type="primary"):
            if not importo or not descrizione.strip():
                st.error("Servono importo e descrizione.")
                return
            aggiungi("spese", {
                "id": uuid.uuid4().hex[:8], "commessa": comm["id"], "persona": comm["persona"], "mese": comm["mese"],
                "data": giorno.isoformat(), "categoria": categoria, "descrizione": descrizione.strip(),
                "riferimento": riferimento.strip(), "importo": f"{importo:.2f}", "stato": "da approvare",
                "inserita_il": adesso()},
                f"{comm['persona']}: spesa {importo:.2f} € ({comm['mese']})")
            st.session_state["esito_spesa"] = f"Spesa di {euro_fmt(importo)} inviata all'approvazione."
            st.rerun()
    if msg := st.session_state.pop("esito_spesa", None):
        st.success(msg)
    if sue.empty:
        st.caption("Nessuna spesa in questa commessa.")
        return
    st.markdown(tabella_spese(sue), unsafe_allow_html=True)
    st.caption(f"Totale {euro_fmt(spese_valide(sue)['importo'].sum())}, escluse le spese respinte.")
    ritira_spesa(comm, sue[sue["stato"] == "da approvare"])


def ritira_spesa(comm: pd.Series, pendenti: pd.DataFrame) -> None:
    """Una spesa si può togliere finché l'admin non l'ha approvata."""
    if pendenti.empty:
        return
    with st.expander("Ritira una spesa non ancora approvata"):
        etichette = {r.id: f"{data_it(r.data)} · {r.descrizione} · {euro_fmt(r.importo)}"
                     for r in importi(pendenti).itertuples()}
        scelta = st.selectbox("Spesa", list(etichette), format_func=etichette.get, index=None,
                              placeholder="Scegli la spesa da ritirare")
        if st.button("Ritira spesa", disabled=scelta is None):
            scrivi("spese", lambda df: df[df["id"] != scelta], f"{comm['persona']}: spesa ritirata ({comm['mese']})")
            st.session_state["esito_spesa"] = "Spesa ritirata."
            st.rerun()


def vista_spese(utente: dict, spese: pd.DataFrame) -> None:
    st.markdown(intestazione("Timesheet · Spese", "Spese da rimborsare",
                             "L'admin approva le spese e le segna come rimborsate dopo il pagamento."
                             if utente["admin"] else "Le tue spese e a che punto è il rimborso."),
                unsafe_allow_html=True)
    if not utente["admin"]:
        spese = spese[spese["persona"] == utente["nome"]]
    if spese.empty:
        st.caption("Nessuna spesa registrata. Le spese si inseriscono dentro la commessa del mese.")
        return
    imp = importi(spese)
    c1, c2, c3 = st.columns(3)
    for col, s, titolo in ((c1, "da approvare", "Da approvare"), (c2, "approvata", "Da rimborsare")):
        sel = imp[imp["stato"] == s]
        col.metric(f"{titolo} ({len(sel)})", euro_fmt(sel["importo"].sum()),
                   help="Spese approvate, in attesa del bonifico." if s == "approvata" else None)
    rimb = imp[(imp["stato"] == "rimborsata") & imp["rimborsata_il"].str.startswith(mese_corrente())]
    c3.metric("Rimborsate nel mese", euro_fmt(rimb["importo"].sum()))

    if msg := st.session_state.pop("esito_rimborso", None):
        st.success(msg)
    mostra = st.segmented_control("Mostra", ["Da gestire", "Tutte"], default="Da gestire", key="filtro_spese")
    if mostra != "Tutte":
        spese = spese[spese["stato"].isin(["da approvare", "approvata"])]
    if spese.empty:
        st.caption("Nessuna spesa da gestire.")
    elif utente["admin"]:
        gestione_stati(spese, utente)
        da_rimborsare_per_persona(imp, utente)
    else:
        st.markdown(tabella_spese(spese), unsafe_allow_html=True)


def gestione_stati(spese: pd.DataFrame, utente: dict) -> None:
    st.caption("Per approvare, respingere o segnare come rimborsata una spesa: doppio clic sulla sua cella "
               "\"Stato\", scegli il nuovo stato e premi \"Salva stato\". Per rimborsare in un colpo tutte le "
               "spese approvate di una persona usa il pulsante in fondo alla pagina. Una spesa inserita per "
               "errore si cancella con la spunta \"Elimina\".")
    tab = importi(spese).sort_values(["data", "persona"]).assign(
        data=lambda d: come_date(d["data"]), rimborsata_il=lambda d: come_date(d["rimborsata_il"]),
        importo=lambda d: d["importo"].map(euro_fmt), mese=lambda d: d["mese"].map(mese_breve))
    tab = tab[["id", "stato", "persona", "importo", "data", "categoria", "descrizione", "riferimento", "mese",
               "rimborsata_il"]].reset_index(drop=True)
    tab.insert(0, "elimina", False)
    # larghezze fisse e strette: tutte le colonne stanno nella pagina senza scorrere di lato
    ed = st.data_editor(tab, hide_index=True, width="stretch", key=f"ed_spese_{st.session_state.get('versione', 0)}",
                        disabled=[c for c in tab.columns if c not in ("stato", "elimina")],
                        column_config={
                            "id": None,
                            "elimina": st.column_config.CheckboxColumn("Elimina", width=70),
                            "stato": st.column_config.SelectboxColumn("Stato", options=STATI_SPESA, required=True,
                                                                      width=110),
                            "persona": st.column_config.TextColumn("Persona", width=110),
                            "importo": st.column_config.TextColumn("Importo", width=80),
                            "data": st.column_config.DateColumn("Giorno", format="DD/MM/YYYY", width=90),
                            "categoria": st.column_config.TextColumn("Categoria", width=130),
                            "descrizione": st.column_config.TextColumn("Descrizione", width=200),
                            "riferimento": st.column_config.TextColumn("Riferimento", width=100),
                            "mese": st.column_config.TextColumn("Commessa", width=80),
                            "rimborsata_il": st.column_config.DateColumn("Rimborsata il", format="DD/MM/YYYY",
                                                                         width=100)})
    cambi = {i: s for i, s, prima in zip(ed["id"], ed["stato"], tab["stato"]) if s != prima}
    if cambi and st.button(f"Salva stato ({quante(len(cambi), 'spesa', 'spese')})", type="primary"):
        scrivi("spese", lambda df: applica_stati(df, cambi, utente["nome"]),
               f"Spese: aggiornato lo stato di {len(cambi)}")
        st.rerun()
    elimina_spese(spese, sorted(ed.loc[ed["elimina"], "id"]))


def elimina_spese(spese: pd.DataFrame, da_togliere: list[str]) -> None:
    """Cancellazione definitiva, solo admin, con conferma come per le ore registrate."""
    if not da_togliere:
        st.session_state.pop("spese_da_eliminare", None)
        return
    if st.session_state.get("spese_da_eliminare") != da_togliere:
        if st.button(f"Elimina {quante(len(da_togliere), 'spesa selezionata', 'spese selezionate')}"):
            st.session_state["spese_da_eliminare"] = da_togliere
            st.rerun()
        return
    totale = importi(spese[spese["id"].isin(da_togliere)])["importo"].sum()
    st.warning(f"Stai per eliminare {quante(len(da_togliere), 'spesa', 'spese')} ({euro_fmt(totale)}). "
               "L'operazione non si può annullare.")
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Sì, elimina", type="primary", width="stretch", key="conferma_elimina_spese"):
        scrivi("spese", lambda df: df[~df["id"].isin(da_togliere)], f"Spese: eliminate {len(da_togliere)}")
        st.session_state.pop("spese_da_eliminare", None)
        st.session_state["esito_rimborso"] = ("Eliminata 1 spesa." if len(da_togliere) == 1
                                              else f"Eliminate {len(da_togliere)} spese.")
        st.rerun()
    if c2.button("Annulla", width="stretch", key="annulla_elimina_spese"):
        st.session_state.pop("spese_da_eliminare", None)
        st.session_state["versione"] = st.session_state.get("versione", 0) + 1  # toglie le spunte
        st.rerun()


def applica_stati(df: pd.DataFrame, cambi: dict, admin: str) -> pd.DataFrame:
    """Nuovo stato delle spese, con chi ha approvato e quando è stata rimborsata."""
    df = df.copy()
    for i, s in cambi.items():
        riga = df["id"] == i
        df.loc[riga, "stato"] = s
        if s in ("approvata", "rimborsata") and not df.loc[riga, "approvata_il"].iloc[0]:
            df.loc[riga, ["approvata_il", "approvata_da"]] = [adesso(), admin]
        if s in ("da approvare", "respinta"):
            df.loc[riga, ["approvata_il", "approvata_da"]] = ["", ""]
        df.loc[riga, "rimborsata_il"] = date.today().isoformat() if s == "rimborsata" else ""
    return df


def da_rimborsare_per_persona(imp: pd.DataFrame, utente: dict) -> None:
    """Quanto bonificare a ciascuno, con il pulsante per segnare il bonifico come fatto."""
    approvate = imp[imp["stato"] == "approvata"]
    if approvate.empty:
        return
    st.markdown(etichetta_sezione("Da rimborsare per persona"), unsafe_allow_html=True)
    st.caption("Dopo il bonifico premi \"Segna come rimborsate\": le spese approvate della persona passano a "
               "rimborsate con la data di oggi.")
    for persona, sue in approvate.groupby("persona"):
        with st.container(border=True):
            a, b, c = st.columns([3, 2, 2], vertical_alignment="center")
            a.markdown(f'<div class="smc-card-title">{escape(persona)}</div><div class="smc-card-sub">'
                       f'{quante(len(sue), "spesa approvata", "spese approvate")}</div>', unsafe_allow_html=True)
            b.markdown(f'<div class="smc-card-title">{euro_fmt(sue["importo"].sum())}</div>', unsafe_allow_html=True)
            if c.button("Segna come rimborsate", key=f"rimborsa_{persona}", width="stretch"):
                cambi = dict.fromkeys(sue["id"], "rimborsata")
                scrivi("spese", lambda df: applica_stati(df, cambi, utente["nome"]),
                       f"Spese: rimborsate {len(cambi)} di {persona}")
                st.session_state["esito_rimborso"] = (f"Segnate come rimborsate le spese di {persona} "
                                                      f"({euro_fmt(sue['importo'].sum())}).")
                st.rerun()


def vista_commesse(utente: dict, persone, commesse, reg, spese) -> None:
    if not utente["admin"] and not st.session_state.get("atterrato"):
        # appena entrato, il collaboratore va dritto alla commessa del mese in corso, se c'è
        st.session_state["atterrato"] = True
        corrente = commessa_di(utente["nome"], mese_corrente(), commesse)
        if corrente is not None:
            st.session_state["commessa"] = corrente["id"]
    sel = st.session_state.get("commessa")
    comm = commesse[commesse["id"] == sel]
    if sel and len(comm) and (utente["admin"] or comm.iloc[0]["persona"] == utente["nome"]):
        dettaglio_commessa(comm.iloc[0], reg, spese)
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
                    marker=dict(symbol="line-ew-open", size=40, color=SAGE_GREEN, line=dict(width=3, color=SAGE_GREEN)))
    fig.update_layout(title="Ore contro plafond", height=360, showlegend=True, template=PLOTLY_TEMPLATE_NAME,
                      title_x=0.01, paper_bgcolor="#fff", plot_bgcolor="#fff")
    return fig


COLONNE_RIEPILOGO = {"persona": "Persona", "ore": "Ore", "plafond": "Plafond", "residuo": "Residuo", "stato": "Stato",
                     "spese": "Spese (€)"}
COLONNE_DETTAGLIO = {"persona": "Persona", "data": "Giorno", "attivita": "Attività", "ore": "Ore", "note": "Note",
                     "inserita_il": "Inserita il"}
COLONNE_SPESE = {"persona": "Persona", "data": "Giorno", "categoria": "Categoria", "descrizione": "Descrizione",
                 "riferimento": "Riferimento", "importo": "Importo (€)", "stato": "Stato",
                 "approvata_il": "Approvata il", "approvata_da": "Approvata da", "rimborsata_il": "Rimborsata il"}


def tabella_riepilogo(riep: pd.DataFrame) -> str:
    """Riepilogo come tabella HTML, per avere lo stato a pillola come nell'elenco commesse."""
    def cella(v, rossa=False):
        return f'<td class="num{" neg" if rossa else ""}">{ore_hm(v)}</td>'

    righe = "".join(
        f"<tr><td>{escape(r.persona)}</td>{cella(r.ore)}{cella(r.plafond)}"
        f"{cella(r.residuo, pd.notna(r.residuo) and r.residuo < 0)}<td>{chip(r.stato)}</td>"
        f'<td class="num">{euro_fmt(r.spese) if r.spese else "—"}</td></tr>'
        for r in riep.itertuples())
    testa = "".join(f'<th class="{"num" if c in ("ore", "plafond", "residuo", "spese") else ""}">{t}</th>'
                    for c, t in COLONNE_RIEPILOGO.items())
    return f'<table class="smc-table"><thead><tr>{testa}</tr></thead><tbody>{righe}</tbody></table>'


def excel_mese(riep, dettaglio, spese=None) -> bytes:
    dett = dettaglio.assign(data=come_date(dettaglio["data"]),
                            inserita_il=pd.to_datetime(dettaglio["inserita_il"], errors="coerce"))
    if spese is None:
        spese = pd.DataFrame(columns=list(COLONNE_SPESE))
    sp = importi(spese)[list(COLONNE_SPESE)].sort_values(["persona", "data"]).assign(
        data=lambda d: come_date(d["data"]), rimborsata_il=lambda d: come_date(d["rimborsata_il"]),
        approvata_il=lambda d: pd.to_datetime(d["approvata_il"], errors="coerce"))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl", date_format="DD/MM/YYYY", datetime_format="DD/MM/YYYY HH:MM") as xw:
        riep.rename(columns=COLONNE_RIEPILOGO).to_excel(xw, sheet_name="Commesse", index=False)
        dett.rename(columns=COLONNE_DETTAGLIO).to_excel(xw, sheet_name="Dettaglio", index=False)
        sp.rename(columns=COLONNE_SPESE).to_excel(xw, sheet_name="Spese", index=False)
        for foglio, larghezze in (("Commesse", [22, 10, 10, 10, 22, 12]), ("Dettaglio", [22, 12, 50, 8, 30, 18]),
                                  ("Spese", [22, 12, 20, 40, 20, 12, 14, 18, 16, 14])):
            for i, w in enumerate(larghezze):
                xw.sheets[foglio].column_dimensions[chr(65 + i)].width = w
    return buf.getvalue()


def vista_riepilogo(utente: dict, persone, commesse, reg, spese) -> None:
    st.markdown(intestazione("Timesheet · Riepilogo", "Riepilogo del mese",
                             "Ore, plafond, residuo e spese di ciascuno, con l'export Excel per la chiusura."),
                unsafe_allow_html=True)
    mesi = elenco_mesi(commesse)
    mese = st.selectbox("Mese", mesi, index=mesi.index(mese_corrente()), format_func=etichetta_mese, key="mese_riep")
    if not utente["admin"]:
        reg = reg[reg["persona"] == utente["nome"]]
        persone = persone[persone["nome"] == utente["nome"]]
        commesse = commesse[commesse["persona"] == utente["nome"]]
        spese = spese[spese["persona"] == utente["nome"]]
    riep = riepilogo_mese(mese, reg, persone, commesse, spese)
    spese_mese = spese[spese["mese"] == mese]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ore totali", ore_hm(riep["ore"].sum()))
    c2.metric("Commesse aperte", int((riep["stato"] != "commessa non aperta").sum()))
    c3.metric("Oltre plafond", int((riep["stato"] == "oltre plafond").sum()))
    c4.metric("Spese del mese", euro_fmt(riep["spese"].sum()))

    if riep["ore"].sum() > 0:
        st.plotly_chart(grafico_plafond(riep), width="stretch", theme=None)
    st.markdown(tabella_riepilogo(riep), unsafe_allow_html=True)

    dettaglio = ore_numeriche(reg[reg["mese"] == mese]).sort_values(["persona", "data", "inserita_il"])
    dettaglio = dettaglio[["persona", "data", "attivita", "ore", "note", "inserita_il"]]
    with st.expander(f"Dettaglio registrazioni ({len(dettaglio)})"):
        st.dataframe(dettaglio.assign(data=come_date(dettaglio["data"]),
                                      inserita_il=dettaglio["inserita_il"].map(data_it),
                                      ore=dettaglio["ore"].map(lambda v: ore_hm(v) if v else "—")),
                     hide_index=True, width="stretch",
                     column_config={"persona": "Persona", "attivita": "Attività", "note": "Note",
                                    "inserita_il": "Inserita il", "ore": "Ore",
                                    "data": st.column_config.DateColumn("Giorno", format="DD/MM/YYYY")})
    if not spese_mese.empty:
        with st.expander(f"Spese del mese ({len(spese_mese)})"):
            st.markdown(tabella_spese(spese_mese, con_persona=True), unsafe_allow_html=True)
    st.download_button("Scarica Excel del mese", excel_mese(riep, dettaglio, spese_mese),
                       file_name=f"timesheet_smace_{mese}.xlsx", type="primary",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ------------------------------------------------------------------ impostazioni
def vista_impostazioni(persone, commesse) -> None:
    st.markdown(intestazione("Timesheet · Admin", "Impostazioni",
                             "Le password non stanno qui: si impostano nei secrets dell'app, una per persona."),
                unsafe_allow_html=True)

    st.markdown(etichetta_sezione("Persone"), unsafe_allow_html=True)
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

    st.markdown(etichetta_sezione("Commesse"), unsafe_allow_html=True)
    st.caption("Qui si corregge il plafond di una commessa già aperta.")
    tab = commesse.sort_values(["mese", "persona"], ascending=[False, True]).assign(
        mese=lambda d: d["mese"].map(etichetta_mese), plafond=lambda d: d["plafond"].map(num),
        aperta_il=lambda d: d["aperta_il"].map(data_it), tipo=lambda d: d["tipo"].replace("", "ore"))
    ed_c = st.data_editor(tab, hide_index=True, width="stretch", key=f"ed_commesse_{st.session_state.get('versione', 0)}",
                          disabled=["id", "persona", "mese", "aperta_il", "aperta_da", "tipo"],
                          column_config={"id": None, "persona": "Persona", "mese": "Mese", "tipo": "Tipo",
                                         "plafond": st.column_config.NumberColumn("Plafond (ore)", min_value=0.0,
                                                                                  step=1.0, format="localized"),
                                         "aperta_il": "Aperta il", "aperta_da": "Aperta da"})
    if st.button("Salva plafond delle commesse"):
        # si riscrivono solo i plafond cambiati, gli altri restano com'erano nel CSV
        prima = dict(zip(tab["id"], tab["plafond"]))
        nuovi = {i: "" if pd.isna(v) else str(float(v)) for i, v in zip(ed_c["id"], ed_c["plafond"])
                 if not (pd.isna(v) and pd.isna(prima[i])) and v != prima[i]}
        if nuovi:
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
    commesse, reg, spese = leggi("commesse"), leggi("registrazioni"), leggi("spese")

    st.sidebar.markdown(logo(CREAM, 130), unsafe_allow_html=True)
    st.sidebar.markdown(etichetta_sezione("Timesheet"), unsafe_allow_html=True)
    st.sidebar.caption(f"{utente['nome']}{' · admin' if utente['admin'] else ''}")
    viste = ["Commesse", "Spese", "Riepilogo"] + (["Impostazioni"] if utente["admin"] else [])
    vista = st.sidebar.radio("Vista", viste, label_visibility="collapsed")
    st.sidebar.markdown("---")
    if st.sidebar.button("Esci"):
        st.session_state.clear()
        st.rerun()

    if vista == "Commesse":
        vista_commesse(utente, persone, commesse, reg, spese)
    elif vista == "Spese":
        vista_spese(utente, spese)
    elif vista == "Riepilogo":
        vista_riepilogo(utente, persone, commesse, reg, spese)
    else:
        vista_impostazioni(persone, commesse)


if __name__ == "__main__":
    main()
