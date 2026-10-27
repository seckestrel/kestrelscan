# -*- coding: utf-8 -*-
"""Poređenje sa prošlim pregledom iste firme.

Ovo je ono što jednokratni audit pretvara u mjesečni izvještaj: ne pokazuje
samo stanje, nego i šta je urađeno od prošlog puta.
"""
import glob
import json
import os
import re

from .nalaz import VISOK, SREDNJI, NIZAK, INFO, DOBRO

PROPUSTI = (VISOK, SREDNJI, NIZAK)


def _kljuc(n):
    """Stabilna oznaka nalaza — naslovi sa brojevima se normalizuju."""
    naslov = re.sub(r"\d+", "#", (n.get("naslov") or "").lower()).strip()
    return f'{(n.get("oblast") or "").lower()}|{naslov}'


def nadji_prethodni(folder_rezultata, firma, trenutni_folder):
    """Najnoviji raniji pregled iste firme."""
    if not firma:
        return None
    kandidati = []
    for p in glob.glob(os.path.join(folder_rezultata, "*", "nalazi.json")):
        if os.path.dirname(p) == os.path.abspath(trenutni_folder):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if (d.get("podaci", {}).get("firma") or "").strip().lower() \
                    == firma.strip().lower():
                kandidati.append((os.path.getmtime(p), p, d))
        except Exception:
            continue
    if not kandidati:
        return None
    kandidati.sort(reverse=True)
    _, putanja, podaci = kandidati[0]
    return {"putanja": putanja, "podaci": podaci}


def uporedi(trenutni_nalazi, prethodni):
    """Vrati rječnik sa riješenim, novim i nepromijenjenim nalazima."""
    if not prethodni:
        return None

    stari = prethodni["podaci"].get("nalazi") or []
    stari_propusti = {_kljuc(n): n for n in stari if n["tezina"] in PROPUSTI}
    novi_propusti = {_kljuc(n): n for n in trenutni_nalazi
                     if n["tezina"] in PROPUSTI}

    rijeseno = [n for k, n in stari_propusti.items() if k not in novi_propusti]
    novo = [n for k, n in novi_propusti.items() if k not in stari_propusti]
    ostalo = [n for k, n in novi_propusti.items() if k in stari_propusti]

    def _ocjena(nalazi):
        from .nalaz import ocjena
        return ocjena(nalazi)

    return {
        "datum_prethodnog": prethodni["podaci"].get("podaci", {}).get("datum"),
        "ocjena_prethodna": _ocjena(stari),
        "rijeseno": sorted(rijeseno, key=lambda n: n["tezina"]),
        "novo": sorted(novo, key=lambda n: n["tezina"]),
        "ostalo": sorted(ostalo, key=lambda n: n["tezina"]),
        "broj": {"rijeseno": len(rijeseno), "novo": len(novo),
                 "ostalo": len(ostalo)},
    }
