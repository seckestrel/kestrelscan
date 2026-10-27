# -*- coding: utf-8 -*-
"""Uvoz pregleda sa druge mašine.

Zbirni izvještaj se pravi od pregleda koji stoje u istom folderu `rezultati`.
Kad alat nije pokretan sa istog USB-a nego je kopiran na svaku mašinu, svaki
računar ima svoj folder i zbirni se nema od čega napraviti.

Ovdje se pregled sa druge mašine prenosi ovamo — iz fajla koji tehničar izabere
u pregledaču, ili sa putanje (drugi disk, stick, mrežni folder).
"""
import json
import os
import re
import shutil
import zipfile


def _bezbjedno(s, podrazumijevano="pregled"):
    s = re.sub(r"[^\w\s-]", "", s or "", flags=re.U).strip()
    return re.sub(r"\s+", "_", s)[:48] or podrazumijevano


def _provjeri(putanja):
    """Je li ovo stvarno nalazi.json iz ovog alata."""
    with open(putanja, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict) or "nalazi" not in d:
        raise ValueError("Fajl nije nalazi.json iz KestrelScan pregleda.")
    return d


def _ime_foldera(d, rezervno="uvezen_pregled"):
    pod = d.get("podaci") or {}
    dijelovi = [_bezbjedno(pod.get("firma"), "")]
    if pod.get("masina"):
        dijelovi.append(_bezbjedno(pod["masina"], ""))
    datum = (pod.get("datum") or "").replace(".", "").strip()
    if datum:
        dijelovi.append(_bezbjedno(datum, ""))
    ime = "_".join(x for x in dijelovi if x)
    return ime or rezervno


def _slobodno(rezultati, ime):
    cilj = os.path.join(rezultati, ime)
    n = 2
    while os.path.exists(cilj):
        cilj = os.path.join(rezultati, f"{ime}_{n}")
        n += 1
    return cilj


def _vec_postoji(rezultati, d):
    """Isti pregled uvezen dvaput je dvaput ista mašina u zbirnom izvještaju."""
    pod = d.get("podaci") or {}
    potpis = (pod.get("firma"), pod.get("masina"), pod.get("datum"),
              len(d.get("nalazi") or []))
    if not any(potpis[:3]):
        return None
    for ime in os.listdir(rezultati):
        p = os.path.join(rezultati, ime, "nalazi.json")
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            continue
        sp = s.get("podaci") or {}
        if (sp.get("firma"), sp.get("masina"), sp.get("datum"),
                len(s.get("nalazi") or [])) == potpis:
            return ime
    return None


def iz_json(rezultati, izvor_json, prateci=None):
    """Uvezi jedan nalazi.json. `prateci` su fajlovi koji idu uz njega (PDF…)."""
    d = _provjeri(izvor_json)
    stari = _vec_postoji(rezultati, d)
    if stari:
        return {"ok": False, "razlog": "duplikat", "folder": stari}

    cilj = _slobodno(rezultati, _ime_foldera(d))
    os.makedirs(cilj, exist_ok=True)
    shutil.copy2(izvor_json, os.path.join(cilj, "nalazi.json"))
    for f in prateci or []:
        try:
            shutil.copy2(f, os.path.join(cilj, os.path.basename(f)))
        except Exception:
            pass
    pod = d.get("podaci") or {}
    return {"ok": True, "folder": os.path.basename(cilj),
            "firma": pod.get("firma") or "", "masina": pod.get("masina") or "",
            "datum": pod.get("datum") or "",
            "nalaza": len(d.get("nalazi") or [])}


def iz_zipa(rezultati, putanja_zip, radni):
    """Uvezi pregled iz zip arhive — svaki nalazi.json u njoj je jedan pregled."""
    raspakovano = os.path.join(radni, "_uvoz_zip")
    shutil.rmtree(raspakovano, ignore_errors=True)
    os.makedirs(raspakovano, exist_ok=True)
    try:
        with zipfile.ZipFile(putanja_zip) as z:
            for clan in z.infolist():
                # arhiva iz nepoznatog izvora ne smije pisati van svog foldera
                ime = clan.filename.replace("\\", "/")
                if ime.startswith("/") or ".." in ime.split("/"):
                    continue
                z.extract(clan, raspakovano)
        return iz_putanje(rezultati, raspakovano, radni)
    finally:
        shutil.rmtree(raspakovano, ignore_errors=True)


def iz_putanje(rezultati, putanja, radni=None):
    """Uvezi sa putanje: fajl nalazi.json, folder pregleda, ili folder
    `rezultati` sa više pregleda u sebi."""
    putanja = os.path.expandvars(os.path.expanduser((putanja or "").strip().strip('"')))
    if not putanja or not os.path.exists(putanja):
        return {"ok": False, "greska": "Putanja ne postoji. Provjeri da li je "
                                       "folder dostupan sa ove mašine."}

    if os.path.isfile(putanja):
        if putanja.lower().endswith(".zip"):
            return iz_zipa(rezultati, putanja, radni or os.path.dirname(rezultati))
        if os.path.basename(putanja).lower() != "nalazi.json":
            return {"ok": False, "greska": "Izaberi nalazi.json ili zip pregleda."}
        nadjeni = [putanja]
    else:
        nadjeni = []
        direktno = os.path.join(putanja, "nalazi.json")
        if os.path.isfile(direktno):
            nadjeni = [direktno]
        else:
            for ime in sorted(os.listdir(putanja)):
                p = os.path.join(putanja, ime, "nalazi.json")
                if os.path.isfile(p):
                    nadjeni.append(p)

    if not nadjeni:
        return {"ok": False, "greska": "Na toj putanji nema nijednog pregleda "
                                       "(nije pronađen nalazi.json)."}

    uvezeni, preskoceni, greske = [], [], []
    for p in nadjeni:
        folder = os.path.dirname(p)
        prateci = [os.path.join(folder, f) for f in os.listdir(folder)
                   if f.lower().endswith((".pdf", ".html", ".jsonl"))]
        try:
            r = iz_json(rezultati, p, prateci)
        except Exception as e:
            greske.append(f"{os.path.basename(folder)}: {type(e).__name__}: {e}")
            continue
        (uvezeni if r.get("ok") else preskoceni).append(r)

    return {"ok": bool(uvezeni), "uvezeno": uvezeni, "duplikata": len(preskoceni),
            "greske": greske,
            "greska": None if uvezeni else
                      ("Taj pregled je već uvezen." if preskoceni
                       else "; ".join(greske) or "Ništa nije uvezeno.")}
