# -*- coding: utf-8 -*-
"""Pasivni uvid spolja — šta o klijentu već zna Shodan.

Razlika u odnosu na provjeru „Izloženost sa interneta": ovdje se ništa ne kuca
na klijentovu adresu. Samo se čita ono što je Shodan ranije vidio i objavio.
Zato se može uraditi i prije nego što firma postane klijent.

Cijena toga je starost podatka. Shodan vidi adresu svakih nekoliko dana do
nekoliko sedmica, a male firme često imaju dinamičku adresu od provajdera — pa
ono što je viđeno prošle sedmice može biti tuđi uređaj. Zato svaki nalaz odavde
nosi datum i piše „prema javnoj evidenciji", nikad kao tvrdnja o stanju danas.
"""
import datetime
import socket

import requests

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

API = "https://api.shodan.io/shodan/host/{ip}?key={kljuc}&minify=false"
BESPLATNI = "https://internetdb.shodan.io/{ip}"

# servisi koji na javnoj adresi male firme nemaju šta tražiti
OPASNI = {
    3389: ("Udaljena radna površina (RDP)", VISOK,
           "Najčešći put ulaska ucjenjivačkog softvera. Automati non-stop "
           "pretražuju internet i pokušavaju lozinke na svakom otvorenom RDP-u."),
    445: ("Dijeljenje fajlova (SMB)", VISOK,
          "SMB na javnoj adresi je put kojim se širio WannaCry. Nema razloga da "
          "ikad bude dostupan sa interneta."),
    23: ("Telnet", VISOK,
         "Telnet šalje lozinku u čitljivom obliku i nema ga na uređaju koji je "
         "iko ažurirao u zadnjih deset godina."),
    21: ("FTP", SREDNJI,
         "FTP šalje korisničko ime i lozinku nešifrovano."),
    3306: ("MySQL baza", VISOK,
           "Baza podataka direktno na internetu. Ako je u njoj išta klijentovo, "
           "to je prijava curenja podataka, ne tehnički propust."),
    1433: ("MS SQL baza", VISOK,
           "Baza podataka direktno na internetu."),
    5432: ("PostgreSQL baza", VISOK, "Baza podataka direktno na internetu."),
    27017: ("MongoDB", VISOK,
            "MongoDB je godinama bio otvoren bez lozinke po fabričkim "
            "postavkama — ovo je čest izvor curenja podataka."),
    9200: ("Elasticsearch", VISOK, "Baza pretrage direktno na internetu."),
    5900: ("VNC", VISOK,
           "Daljinski pristup ekranu, često bez ikakve lozinke."),
    6379: ("Redis", VISOK, "Redis po fabričkim postavkama nema lozinku."),
    8000: ("Web sučelje uređaja", SREDNJI,
           "Čest port video-nadzora i mrežnih uređaja sa fabričkom lozinkom."),
    8080: ("Web sučelje uređaja", NIZAK,
           "Obično upravljačko sučelje nekog uređaja."),
    554: ("Video nadzor (RTSP)", SREDNJI,
          "Snimak kamere dostupan sa interneta, često bez lozinke."),
    9100: ("Direktna štampa", SREDNJI,
           "Štampač dostupan sa interneta — svako može slati zadatke, a kod "
           "nekih modela i čitati memoriju uređaja."),
    161: ("SNMP", SREDNJI,
          "Sa fabričkom zajednicom otkriva popis uređaja i postavke mreže."),
    25: ("Mail server (SMTP)", NIZAK,
         "Provjeriti da nije otvoreni relej."),
}


def _datum(s):
    """Shodan vraća 2026-10-09T11:22:33.000000 — nama treba 09.10.2026."""
    if not s:
        return ""
    try:
        d = datetime.datetime.fromisoformat(str(s).split(".")[0])
        return d.strftime("%d.%m.%Y.")
    except Exception:
        return str(s)[:10]


def _adresa(javna_ip, domena, log):
    if (javna_ip or "").strip():
        return javna_ip.strip(), ""
    d = (domena or "").strip().replace("https://", "").replace("http://", "").strip("/")
    if not d:
        return "", "Nije unesena javna adresa ni domena."
    try:
        ip = socket.gethostbyname(d)
        log(f"Domena {d} pokazuje na {ip}")
        return ip, ""
    except Exception as e:
        return "", f"Domena {d} se ne može razriješiti: {e}"


