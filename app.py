# -*- coding: utf-8 -*-
"""KestrelScan — alat za sigurnosni pregled malih firmi.

Pokreće se dvoklikom, otvara se u pregledaču na 127.0.0.1.
Radi sa USB-a, bez instalacije.
"""
import datetime
import json
import socket
import os
import shutil
import re
import sys
import threading
import time
import webbrowser

from flask import Flask, jsonify, request, send_from_directory, render_template

import izvjestaj
from skener import cms as m_cms
from skener import dijeljeno as m_dijeljeno
from skener import azuriranje as m_azuriranje
from skener import backup as m_backup
from skener import domena as m_domena
from skener import poredjenje as m_poredjenje
from skener import rucni_unos as m_rucni_unos
from skener import stampaci as m_stampaci
from skener import zapisi as m_zapisi
from skener import spajanje as m_spajanje
from skener import uvoz as m_uvoz
from skener import win11 as m_win11
from skener import inventar as m_inventar
from skener import licenca as m_licenca
from skener import politika as m_politika
from skener import softver as m_softver
from skener import wifi as m_wifi
from skener import hardver as m_hardver
from skener import mreza as m_mreza
from skener import nalozi as m_nalozi
from skener import pasivno as m_pasivno
from skener import pingcastle as m_pingcastle
from skener import rucno as m_rucno
from skener import sajt as m_sajt
from skener import windows as m_windows
from skener.nalaz import (nalaz, ocjena, sortiraj,
                          VISOK, SREDNJI, NIZAK, INFO, DOBRO)

PORT = 8777
VERZIJA = "1.7.2"


