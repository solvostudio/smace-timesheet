import pandas as pd

from ts.calcoli import commessa_di, riepilogo_mese
from ts.store import ArchivioLocale

PERSONE = pd.DataFrame([
    {"nome": "Admin", "ruolo": "admin", "attiva": "sì"},
    {"nome": "Mario", "ruolo": "collaboratore", "attiva": "sì"},
    {"nome": "Ex", "ruolo": "collaboratore", "attiva": "no"},
])
COMMESSE = pd.DataFrame([
    {"id": "a10", "persona": "Mario", "mese": "2026-10", "plafond": "26"},
    {"id": "a11", "persona": "Mario", "mese": "2026-11", "plafond": "40"},
    {"id": "l10", "persona": "Admin", "mese": "2026-10", "plafond": ""},
])
REG = pd.DataFrame([
    {"commessa": "a10", "persona": "Mario", "mese": "2026-10", "attivita": "Chiusura contabile", "ore": "20"},
    {"commessa": "a10", "persona": "Mario", "mese": "2026-10", "attivita": "Call fornitore", "ore": "8,5"},
    {"commessa": "a11", "persona": "Mario", "mese": "2026-11", "attivita": "M&A", "ore": "30"},
])


def test_commessa_di():
    assert commessa_di("Mario", "2026-11", COMMESSE)["plafond"] == "40"
    assert commessa_di("Mario", "2026-12", COMMESSE) is None


def test_riepilogo_stati():
    r = riepilogo_mese("2026-10", REG, PERSONE, COMMESSE).set_index("persona")
    assert r.loc["Mario", "ore"] == 28.5 and r.loc["Mario", "stato"] == "oltre plafond"
    assert r.loc["Admin", "stato"] == "plafond da definire"
    assert "Ex" not in r.index  # non attiva e senza commessa
    r11 = riepilogo_mese("2026-11", REG, PERSONE, COMMESSE).set_index("persona")
    assert r11.loc["Mario", "stato"] == "nei limiti" and r11.loc["Mario", "residuo"] == 10
    assert r11.loc["Admin", "stato"] == "commessa non aperta"


def test_archivio_locale(tmp_path):
    a = ArchivioLocale(tmp_path)
    assert a.leggi("registrazioni").empty
    a.modifica("registrazioni", lambda df: pd.concat([df, pd.DataFrame([{"id": "x", "ore": "2"}])]), "t")
    df = a.leggi("registrazioni")
    assert list(df["id"]) == ["x"] and df.loc[0, "persona"] == ""