def _dohvati(ip, kljuc, log):
    """Vrati (podaci, izvor, greska)."""
    if kljuc:
        try:
            r = requests.get(API.format(ip=ip, kljuc=kljuc), timeout=25)
            if r.status_code == 200:
                return r.json(), "Shodan (ključ)", ""
            if r.status_code == 404:
                return {}, "Shodan (ključ)", ""        # nema zapisa — to je dobro
            if r.status_code in (401, 403):
                log("   ključ nije prihvaćen — prelazim na besplatni izvor")
            elif r.status_code == 429:
                log("   previše upita — prelazim na besplatni izvor")
            else:
                log(f"   Shodan je vratio {r.status_code} — prelazim na besplatni izvor")
        except Exception as e:
            log(f"   Shodan nije dostupan ({type(e).__name__}) — besplatni izvor")

    try:
        r = requests.get(BESPLATNI.format(ip=ip), timeout=20)
        if r.status_code == 404:
            return {}, "InternetDB", ""
        if r.status_code == 200:
            return r.json(), "InternetDB", ""
        return None, "InternetDB", f"Servis je vratio {r.status_code}"
    except Exception as e:
        return None, "InternetDB", f"{type(e).__name__}: {e}"


def _uredi(d, izvor):
    """Dva izvora, dva oblika — svedi na jedno."""
    if izvor.startswith("Shodan"):
        servisi = []
        for s in d.get("data") or []:
            servisi.append({
                "port": s.get("port"),
                "proizvod": " ".join(x for x in (s.get("product"),
                                                 s.get("version")) if x),
                "vidjeno": _datum(s.get("timestamp")),
            })
        return {
            "portovi": sorted({s["port"] for s in servisi if s["port"]}),
            "servisi": servisi,
            "ranjivosti": sorted((d.get("vulns") or [])),
            "imena": d.get("hostnames") or [],
            "organizacija": d.get("org") or d.get("isp") or "",
            "drzava": d.get("country_name") or "",
            "vidjeno": _datum(d.get("last_update")),
            "oznake": d.get("tags") or [],
        }
    return {
        "portovi": sorted(d.get("ports") or []),
        "servisi": [],
        "ranjivosti": sorted(d.get("vulns") or []),
        "imena": d.get("hostnames") or [],
        "organizacija": "",
        "drzava": "",
        "vidjeno": "",
        "oznake": d.get("tags") or [],
    }


OGRADA = ("Podatak je iz javne evidencije interneta, ne iz mjerenja na licu "
          "mjesta. Adresa koju firma danas ima mogla je prošle sedmice "
          "pripadati drugom pretplatniku, pa svaki nalaz odavde treba potvrditi "
          "prije nego se po njemu postupa.")


