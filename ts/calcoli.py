"""Calcoli del timesheet: commesse mensili, ore registrate, plafond e sforamenti.

Una commessa = una persona in un mese (es. "Mario · ottobre 2026"), aperta a inizio
mese con il plafond che dà il suo contratto. Le ore si registrano dentro la commessa.
"""
from __future__ import annotations

import pandas as pd


def num(v) -> float | None:
    """Converte un valore CSV in numero; vuoto o non numerico = None."""
    try:
        s = str(v).strip().replace(",", ".")
        return float(s) if s else None
    except ValueError:
        return None


def ore_numeriche(reg: pd.DataFrame) -> pd.DataFrame:
    out = reg.copy()
    out["ore"] = out["ore"].map(num).astype(float).fillna(0.0)
    return out


def commessa_di(persona: str, mese: str, commesse: pd.DataFrame) -> pd.Series | None:
    c = commesse[(commesse["persona"] == persona) & (commesse["mese"] == mese)]
    return c.iloc[0] if len(c) else None


def stato(ore: float, plafond: float | None) -> str:
    if plafond is None:
        return "plafond da definire"
    if ore > plafond:
        return "oltre plafond"
    if plafond and ore >= 0.9 * plafond:
        return "vicino al plafond"
    return "nei limiti"


def riepilogo_mese(mese: str, reg: pd.DataFrame, persone: pd.DataFrame, commesse: pd.DataFrame) -> pd.DataFrame:
    """Una riga per persona attiva o con commessa nel mese: ore, plafond, residuo, stato."""
    ore = ore_numeriche(reg[reg["mese"] == mese]).groupby("persona")["ore"].sum()
    del_mese = commesse[commesse["mese"] == mese]
    nomi = list(persone.loc[persone["attiva"] != "no", "nome"]) + list(del_mese["persona"]) + list(ore.index)
    righe = []
    for p in dict.fromkeys(nomi):
        o = float(ore.get(p, 0.0))
        c = commessa_di(p, mese, del_mese)
        pl = num(c["plafond"]) if c is not None else None
        righe.append({
            "persona": p,
            "ore": o,
            "plafond": pl,
            "residuo": None if pl is None else pl - o,
            "stato": "commessa non aperta" if c is None else stato(o, pl),
        })
    return pd.DataFrame(righe, columns=["persona", "ore", "plafond", "residuo", "stato"])
