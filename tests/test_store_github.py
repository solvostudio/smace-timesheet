import base64

import pandas as pd

from ts.store import ArchivioGitHub


class Risposta:
    def __init__(self, codice, corpo=None):
        self.status_code, self._corpo = codice, corpo or {}

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class GitHubFinto:
    """Contents API minimale: un file per path, sha = numero di versione."""

    def __init__(self, conflitti=0):
        self.file, self.conflitti, self.headers = {}, conflitti, {}

    def get(self, url, params=None, timeout=None):
        if url not in self.file:
            return Risposta(404)
        testo, ver = self.file[url]
        return Risposta(200, {"content": base64.b64encode(testo.encode()).decode(), "sha": str(ver)})

    def put(self, url, json=None, timeout=None):
        ver = self.file.get(url, ("", 0))[1]
        if self.conflitti:  # qualcun altro scrive nel frattempo
            self.conflitti -= 1
            testo = self.file.get(url, ("id,commessa,persona,mese,data,attivita,ore,note,inserita_il\n", 0))[0]
            self.file[url] = (testo + "altro,,Admin,2026-10,,x,1,,\n", ver + 1)
            return Risposta(409)
        if json.get("sha", "0") != str(ver):
            return Risposta(409)
        self.file[url] = (base64.b64decode(json["content"]).decode(), ver + 1)
        return Risposta(201)


def archivio(finto):
    a = ArchivioGitHub("org/repo", "token", "dati")
    a.s = finto
    return a


def aggiungi(riga):
    return lambda df: pd.concat([df, pd.DataFrame([riga])], ignore_index=True)


def test_scrittura_e_lettura():
    a = archivio(GitHubFinto())
    assert a.leggi("registrazioni").empty
    a.modifica("registrazioni", aggiungi({"id": "a", "ore": "2"}), "t")
    a.modifica("registrazioni", aggiungi({"id": "b", "ore": "3"}), "t")
    assert list(a.leggi("registrazioni")["id"]) == ["a", "b"]


def test_scrittura_concorrente_non_perde_righe():
    finto = GitHubFinto()
    a = archivio(finto)
    a.modifica("registrazioni", aggiungi({"id": "a", "ore": "2"}), "t")
    finto.conflitti = 1
    a.modifica("registrazioni", aggiungi({"id": "b", "ore": "3"}), "t")
    assert list(a.leggi("registrazioni")["id"]) == ["a", "altro", "b"]
