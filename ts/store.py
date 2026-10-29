"""Archivio delle tabelle CSV: file locali in sviluppo, repo GitHub privato in produzione.

Streamlit Cloud azzera il disco a ogni riavvio, quindi online i dati vivono in un
repo GitHub (stesso meccanismo del tasto "Salva" del FP). Ogni scrittura rilegge
il file, applica la modifica e salva con lo sha letto: se nel frattempo qualcun
altro ha scritto, GitHub rifiuta e si riprova sulla versione nuova.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

TABELLE = {
    "persone": ["nome", "ruolo", "attiva"],
    "commesse": ["id", "persona", "mese", "plafond", "aperta_il", "aperta_da"],
    "registrazioni": ["id", "commessa", "persona", "mese", "data", "attivita", "ore", "note", "inserita_il"],
}


def _da_csv(testo: str, nome: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(testo), dtype=str, keep_default_na=False) if testo.strip() else pd.DataFrame()
    for col in TABELLE[nome]:
        if col not in df.columns:
            df[col] = ""
    return df[TABELLE[nome]]


def _a_csv(df: pd.DataFrame, nome: str) -> str:
    return df.reindex(columns=TABELLE[nome]).fillna("").astype(str).to_csv(index=False)


class ArchivioLocale:
    def __init__(self, cartella: Path):
        self.cartella = Path(cartella)

    def leggi(self, nome: str) -> pd.DataFrame:
        f = self.cartella / f"{nome}.csv"
        return _da_csv(f.read_text(encoding="utf-8") if f.exists() else "", nome)

    def modifica(self, nome: str, fn: Callable[[pd.DataFrame], pd.DataFrame], messaggio: str) -> None:
        df = fn(self.leggi(nome))
        (self.cartella / f"{nome}.csv").write_text(_a_csv(df, nome), encoding="utf-8")


class ArchivioGitHub:
    API = "https://api.github.com"

    def __init__(self, repo: str, token: str, ramo: str = "main", cartella: str = "data"):
        self.repo, self.ramo, self.cartella = repo, ramo, cartella.strip("/")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})

    def _url(self, nome: str) -> str:
        return f"{self.API}/repos/{self.repo}/contents/{self.cartella}/{nome}.csv"

    def _scarica(self, nome: str) -> tuple[str, str | None]:
        r = self.s.get(self._url(nome), params={"ref": self.ramo}, timeout=15)
        if r.status_code == 404:
            return "", None
        r.raise_for_status()
        j = r.json()
        return base64.b64decode(j["content"]).decode("utf-8"), j["sha"]

    def leggi(self, nome: str) -> pd.DataFrame:
        return _da_csv(self._scarica(nome)[0], nome)

    def modifica(self, nome: str, fn: Callable[[pd.DataFrame], pd.DataFrame], messaggio: str) -> None:
        for _ in range(4):
            testo, sha = self._scarica(nome)
            nuovo = _a_csv(fn(_da_csv(testo, nome)), nome)
            corpo = {"message": messaggio, "branch": self.ramo,
                     "content": base64.b64encode(nuovo.encode("utf-8")).decode("ascii")}
            if sha:
                corpo["sha"] = sha
            r = self.s.put(self._url(nome), json=corpo, timeout=15)
            if r.status_code in (409, 422):  # scrittura concorrente: si riprova sulla versione nuova
                continue
            r.raise_for_status()
            return
        raise RuntimeError(f"Salvataggio di {nome} non riuscito dopo più tentativi")
