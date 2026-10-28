# -*- coding: utf-8 -*-
"""Zapisi — dokazni trag o tome ko je, kad i šta uradio.

Svaka radnja se dopisuje u fajl kao jedan red. Red se nikad ne mijenja ni ne
briše — ispravka se zapisuje kao nova stavka koja čuva i staru vrijednost. Zbog
toga izvještaj može izdržati osporavanje: vidi se da je procjena promijenjena,
ko ju je promijenio i šta je pisalo prije.
"""
import datetime
import json
import os
import socket

IME = "zapisi.jsonl"

OPIS = {
    "pocetak": "Pokrenut pregled",
    "provjera": "Izvršena provjera",
    "greska": "Provjera nije uspjela",
    "kraj": "Pregled završen",
    "izmjena": "Ispravka nalaza",
    "komentar": "Dodata napomena tehničara",
    "rucni_uredjaj": "Ručno unesen uređaj",
    "dokaz": "Priložen dokaz",
    "izvjestaj": "Napravljen izvještaj",
    "spajanje": "Spojeni pregledi",
}


def _sad():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ")


def upisi(folder, vrsta, tehnicar, sazetak=None, lokacija=""):
    """Dopiši jednu stavku. Nikad ne obara pregled ako upis ne uspije."""
    stavka = {
        "vrijeme_utc": _sad(),
        "vrsta": vrsta,
        "opis": OPIS.get(vrsta, vrsta),
        "tehnicar": (tehnicar or "").strip() or "nepoznat",
        "masina": socket.gethostname(),
        "lokacija": lokacija or "",
        "sazetak": sazetak or {},
    }
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, IME), "a", encoding="utf-8") as f:
            f.write(json.dumps(stavka, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    return stavka


def procitaj(folder, najvise=400):
    out = []
    p = os.path.join(folder, IME)
    try:
        with open(p, encoding="utf-8") as f:
            for red in f:
                red = red.strip()
                if red:
                    try:
                        out.append(json.loads(red))
                    except Exception:
                        continue
    except Exception:
        return []
    return out[-najvise:]


def sazmi(stavka):
    """Jedan red za prikaz u sučelju i u izvještaju."""
    s = stavka.get("sazetak") or {}
    v = stavka.get("vrsta")
    if v == "izmjena":
        d = []
        for polje, naziv in (("sati", "sati"), ("trosak", "trošak"),
                             ("tezina", "težina")):
            if polje in s:
                d.append(f'{naziv}: {s[polje].get("prije")} → {s[polje].get("poslije")}')
        return f'{s.get("nalaz", "nalaz")} — ' + ("; ".join(d) or "izmijenjen")
    if v == "komentar":
        return f'{s.get("nalaz", "nalaz")} — "{str(s.get("tekst", ""))[:90]}"'
    if v == "provjera":
        d = f'{s.get("naziv", "")} — {s.get("nalaza", 0)} nalaza'
        if s.get("sekundi") is not None:
            d += f', {s["sekundi"]} s'
        return d
    if v == "greska":
        return f'{s.get("naziv", "")} — {s.get("poruka", "")}'
    if v == "rucni_uredjaj":
        return f'{s.get("naziv", "")} ({s.get("vrsta_uredjaja", "")})'
    if v == "dokaz":
        return str(s.get("fajl", ""))
    if v == "pocetak":
        return f'{s.get("firma", "")} — {s.get("obim", "")}'
    if v == "izvjestaj":
        return str(s.get("fajl", ""))
    if v == "kraj":
        d = f'{s.get("nalaza", 0)} nalaza'
        if s.get("sekundi"):
            d += f', ukupno {s["sekundi"]} s'
        if s.get("najduze"):
            d += f', najduže: {s["najduze"]}'
        if s.get("greska"):
            d += f', {s["greska"]} provjera nije uspjela'
        return d
    if v == "spajanje":
        return f'{s.get("pregleda", "")} pregleda, {s.get("masina", "")} mašina'
    return json.dumps(s, ensure_ascii=False)[:120] if s else ""
