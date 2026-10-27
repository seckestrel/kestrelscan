# -*- coding: utf-8 -*-
"""Sajt: koji CMS, koja verzija, i šta je izloženo a ne bi trebalo."""
import re

import requests
from requests.exceptions import RequestException

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

AGENT = {"User-Agent": "KestrelScan/1.0 (sigurnosni pregled uz saglasnost)"}

# putanja, naziv, težina, zašto je problem
IZLOZENO = [
    ("/.env", "Konfiguracioni fajl .env", VISOK,
     "U njemu su po pravilu lozinka baze i ključevi servisa, u čitljivom obliku."),
    ("/.git/config", "Git repozitorij", VISOK,
     "Kroz njega se može preuzeti kompletan izvorni kod sajta, zajedno sa lozinkama."),
    ("/wp-config.php.bak", "Rezervna kopija konfiguracije", VISOK,
     "Sadrži pristupne podatke za bazu, a server je šalje kao običan tekst."),
    ("/phpinfo.php", "phpinfo stranica", SREDNJI,
     "Otkriva verzije, putanje i postavke servera — gotova mapa za napadača."),
    ("/server-status", "Apache server-status", SREDNJI,
     "Prikazuje aktivne zahtjeve i adrese posjetilaca."),
    ("/wp-admin/install.php", "WordPress instalacija", VISOK,
     "Ako je dostupna, sajt se može preuzeti u potpunosti."),
    ("/xmlrpc.php", "WordPress xmlrpc", NIZAK,
     "Koristi se za masovno pogađanje lozinki i pojačavanje napada."),
    ("/readme.html", "WordPress readme", NIZAK,
     "Otkriva tačnu verziju, pa napadač zna koji propust da proba."),
    ("/backup.zip", "Arhiva sajta", VISOK,
     "Cijeli sajt i baza dostupni za preuzimanje bez ikakve prijave."),
    ("/.DS_Store", "Fajl .DS_Store", NIZAK,
     "Otkriva spisak fajlova i foldera na serveru."),
]

CMS_TRAGOVI = [
    ("WordPress", [r"/wp-content/", r"/wp-includes/", r'name="generator" content="WordPress ([\d.]+)']),
    ("Joomla", [r"/media/jui/", r'name="generator" content="Joomla']),
    ("Drupal", [r"/sites/all/", r"Drupal.settings"]),
    ("PrestaShop", [r"/modules/ps_", r"prestashop"]),
    ("Shopify", [r"cdn\.shopify\.com"]),
    ("Wix", [r"static\.wixstatic\.com"]),
    ("Squarespace", [r"squarespace\.com"]),
]


def provjeri(domena, log=lambda s: None):
    host = (domena or "").strip().lower()
    for p in ("https://", "http://"):
        if host.startswith(p):
            host = host[len(p):]
    host = host.split("/")[0]
    if not host:
        return {"nalazi": [], "sirovo": {}}

    baza = f"https://{host}"
    nalazi, sirovo = [], {"host": host}

    log(f"Učitavam {baza}")
    try:
        r = requests.get(baza, timeout=12, headers=AGENT, allow_redirects=True)
        html = r.text[:400000]
    except RequestException as e:
        return {"nalazi": [nalaz("Sajt firme", "Sajt nije dostupan", INFO,
                                 f"Učitavanje nije uspjelo: {e}")],
                "sirovo": sirovo}

    # --- koji CMS ---
    pronadjen, verzija = None, None
    for ime, obrasci in CMS_TRAGOVI:
        for o in obrasci:
            m = re.search(o, html, re.I)
            if m:
                pronadjen = ime
                if m.groups():
                    verzija = m.group(1)
                break
        if pronadjen:
            break
    sirovo["cms"] = pronadjen
    sirovo["verzija"] = verzija

    if pronadjen:
        if verzija:
            nalazi.append(nalaz(
                "Sajt firme", f"Sajt otkriva verziju sistema ({pronadjen} {verzija})",
                SREDNJI,
                f"U izvoru stranice stoji da je {pronadjen} verzija {verzija}.",
                "Napadač ne mora ništa tražiti — zna tačnu verziju i odmah proba "
                "propuste koji za nju postoje. Automatizovani alati to rade masovno.",
                "Ukloniti oznaku verzije iz zaglavlja i izvora stranice, i "
                "provjeriti je li sistem na posljednjoj verziji.",
                sati=1, trosak=60, dokaz=[f"{pronadjen} {verzija}"]))
        else:
            nalazi.append(nalaz(
                "Sajt firme", f"Sajt koristi {pronadjen}", INFO,
                f"Prepoznat je {pronadjen}.",
                preporuka="Provjeriti da su jezgro, teme i dodaci na posljednjoj "
                          "verziji, i ukloniti ono što se ne koristi."))

    # --- izloženi fajlovi ---
    log("Tražim izložene fajlove")
    nadjeno = []
    for put, naziv, tez, zasto in IZLOZENO:
        # WordPress putanje se provjeravaju samo ako je WordPress
        if put.startswith(("/wp-", "/xmlrpc", "/readme")) and pronadjen != "WordPress":
            continue
        try:
            rr = requests.get(baza + put, timeout=8, headers=AGENT,
                              allow_redirects=False)
            if rr.status_code == 200 and len(rr.content) > 20:
                tijelo = rr.text[:3000].lower()
                # stranica greške koja vraća 200 nije nalaz
                if any(z in tijelo for z in ("404", "not found", "nije pronađen",
                                             "page not found")):
                    continue
                nadjeno.append((put, naziv, tez, zasto, rr.status_code,
                                len(rr.content)))
                log(f"  {put} → {rr.status_code}")
        except RequestException:
            continue

    sirovo["izlozeno"] = [{"putanja": p, "naziv": n} for p, n, *_ in nadjeno]

    for put, naziv, tez, zasto, kod, vel in nadjeno:
        nalazi.append(nalaz(
            "Sajt firme", f"Javno dostupno: {naziv}", tez,
            f"{baza}{put} vraća odgovor {kod} ({vel} bajta).",
            zasto,
            "Ukloniti fajl sa servera ili zabraniti pristup u konfiguraciji "
            "web servera.",
            sati=0.5, trosak=30, dokaz=[f"GET {baza}{put} → {kod}"]))

    if pronadjen and not nadjeno:
        nalazi.append(nalaz(
            "Sajt firme", "Nema uobičajenih izloženih fajlova", DOBRO,
            "Provjerene su standardne putanje i nijedna nije dostupna.",
            dokaz=[p for p, *_ in IZLOZENO]))

    return {"nalazi": nalazi, "sirovo": sirovo}
