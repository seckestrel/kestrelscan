# -*- coding: utf-8 -*-
"""Spajanje više pregleda u jedan zbirni izvještaj.

Lokalne provjere — BitLocker, makroi, lozinke u pregledaču — vide samo mašinu
na kojoj je alat pokrenut. Kod firme sa petnaest računara to je jedna
petnaestina slike. Ovdje se pojedinačni pregledi spajaju u jedan izvještaj.
"""
import glob
import json
import os

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO, sortiraj
from .poredjenje import _kljuc

# provjere koje se tiču cijele firme, ne pojedinačne mašine
ZAJEDNICKE = {"Mail i domena", "Sajt firme", "Mreža"}


def popis(folder_rezultata):
    """Spisak ranijih pregleda, najnoviji prvi."""
    out = []
    for p in sorted(glob.glob(os.path.join(folder_rezultata, "*", "nalazi.json")),
                    key=os.path.getmtime, reverse=True):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            pod = d.get("podaci", {})
            nal = d.get("nalazi", [])
            out.append({
                "folder": os.path.basename(os.path.dirname(p)),
                "firma": pod.get("firma") or "",
                "datum": pod.get("datum") or "",
                "masina": pod.get("masina") or "",
                "obim": pod.get("obim") or "",
                "nalaza": len([n for n in nal
                               if n["tezina"] in (VISOK, SREDNJI, NIZAK)]),
            })
        except Exception:
            continue
    return out


def spoji(folder_rezultata, folderi):
    """Spoji izabrane preglede. Vraća (podaci, nalazi, spisak_masina)."""
    ucitani = []
    for ime in folderi:
        p = os.path.join(folder_rezultata, ime, "nalazi.json")
        try:
            with open(p, encoding="utf-8") as f:
                ucitani.append(json.load(f))
        except Exception:
            continue

    if not ucitani:
        return None, [], []

    masine = []
    grupe = {}
    for d in ucitani:
        pod = d.get("podaci", {})
        masina = pod.get("masina") or pod.get("firma") or "mašina"
        masine.append({"masina": masina, "datum": pod.get("datum") or "",
                       "obim": pod.get("obim") or ""})
        for n in d.get("nalazi", []):
            k = _kljuc(n)
            g = grupe.setdefault(k, {"nalaz": dict(n), "masine": [], "dokaz": []})
            g["masine"].append(masina)
            for red in (n.get("dokaz") or [])[:6]:
                g["dokaz"].append(f"[{masina}] {red}")

    ukupno = len(masine)
    spojeni = []
    for g in grupe.values():
        n = dict(g["nalaz"])
        pogodjene = sorted(set(g["masine"]))
        zajednicka = n.get("oblast") in ZAJEDNICKE

        if not zajednicka and ukupno > 1:
            n["utvrdjeno"] = (f'Pogođeno {len(pogodjene)} od {ukupno} mašina: '
                              f'{", ".join(pogodjene)}. ' + (n.get("utvrdjeno") or ""))
            # trošak i vrijeme rastu sa brojem mašina
            if n.get("sati"):
                n["sati"] = round(n["sati"] * len(pogodjene), 1)
            if n.get("trosak"):
                n["trosak"] = int(n["trosak"] * len(pogodjene))
        n["dokaz"] = g["dokaz"][:20]
        n["masine"] = pogodjene
        spojeni.append(n)

    podaci = {
        "firma": ucitani[0].get("podaci", {}).get("firma") or "",
        "datum": max((d.get("podaci", {}).get("datum") or "") for d in ucitani),
        "izvrsio": ucitani[0].get("podaci", {}).get("izvrsio") or "",
        "kontakt": ucitani[0].get("podaci", {}).get("kontakt") or "",
        "kontakt_osoba": ucitani[0].get("podaci", {}).get("kontakt_osoba") or "",
        "obim": f"zbirni pregled {ukupno} mašina",
        "zbirni": True,
    }

    # tabela mašina na početak izvještaja
    tabela_masina = nalaz(
        "Uređaji", f"Zbirni pregled {ukupno} mašina", INFO,
        "Izvještaj objedinjuje pojedinačne preglede sa svih navedenih mašina. "
        "Nalaz koji se javlja na više njih prikazan je jednom, sa spiskom "
        "pogođenih.",
        tabela={"zaglavlje": ["Mašina", "Datum", "Obim pregleda"],
                "redovi": [[m["masina"], m["datum"], m["obim"][:60]]
                           for m in masine],
                "sirine": [22, 16, 62]})
    spojeni.insert(0, tabela_masina)

    return podaci, sortiraj(spojeni), masine