def korijen():
    """Folder pored programa — tu idu rezultati, postavke i tools/."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resurs(ime):
    """Folder sa ugrađenim fajlovima (šabloni, statika, fontovi).

    U .exe verziji PyInstaller ih raspakuje u privremeni folder, pa se ne
    traže pored programa.
    """
    baza = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(baza, ime)


KORIJEN = korijen()
RESURSI = getattr(sys, "_MEIPASS", None) or KORIJEN
REZULTATI = os.path.join(KORIJEN, "rezultati")
POSTAVKE = os.path.join(KORIJEN, "postavke.json")
os.makedirs(REZULTATI, exist_ok=True)

app = Flask(__name__, template_folder=resurs("sabloni"),
            static_folder=resurs("statika"), static_url_path="/statika")

# jedan posao u jednom trenutku — alat radi na terenu, ne na serveru
POSAO = {"radi": False, "dnevnik": [], "nalazi": [], "sirovo": {},
         "gotovo": False, "folder": None, "pdf": None, "sazetak": None,
         "greske": [], "treba_izvjestaj": False, "trajanje": {},
         "prekid": False, "prekinut": False,
         "korak": "", "napredak": 0, "podaci": {}}
BRAVA = threading.Lock()


# Ključevi ugrađeni u alat — rade i na praznoj kopiji, bez podešavanja.
# postavke.json pored alata ima prednost, pa se mogu promijeniti kroz Postavke
# bez diranja koda.
UGRADJENO = {
    # Ključevi NAMJERNO nisu ovdje. Paket ide na GitHub i svako ga može
    # preuzeti — ključ u kodu bi otišao s njim. Shodan i HIBP ključ stoje u
    # postavke.json pored alata, a taj fajl nije u paketu i ne dira se pri
    # ažuriranju.
    # Ažuriranje čeka mjesto za objavu (vlastiti hosting). Dok ga nema,
    # paket stiže ručno, a provjera se ne pokreće sama — da alat ne kuca na
    # adresu koje nema.
    "azuriranje_url": "",
    "azuriranje_automatski": False,
}


def ucitaj_postavke():
    p = dict(UGRADJENO)
    try:
        with open(POSTAVKE, encoding="utf-8") as f:
            snimljeno = json.load(f)
        p.update({k: v for k, v in snimljeno.items()
                  if v is not None and v != ""})
    except Exception:
        pass
    return p


def snimi_postavke(p):
    with open(POSTAVKE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def je_administrator():
    """Bez administratorskih prava BitLocker, sigurnosni dnevnik i dio SMB
    postavki vrate prazno — a pregled izgleda uredno. Zato se pita unaprijed."""
    if not sys.platform.startswith("win"):
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return True


def trajanje(sekundi):
    """Vrijeme u obliku koji se čita bez računanja."""
    s = int(round(sekundi))
    if s < 60:
        return f"{s} s"
    return f"{s // 60} min {s % 60} s" if s % 60 else f"{s // 60} min"


def log(poruka):
    vrijeme = datetime.datetime.now().strftime("%H:%M:%S")
    POSAO["dnevnik"].append(f"{vrijeme}  {poruka}")
    if len(POSAO["dnevnik"]) > 400:
        del POSAO["dnevnik"][:100]


def bezbjedno_ime(s):
    s = re.sub(r"[^\w\s-]", "", s or "klijent", flags=re.U).strip()
    return re.sub(r"[\s]+", "_", s)[:48] or "klijent"


def ime_foldera(firma, masina=None, predmetak=""):
    """Firma, datum, vrijeme i mašina — da se u folderu `rezultati` na prvi
    pogled zna čiji je pregled, kada je rađen i sa koje mašine."""
    sad = datetime.datetime.now()
    dijelovi = [predmetak, bezbjedno_ime(firma),
                sad.strftime("%Y-%m-%d"), sad.strftime("%H-%M"),
                bezbjedno_ime(masina or socket.gethostname(), )]
    ime = "_".join(x for x in dijelovi if x)
    cilj = os.path.join(REZULTATI, ime)
    n = 2
    while os.path.exists(cilj):
        cilj = os.path.join(REZULTATI, f"{ime}_{n}")
        n += 1
    return cilj


def pokreni(podaci):
    POSAO.update({"radi": True, "dnevnik": [], "nalazi": [], "sirovo": {},
                  "gotovo": False, "pdf": None, "sazetak": None,
                  "greske": [], "treba_izvjestaj": False, "trajanje": {},
                  "prekid": False, "prekinut": False,
                  "napredak": 0, "podaci": podaci})

    podaci.setdefault("masina", socket.gethostname())
    podaci["lokacija_puna"] = " | ".join(
        x for x in (podaci.get("regija"), podaci.get("lokacija"),
                    podaci.get("podlokacija")) if (x or "").strip())
    ime = bezbjedno_ime(podaci.get("firma"))
    folder = ime_foldera(podaci.get("firma"), podaci.get("masina"))
    os.makedirs(folder, exist_ok=True)
    POSAO["folder"] = folder
    tehnicar = podaci.get("izvrsio") or ""
    lok = podaci.get("lokacija_puna") or ""
    m_zapisi.upisi(folder, "pocetak", tehnicar, {
        "firma": podaci.get("firma"), "obim": podaci.get("obim"),
        "masina": podaci.get("masina")}, lok)

    izabrani = podaci.get("provjere") or []
    koraka = max(1, len(izabrani))
    uradjeno = 0

    def napreduj(naziv):
        nonlocal uradjeno
        uradjeno += 1
        POSAO["napredak"] = int(uradjeno / koraka * 100)
        POSAO["korak"] = naziv

    def izvrsi(kljuc, naziv, funkcija, uslov=True):
        """Pokreni jednu provjeru. Pad jedne provjere ne smije oboriti pregled —
        inače se ne dođe ni do PDF-a, a to je jedino zbog čega se alat pokreće."""
        if kljuc not in izabrani:
            return
        if POSAO["prekid"]:
            POSAO["prekinut"] = True
            napreduj(naziv)
            return
        if not uslov:
            log(f"── {naziv} — preskočeno, nema potrebnog podatka ──")
            napreduj(naziv)
            return
        POSAO["korak"] = naziv
        log(f"── {naziv} ──")
        pocelo = time.monotonic()
        try:
            r = funkcija()
            novi = r.get("nalazi") or []
            POSAO["nalazi"] += novi
            POSAO["sirovo"][kljuc] = r.get("sirovo") or {}
            trajalo = time.monotonic() - pocelo
            POSAO["trajanje"][naziv] = trajalo
            log(f"   gotovo za {trajanje(trajalo)} — {len(novi)} nalaza")
            m_zapisi.upisi(folder, "provjera", tehnicar,
                           {"naziv": naziv, "nalaza": len(novi),
                            "sekundi": round(trajalo, 1)}, lok)
        except Exception as e:
            poruka = f"{type(e).__name__}: {e}"
            trajalo = time.monotonic() - pocelo
            POSAO["trajanje"][naziv] = trajalo
            log(f"   provjera nije uspjela nakon {trajanje(trajalo)} — {poruka}")
            POSAO["greske"].append(f"{naziv}: {poruka}")
            m_zapisi.upisi(folder, "greska", tehnicar,
                           {"naziv": naziv, "poruka": poruka,
                            "sekundi": round(trajalo, 1)}, lok)
            POSAO["nalazi"].append(nalaz(
                "Napomene", f"Provjera nije uspjela: {naziv}", INFO,
                f"Tokom provjere došlo je do greške: {poruka}",
                preporuka="Ostale provjere su izvršene normalno. Ovu stavku "
                          "provjeriti ručno ili ponoviti pregled.",
                dokaz=[poruka]))
        napreduj(naziv)

    try:
        izvrsi("domena", "Mail domena",
               lambda: m_domena.provjeri(podaci["domena"], log,
                                         podaci.get("dkim_selektor")),
               bool(podaci.get("domena")))

        izvrsi("sajt", "Sertifikat i TLS",
               lambda: m_sajt.provjeri(podaci.get("sajt") or podaci.get("domena"), log),
               bool(podaci.get("sajt") or podaci.get("domena")))

        izvrsi("cms", "CMS i izloženi fajlovi",
               lambda: m_cms.provjeri(podaci.get("sajt") or podaci.get("domena"), log),
               bool(podaci.get("sajt") or podaci.get("domena")))

        izvrsi("pasivno", "Pasivni uvid (Shodan)",
               lambda: m_pasivno.provjeri(
                   podaci.get("javna_ip"), podaci.get("domena") or podaci.get("sajt"),
                   ucitaj_postavke().get("shodan_kljuc"), log),
               bool(podaci.get("javna_ip") or podaci.get("domena")
                    or podaci.get("sajt")))

        izvrsi("izlozenost", "Izloženost sa interneta",
               lambda: m_mreza.izlozenost(podaci.get("javna_ip"), log),
               bool(podaci.get("javna_ip")))

        izvrsi("nalozi", "Procurjeli nalozi",
               lambda: m_nalozi.provjeri(
                   [a for a in re.split(r"[,\s;]+", podaci.get("adrese") or "") if a],
                   ucitaj_postavke().get("hibp_kljuc"), log,
                   ucitaj_postavke().get("hibp_razmak")),
               bool(podaci.get("adrese")))

        def _mreza():
            r = m_mreza.provjeri(podaci["opseg"], log,
                                 preskoci=podaci.get("preskoci"),
                                 stani=lambda: POSAO["prekid"])
            try:
                j = m_mreza.javna_izlozenost(log)
                r["nalazi"] += j["nalazi"]
                r["sirovo"]["javna"] = j["sirovo"]
            except Exception as e:
                log(f"   javna adresa nije utvrđena: {e}")
            return r

        izvrsi("mreza", "Mreža i otvoreni servisi", _mreza, bool(podaci.get("opseg")))

        izvrsi("windows", "Postavke sistema", lambda: m_windows.provjeri(log))

        izvrsi("inventar", "Inventar uređaja",
               lambda: m_inventar.provjeri(
                   (POSAO["sirovo"].get("mreza") or {}).get("uredjaji"),
                   podaci.get("ad_korisnik"), podaci.get("ad_lozinka"), log))

        izvrsi("stampaci", "Popis štampača",
               lambda: m_stampaci.provjeri(
                   (POSAO["sirovo"].get("mreza") or {}).get("uredjaji"), log))

        izvrsi("wifi", "Bežična mreža", lambda: m_wifi.provjeri(log))

        izvrsi("dijeljeno", "Dijeljeni folderi",
               lambda: m_dijeljeno.provjeri(
                   (POSAO["sirovo"].get("mreza") or {}).get("uredjaji"), log))

        izvrsi("softver", "Softver i daljinski pristup",
               lambda: m_softver.provjeri(log))

        izvrsi("politika", "Politika lozinki", lambda: m_politika.provjeri(log))

        izvrsi("licence", "Licence i aktivacija", lambda: m_licenca.provjeri(log))

        izvrsi("hardver", "Popis hardvera", lambda: m_hardver.provjeri(log))

        izvrsi("win11", "Spremnost za Windows 11",
               lambda: m_win11.provjeri(POSAO["sirovo"].get("hardver"), log))

        izvrsi("backup", "Backup softver i zadaci",
               lambda: m_backup.provjeri(
                   (POSAO["sirovo"].get("softver") or {}).get("programi"), log))

        izvrsi("pingcastle", "Active Directory",
               lambda: m_pingcastle.provjeri(KORIJEN, podaci["domen_ad"], folder, log),
               bool(podaci.get("domen_ad")))

        POSAO["nalazi"] = sortiraj(POSAO["nalazi"])

        # lozinka se koristi samo tokom skeniranja i nikad se ne snima na disk
        za_snimanje = {k: v for k, v in podaci.items() if k != "ad_lozinka"}
        try:
            with open(os.path.join(folder, "nalazi.json"), "w", encoding="utf-8") as f:
                json.dump({"podaci": za_snimanje, "nalazi": POSAO["nalazi"],
                           "sirovo": POSAO["sirovo"]}, f, ensure_ascii=False,
                          indent=2, default=str)
        except Exception as e:
            log(f"nalazi.json nije snimljen — {type(e).__name__}: {e}")

        try:
            prethodni = m_poredjenje.nadji_prethodni(REZULTATI, podaci.get("firma"),
                                                     folder)
            if prethodni:
                log("Poredim sa prošlim pregledom")
                podaci["poredjenje"] = m_poredjenje.uporedi(POSAO["nalazi"], prethodni)
                b = podaci["poredjenje"]["broj"]
                log(f'Riješeno {b["rijeseno"]}, novih {b["novo"]}, '
                    f'i dalje otvoreno {b["ostalo"]}')
        except Exception as e:
            log(f"Poređenje sa prošlim pregledom nije uspjelo — {e}")

        log("Pravim PDF izvještaj")
        pdf = os.path.join(folder, f"Sigurnosni_pregled_{ime}.pdf")
        try:
            izvjestaj.napravi(podaci, POSAO["nalazi"], pdf, RESURSI)
            POSAO["pdf"] = os.path.basename(pdf)
            m_zapisi.upisi(folder, "izvjestaj", tehnicar,
                           {"fajl": os.path.basename(pdf)}, lok)
        except Exception as e:
            poruka = f"{type(e).__name__}: {e}"
            log(f"PDF izvještaj nije napravljen — {poruka}")
            POSAO["greske"].append(f"PDF izvještaj: {poruka}")

        log("Pravim jednostrani sažetak")
        saz = os.path.join(folder, f"Sazetak_{ime}.pdf")
        try:
            izvjestaj.sazetak(podaci, POSAO["nalazi"], saz, RESURSI)
            POSAO["sazetak"] = os.path.basename(saz)
        except Exception as e:
            poruka = f"{type(e).__name__}: {e}"
            log(f"Sažetak nije napravljen — {poruka}")
            POSAO["greske"].append(f"Sažetak: {poruka}")

        if POSAO["prekinut"] or POSAO["prekid"]:
            log("── Pregled je prekinut na zahtjev ──")
            log("   Izvještaj se pravi od onoga što je do sada urađeno.")
            m_zapisi.upisi(folder, "prekid", tehnicar,
                           {"nalaza": len(POSAO["nalazi"])}, lok)
            POSAO["nalazi"].append(nalaz(
                "Napomene", "Pregled je prekinut prije kraja", INFO,
                "Pregled je zaustavljen na zahtjev tehničara, pa nisu izvršene "
                "sve izabrane provjere.",
                preporuka="Ponoviti pregled u punom obimu prije nego se "
                          "izvještaj preda klijentu."))

        po_duzini = sorted(POSAO["trajanje"].items(), key=lambda x: -x[1])
        ukupno = sum(POSAO["trajanje"].values())
        if po_duzini:
            log(f"── Utrošeno vrijeme: {trajanje(ukupno)} ──")
            for naziv, sek in po_duzini[:5]:
                udio = f" ({sek / ukupno * 100:.0f}%)" if ukupno else ""
                log(f"   {trajanje(sek):>10}  {naziv}{udio}")
            if len(po_duzini) > 5:
                log(f"   ostale provjere: "
                    f"{trajanje(sum(s for _, s in po_duzini[5:]))}")
        m_zapisi.upisi(folder, "kraj", tehnicar, {
            "nalaza": len(POSAO["nalazi"]),
            "greska": len(POSAO.get("greske") or []),
            "sekundi": round(ukupno, 1),
            "najduze": po_duzini[0][0] if po_duzini else ""}, lok)
        log(f"Gotovo. Rezultati su u: {folder}")
    except Exception as e:
        log(f"GREŠKA: {type(e).__name__}: {e}")
    finally:
        POSAO["napredak"] = 100
        POSAO["radi"] = False
        POSAO["gotovo"] = True
        POSAO["korak"] = "Završeno"


@app.route("/")
def pocetna():
    return render_template("index.html",
                           moja_mreza=m_mreza.moja_mreza(),
                           ima_kljuc=bool(ucitaj_postavke().get("hibp_kljuc")),
                           ima_shodan=bool(ucitaj_postavke().get("shodan_kljuc")),
                           je_windows=m_windows.JE_WINDOWS,
                           je_admin=je_administrator(),
                           ima_pingcastle=bool(m_pingcastle.putanja_exe(KORIJEN)),
                           pitanja=m_rucno.po_oblastima())


@app.route("/api/pokreni", methods=["POST"])
def api_pokreni():
    with BRAVA:
        if POSAO["radi"]:
            return jsonify({"ok": False, "greska": "Skeniranje je već u toku."}), 409
        podaci = request.get_json(force=True)
        podaci["datum"] = datetime.date.today().strftime("%d.%m.%Y.")
        if not (podaci.get("izvrsio") or "").strip():
            podaci["izvrsio"] = ucitaj_postavke().get(
                "izvrsio", "Dragomir Babić, KestrelSec")
        podaci.setdefault("kontakt", ucitaj_postavke().get(
            "kontakt", "066/531-666 · dragomir@kestrelsec.io · kestrelsec.io"))
        opis = {"domena": "mail domena", "sajt": "sajt", "nalozi": "procurjeli nalozi",
                "mreza": "mreža", "windows": "Windows mašina",
                "hardver": "popis hardvera", "pingcastle": "Active Directory",
                "cms": "CMS i izloženi fajlovi", "wifi": "bežična mreža",
                "dijeljeno": "dijeljeni folderi", "softver": "instalirani softver",
                "politika": "politika lozinki", "inventar": "inventar uređaja",
                "win11": "spremnost za Windows 11", "backup": "backup",
                "izlozenost": "izloženost sa interneta",
                "pasivno": "pasivni uvid (Shodan)",
                "licence": "licence i aktivacija",
                "stampaci": "popis štampača"}
        podaci["obim"] = ", ".join(opis.get(p, p) for p in podaci.get("provjere", []))
        if podaci.get("odgovori"):
            podaci["obim"] += ", razgovor sa klijentom"
        threading.Thread(target=pokreni, args=(podaci,), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/stanje")
def api_stanje():
    oc = ocjena(POSAO["nalazi"])
    return jsonify({
        "radi": POSAO["radi"], "gotovo": POSAO["gotovo"], "korak": POSAO["korak"],
        "napredak": POSAO["napredak"], "dnevnik": POSAO["dnevnik"][-120:],
        "nalazi": POSAO["nalazi"], "ocjena": oc,
        "pdf": POSAO["pdf"], "sazetak": POSAO.get("sazetak"),
        "greske": POSAO.get("greske") or [],
        "treba_izvjestaj": bool(POSAO.get("treba_izvjestaj")),
        "prekid": bool(POSAO.get("prekid")),
        "prekinut": bool(POSAO.get("prekinut")),
        "folder": os.path.basename(POSAO["folder"]) if POSAO["folder"] else None,
    })


def _napravi_izvjestaje():
    """Napravi oba PDF-a iz trenutnog stanja nalaza."""
    folder = POSAO["folder"]
    podaci = POSAO["podaci"]
    ime = bezbjedno_ime(podaci.get("firma"))
    POSAO["greske"] = [g for g in (POSAO.get("greske") or [])
                       if not g.startswith(("PDF izvještaj:", "Sažetak:"))]
    POSAO["nalazi"] = sortiraj(POSAO["nalazi"])

    pdf = os.path.join(folder, f"Sigurnosni_pregled_{ime}.pdf")
    try:
        izvjestaj.napravi(podaci, POSAO["nalazi"], pdf, RESURSI)
        POSAO["pdf"] = os.path.basename(pdf)
    except Exception as e:
        POSAO["greske"].append(f"PDF izvještaj: {type(e).__name__}: {e}")

    saz = os.path.join(folder, f"Sazetak_{ime}.pdf")
    try:
        izvjestaj.sazetak(podaci, POSAO["nalazi"], saz, RESURSI)
        POSAO["sazetak"] = os.path.basename(saz)
    except Exception as e:
        POSAO["greske"].append(f"Sažetak: {type(e).__name__}: {e}")

    m_zapisi.upisi(folder, "izvjestaj", podaci.get("izvrsio"),
                   {"fajl": POSAO["pdf"], "nalaza": len(POSAO["nalazi"])},
                   podaci.get("lokacija_puna") or "")
    return POSAO["pdf"]


@app.route("/api/izmijeni", methods=["POST"])
def api_izmijeni():
    """Tehničar ispravlja procjenu i dodaje stručni komentar."""
    if POSAO["radi"]:
        return jsonify({"ok": False, "greska": "Skeniranje je u toku."}), 409
    t = request.get_json(force=True) or {}
    try:
        i = int(t.get("indeks"))
        n = POSAO["nalazi"][i]
    except (TypeError, ValueError, IndexError):
        return jsonify({"ok": False, "greska": "Nalaz nije pronađen."}), 404

    promjene = m_rucni_unos.primijeni_ispravku(n, t)
    if not promjene:
        return jsonify({"ok": True, "promjena": False})

    m_zapisi.upisi(POSAO["folder"], "izmjena", POSAO["podaci"].get("izvrsio"),
                   dict(promjene, nalaz=n.get("naslov")),
                   POSAO["podaci"].get("lokacija_puna") or "")
    log(f'Ispravka: {n.get("naslov")} — ' +
        "; ".join(f'{k}: {v.get("prije")} → {v.get("poslije")}'
                  for k, v in promjene.items() if k != "komentar"))
    POSAO["treba_izvjestaj"] = True
    return jsonify({"ok": True, "promjena": True, "nalaz": n})


@app.route("/api/uredjaj", methods=["POST"])
def api_uredjaj():
    """Ručni unos uređaja koji alat ne može očitati."""
    if POSAO["radi"]:
        return jsonify({"ok": False, "greska": "Skeniranje je u toku."}), 409
    if not POSAO["folder"]:
        return jsonify({"ok": False, "greska": "Prvo pokreni pregled."}), 400
    u = request.get_json(force=True) or {}
    if not (u.get("naziv") or "").strip():
        return jsonify({"ok": False, "greska": "Naziv uređaja je obavezan."}), 400

    n = m_rucni_unos.u_nalaz(u)
    POSAO["nalazi"].append(n)
    m_zapisi.upisi(POSAO["folder"], "rucni_uredjaj",
                   POSAO["podaci"].get("izvrsio"),
                   {"naziv": u.get("naziv"), "vrsta_uredjaja": u.get("vrsta"),
                    "stanje": u.get("stanje")},
                   POSAO["podaci"].get("lokacija_puna") or "")
    log(f'Ručno unesen uređaj: {u.get("naziv")}')
    POSAO["treba_izvjestaj"] = True
    return jsonify({"ok": True, "nalaz": n})


@app.route("/api/izvjestaj-ponovo", methods=["POST"])
def api_izvjestaj_ponovo():
    if POSAO["radi"]:
        return jsonify({"ok": False, "greska": "Skeniranje je u toku."}), 409
    if not POSAO["folder"]:
        return jsonify({"ok": False, "greska": "Nema pregleda."}), 400
    try:
        za_snimanje = {k: v for k, v in POSAO["podaci"].items()
                       if k != "ad_lozinka"}
        with open(os.path.join(POSAO["folder"], "nalazi.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"podaci": za_snimanje, "nalazi": POSAO["nalazi"],
                       "sirovo": POSAO["sirovo"]}, f, ensure_ascii=False,
                      indent=2, default=str)
    except Exception as e:
        log(f"nalazi.json nije snimljen — {e}")
    _napravi_izvjestaje()
    POSAO["treba_izvjestaj"] = False
    log("Izvještaj napravljen ponovo, sa ispravkama")
    return jsonify({"ok": True, "pdf": POSAO["pdf"],
                    "sazetak": POSAO.get("sazetak")})


@app.route("/api/zapisi")
def api_zapisi():
    if not POSAO["folder"]:
        return jsonify([])
    st = m_zapisi.procitaj(POSAO["folder"])
    return jsonify([{"vrijeme": z.get("vrijeme_utc"), "vrsta": z.get("vrsta"),
                     "opis": z.get("opis"), "tehnicar": z.get("tehnicar"),
                     "sazetak": m_zapisi.sazmi(z)} for z in reversed(st)])


@app.route("/api/vrste-uredjaja")
def api_vrste():
    return jsonify({"vrste": m_rucni_unos.VRSTE,
                    "stanja": [{"kljuc": k, "opis": v[0]}
                               for k, v in m_rucni_unos.STANJA.items()]})


@app.route("/api/prekini", methods=["POST"])
def api_prekini():
    """Zaustavi pregled. Provjera koja je u toku se dovrši, ostale se preskaču —
    izvještaj se pravi od onoga što je do tada urađeno."""
    if not POSAO["radi"]:
        return jsonify({"ok": False, "greska": "Pregled nije u toku."}), 400
    POSAO["prekid"] = True
    POSAO["korak"] = "Prekidam…"
    log("Zatražen prekid pregleda — čekam da se tekuća provjera završi")
    return jsonify({"ok": True})


@app.route("/api/verzija")
def api_verzija():
    """Provjeri ima li novija verzija. Ne smije oboriti sučelje ako nema mreže."""
    p = ucitaj_postavke()
    if not p.get("azuriranje_automatski", True) and request.args.get("sam") != "1":
        return jsonify({"moja": VERZIJA, "ima_novu": False, "iskljuceno": True})
    return jsonify(m_azuriranje.provjeri(p.get("azuriranje_url"), VERZIJA))


@app.route("/api/azuriraj", methods=["POST"])
def api_azuriraj():
    if POSAO["radi"]:
        return jsonify({"ok": False, "greska": "Pregled je u toku — sačekaj kraj."}), 409
    p = ucitaj_postavke()
    info = m_azuriranje.provjeri(p.get("azuriranje_url"), VERZIJA)
    if info.get("greska"):
        return jsonify({"ok": False, "greska": info["greska"]}), 400
    if not info.get("ima_novu"):
        return jsonify({"ok": False, "greska": "Već imaš najnoviju verziju."}), 400
    ok, poruka = m_azuriranje.ugradi(info.get("zip"), KORIJEN, log)
    return jsonify({"ok": ok, "poruka" if ok else "greska": poruka,
                    "verzija": info.get("verzija")}), (200 if ok else 400)


@app.route("/api/pregledi")
def api_pregledi():
    return jsonify(m_spajanje.popis(REZULTATI))


@app.route("/api/uvezi-putanju", methods=["POST"])
def api_uvezi_putanju():
    """Uvoz sa druge putanje — stick, drugi disk, mrežni folder."""
    putanja = (request.get_json(force=True) or {}).get("putanja") or ""
    r = m_uvoz.iz_putanje(REZULTATI, putanja, KORIJEN)
    if r.get("ok"):
        log(f'Uvezeno pregleda: {len(r["uvezeno"])} sa {putanja}')
    return jsonify(r), (200 if r.get("ok") else 400)


@app.route("/api/uvezi-fajl", methods=["POST"])
def api_uvezi_fajl():
    """Uvoz fajla izabranog u pregledaču — nalazi.json ili zip pregleda."""
    f = request.files.get("fajl")
    if not f or not f.filename:
        return jsonify({"ok": False, "greska": "Nije izabran fajl."}), 400

    ime = os.path.basename(f.filename)
    if not (ime.lower() == "nalazi.json" or ime.lower().endswith((".json", ".zip"))):
        return jsonify({"ok": False,
                        "greska": "Izaberi nalazi.json ili zip pregleda."}), 400

    privremeni = os.path.join(KORIJEN, "_uvoz")
    os.makedirs(privremeni, exist_ok=True)
    put = os.path.join(privremeni, "nalazi.json" if ime.lower().endswith(".json")
                       else "pregled.zip")
    try:
        f.save(put)
        r = m_uvoz.iz_putanje(REZULTATI, put, KORIJEN)
    except Exception as e:
        r = {"ok": False, "greska": f"{type(e).__name__}: {e}"}
    finally:
        try:
            shutil.rmtree(privremeni, ignore_errors=True)
        except Exception:
            pass
    if r.get("ok"):
        log(f'Uvezeno pregleda: {len(r["uvezeno"])} iz fajla {ime}')
    return jsonify(r), (200 if r.get("ok") else 400)


@app.route("/api/spoji", methods=["POST"])
def api_spoji():
    folderi = (request.get_json(force=True) or {}).get("folderi") or []
    if len(folderi) < 2:
        return jsonify({"ok": False, "greska": "Izaberi bar dva pregleda."}), 400

    podaci, nalazi, masine = m_spajanje.spoji(REZULTATI, folderi)
    if not podaci:
        return jsonify({"ok": False, "greska": "Pregledi se ne mogu učitati."}), 400

    p = ucitaj_postavke()
    podaci.setdefault("izvrsio", p.get("izvrsio", "Dragomir Babić, KestrelSec"))
    podaci.setdefault("kontakt", p.get("kontakt", ""))
    podaci["datum"] = datetime.date.today().strftime("%d.%m.%Y.")

    ime = bezbjedno_ime(podaci.get("firma"))
    folder = ime_foldera(podaci.get("firma"), predmetak="ZBIRNI")
    os.makedirs(folder, exist_ok=True)

    with open(os.path.join(folder, "nalazi.json"), "w", encoding="utf-8") as f:
        json.dump({"podaci": podaci, "nalazi": nalazi, "masine": masine},
                  f, ensure_ascii=False, indent=2)

    pdf = os.path.join(folder, f"Zbirni_pregled_{ime}.pdf")
    izvjestaj.napravi(podaci, nalazi, pdf, RESURSI)
    saz = os.path.join(folder, f"Sazetak_{ime}.pdf")
    izvjestaj.sazetak(podaci, nalazi, saz, RESURSI)

    POSAO["folder"] = folder
    tehnicar = podaci.get("izvrsio") or ""
    lok = podaci.get("lokacija_puna") or ""
    m_zapisi.upisi(folder, "pocetak", tehnicar, {
        "firma": podaci.get("firma"), "obim": podaci.get("obim"),
        "masina": podaci.get("masina")}, lok)
    POSAO["pdf"] = os.path.basename(pdf)
    POSAO["sazetak"] = os.path.basename(saz)
    POSAO["nalazi"] = nalazi
    POSAO["gotovo"] = True
    POSAO["korak"] = "Zbirni izvještaj"
    POSAO["napredak"] = 100
    log(f"Zbirni izvještaj od {len(masine)} pregleda: {os.path.basename(folder)}")
    return jsonify({"ok": True, "pdf": os.path.basename(pdf),
                    "sazetak": os.path.basename(saz),
                    "folder": os.path.basename(folder),
                    "masine": masine, "masina": len(masine),
                    "nalaza": len(nalazi)})


@app.route("/api/postavke", methods=["GET", "POST"])
def api_postavke():
    if request.method == "POST":
        p = ucitaj_postavke()
        p.update(request.get_json(force=True))
        snimi_postavke(p)
        return jsonify({"ok": True})
    p = ucitaj_postavke()
    return jsonify({"izvrsio": p.get("izvrsio", ""), "kontakt": p.get("kontakt", ""),
                    "hibp_razmak": p.get("hibp_razmak") or 6.5,
                    "ima_kljuc": bool(p.get("hibp_kljuc")),
                    "ima_shodan": bool(p.get("shodan_kljuc")),
                    "verzija": VERZIJA,
                    "azuriranje_url": p.get("azuriranje_url", ""),
                    "azuriranje_automatski": p.get("azuriranje_automatski", True)})


@app.route("/preuzmi/<path:ime>")
def preuzmi(ime):
    if not POSAO["folder"]:
        return "Nema rezultata", 404
    return send_from_directory(POSAO["folder"], ime, as_attachment=True)


@app.route("/api/otvori-folder", methods=["POST"])
def otvori_folder():
    f = POSAO["folder"]
    if not f:
        return jsonify({"ok": False})
    try:
        if sys.platform.startswith("win"):
            os.startfile(f)
        elif sys.platform == "darwin":
            os.system(f'open "{f}"')
        else:
            os.system(f'xdg-open "{f}"')
    except Exception:
        return jsonify({"ok": False})
    return jsonify({"ok": True})


def slobodan_port(pocetni=PORT, pokusaja=20):
    """Ako je 8777 zauzet — drugi alat, ranije pokrenuta kopija — uzmi sljedeći
    slobodan umjesto da pucaš sa greškom koju niko ne zna pročitati."""
    for p in range(pocetni, pocetni + pokusaja):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return pocetni


def main():
    global PORT
    PORT = slobodan_port()
    url = f"http://127.0.0.1:{PORT}/"
    print(f"\n  KestrelScan {VERZIJA} radi na {url}\n  Zatvori ovaj prozor da prekineš.\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