def provjeri(javna_ip, domena=None, kljuc=None, log=lambda s: None):
    nalazi, sirovo = [], {}

    ip, greska = _adresa(javna_ip, domena, log)
    if not ip:
        nalazi.append(nalaz(
            "Izloženost", "Pasivni uvid nije izvršen", INFO, greska,
            preporuka="Unijeti javnu adresu klijenta ili domenu."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    log(f"Pasivni uvid za {ip}")
    podaci, izvor, greska = _dohvati(ip, kljuc, log)

    if podaci is None:
        nalazi.append(nalaz(
            "Izloženost", "Pasivni uvid nije izvršen", INFO,
            f"Izvor podataka nije dostupan: {greska}",
            preporuka="Provjeriti vezu prema internetu i ključ u Postavkama."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    if not podaci:
        nalazi.append(nalaz(
            "Izloženost", "Adresa nije u javnoj evidenciji", DOBRO,
            f"O adresi {ip} nema zapisa. To znači da pretraživači interneta na "
            f"njoj nisu zatekli nijedan otvoren servis.",
            dokaz=[f"{izvor}: nema zapisa za {ip}"]))
        return {"nalazi": nalazi, "sirovo": {"ip": ip, "izvor": izvor}}

    p = _uredi(podaci, izvor)
    sirovo = dict(p, ip=ip, izvor=izvor)
    log(f"   {len(p['portovi'])} portova, {len(p['ranjivosti'])} oznaka ranjivosti")

    # --- šta se vidi spolja ---
    po_portu = {s["port"]: s for s in p["servisi"]}
    redovi = []
    for port in p["portovi"]:
        s = po_portu.get(port, {})
        opis, _, _ = OPASNI.get(port, ("", None, ""))[0:3] if port in OPASNI \
            else ("", None, "")
        redovi.append([str(port), opis or "—", s.get("proizvod") or "—",
                       s.get("vidjeno") or p["vidjeno"] or "—"])

    detalji = []
    if p["organizacija"]:
        detalji.append(f'Provajder / organizacija: {p["organizacija"]}')
    if p["imena"]:
        detalji.append("Imena: " + ", ".join(p["imena"][:6]))
    if p["vidjeno"]:
        detalji.append(f'Zadnji put viđeno: {p["vidjeno"]}')

    nalazi.append(nalaz(
        "Izloženost", f"Sa interneta se na {ip} vidi {len(p['portovi'])} servisa",
        INFO,
        (". ".join(detalji) + ". " if detalji else "")
        + f"Izvor: {izvor}. " + OGRADA,
        preporuka="Svaki servis koji ovdje stoji a nije namjerno objavljen treba "
                  "zatvoriti na ruteru ili firewallu.",
        tabela={"zaglavlje": ["Port", "Šta je to", "Prepoznato", "Viđeno"],
                "redovi": redovi, "sirine": [10, 32, 36, 22]},
        dokaz=[f"{ip}:{r[0]}  {r[2]}  ({r[3]})" for r in redovi]))

    # --- opasni servisi ---
    for port in p["portovi"]:
        if port not in OPASNI:
            continue
        ime, tezina, zasto = OPASNI[port]
        s = po_portu.get(port, {})
        nalazi.append(nalaz(
            "Izloženost", f"Sa interneta je dostupno: {ime}", tezina,
            f"Na javnoj adresi {ip} otvoren je port {port}"
            + (f' — prepoznato: {s["proizvod"]}' if s.get("proizvod") else "")
            + (f'. Viđeno {s.get("vidjeno") or p["vidjeno"]}'
               if (s.get("vidjeno") or p["vidjeno"]) else "") + ".",
            zasto + " " + OGRADA,
            f"Zatvoriti port {port} na ruteru. Ako je pristup stvarno potreban, "
            "ide kroz VPN, ne otvaranjem porta.",
            sati=1, trosak=60,
            dokaz=[f"{ip}:{port} — {s.get('proizvod') or ime} "
                   f"({s.get('vidjeno') or p['vidjeno'] or 'bez datuma'})",
                   f"izvor: {izvor}"]))

    # --- poznate ranjivosti ---
    if p["ranjivosti"]:
        prvih = p["ranjivosti"][:14]
        nalazi.append(nalaz(
            "Izloženost", f"Poznate ranjivosti vezane za ovu adresu "
                          f"({len(p['ranjivosti'])})",
            VISOK if len(p["ranjivosti"]) >= 3 else SREDNJI,
            "Oznake: " + ", ".join(prvih)
            + (f" i još {len(p['ranjivosti']) - 14}" if len(p["ranjivosti"]) > 14 else "")
            + ". " + OGRADA,
            "Oznake se vežu za verziju softvera koju je pretraživač prepoznao "
            "spolja. Ne znači da je svaka iskoristiva, ali znači da je verzija "
            "dovoljno stara da se o njoj zna i da je napadač vidi isto kao i mi.",
            "Utvrditi koji uređaj ili servis je u pitanju i ažurirati ga. Ako se "
            "ne može ažurirati, skloniti ga sa javne adrese.",
            sati=2, trosak=120,
            dokaz=p["ranjivosti"][:40] + [f"izvor: {izvor}"]))

    if p["oznake"]:
        nalazi.append(nalaz(
            "Izloženost", "Oznake koje nosi adresa", INFO,
            ", ".join(p["oznake"]) + ". " + OGRADA,
            preporuka="Oznaka govori kakav je uređaj iza adrese — npr. "
                      "self-signed (sertifikat sam sebi izdat), ics "
                      "(industrijska oprema), printer, cloud.",
            dokaz=p["oznake"]))

    return {"nalazi": nalazi, "sirovo": sirovo}
