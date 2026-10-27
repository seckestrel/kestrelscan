# -*- coding: utf-8 -*-
"""Provjera sajta: sertifikat, verzije TLS-a, sigurnosna zaglavlja, preusmjeravanje.

Sve se radi direktno, bez SSL Labs API-ja — pa radi i kad je mreža klijenta
iza firewalla koji ne pušta vanjske servise.
"""
import datetime
import socket
import ssl

import requests
from requests.exceptions import RequestException

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, DOBRO

ZAGLAVLJA = [
    ("strict-transport-security", "HSTS", SREDNJI,
     "Pregledač može biti naveden da se poveže preko nešifrovanog HTTP-a."),
    ("content-security-policy", "CSP", NIZAK,
     "Nema zaštite od ubacivanja stranog skripta u stranicu."),
    ("x-frame-options", "X-Frame-Options", NIZAK,
     "Stranica se može ugraditi u tuđi sajt i iskoristiti za prevaru klikom."),
    ("x-content-type-options", "X-Content-Type-Options", NIZAK,
     "Pregledač može pogrešno protumačiti tip fajla."),
    ("referrer-policy", "Referrer-Policy", NIZAK,
     "Adrese vaših stranica se prosljeđuju stranim sajtovima."),
]

VERZIJE = [
    ("TLS 1.0", ssl.TLSVersion.TLSv1, True),
    ("TLS 1.1", ssl.TLSVersion.TLSv1_1, True),
    ("TLS 1.2", ssl.TLSVersion.TLSv1_2, False),
    ("TLS 1.3", ssl.TLSVersion.TLSv1_3, False),
]


def _sertifikat(host, port=443, timeout=8):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as s:
        with ctx.wrap_socket(s, server_hostname=host) as ss:
            return ss.getpeercert(), ss.version(), ss.cipher()


def _podrzava(host, verzija, port=443, timeout=5):
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = verzija
        ctx.maximum_version = verzija
        with socket.create_connection((host, port), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=host):
                return True
    except (ssl.SSLError, OSError, ValueError):
        return False


def provjeri(domena, log=lambda s: None):
    host = domena.strip().lower()
    for p in ("https://", "http://"):
        if host.startswith(p):
            host = host[len(p):]
    host = host.split("/")[0]

    nalazi = []
    sirovo = {"host": host}

    # --- sertifikat ---
    log(f"Sertifikat za {host}")
    try:
        cert, verzija, sifra = _sertifikat(host)
        sirovo["tls_verzija"] = verzija
        sirovo["sifra"] = sifra[0] if sifra else None
        izdavac = dict(x[0] for x in cert.get("issuer", ())).get("organizationName", "nepoznat")
        istek = cert.get("notAfter")
        dana = None
        if istek:
            d = datetime.datetime.strptime(istek, "%b %d %H:%M:%S %Y %Z")
            dana = (d - datetime.datetime.utcnow()).days
        sirovo["izdavac"] = izdavac
        sirovo["istice_za_dana"] = dana

        if dana is None:
            pass
        elif dana < 0:
            nalazi.append(nalaz(
                "Sajt firme", "Sertifikat je istekao", VISOK,
                f"Sertifikat je istekao prije {abs(dana)} dana. Izdavač: {izdavac}.",
                "Posjetiocima se prikazuje upozorenje o nesigurnoj vezi. Dio "
                "ljudi odustane na tom ekranu.",
                "Obnoviti sertifikat i uključiti automatsko obnavljanje.",
                sati=0.5, trosak=30, dokaz=[f"notAfter = {istek}"]))
        elif dana < 21:
            nalazi.append(nalaz(
                "Sajt firme", "Sertifikat uskoro ističe", SREDNJI,
                f"Sertifikat ističe za {dana} dana. Izdavač: {izdavac}.",
                "Ako obnavljanje nije automatsko, sajt će za manje od tri sedmice "
                "prikazivati upozorenje.",
                "Provjeriti da li je automatsko obnavljanje uključeno.",
                sati=0.25, dokaz=[f"notAfter = {istek}"]))
        else:
            nalazi.append(nalaz(
                "Sajt firme", "Sertifikat je važeći", DOBRO,
                f"Važi još {dana} dana. Izdavač: {izdavac}.",
                dokaz=[f"notAfter = {istek}"]))
    except Exception as e:
        sirovo["greska_tls"] = str(e)
        nalazi.append(nalaz(
            "Sajt firme", "HTTPS nije dostupan", VISOK,
            f"Povezivanje na {host}:443 nije uspjelo ({type(e).__name__}).",
            "Sajt ili ne koristi HTTPS, ili je nedostupan. Sve što posjetilac "
            "unese putuje nešifrovano.",
            "Postaviti sertifikat (Let's Encrypt je besplatan) i preusmjeriti HTTP na HTTPS.",
            sati=1, trosak=60, dokaz=[str(e)]))
        return {"nalazi": nalazi, "sirovo": sirovo}

    # --- verzije TLS-a ---
    log("Verzije TLS-a")
    podrzane, stare = [], []
    for ime, v, zastarjela in VERZIJE:
        try:
            if _podrzava(host, v):
                podrzane.append(ime)
                if zastarjela:
                    stare.append(ime)
        except ValueError:
            continue  # lokalni OpenSSL ne podržava tu verziju
    sirovo["tls_podrzane"] = podrzane
    if stare:
        nalazi.append(nalaz(
            "Sajt firme", "Omogućene su zastarjele verzije TLS-a", NIZAK,
            "Server i dalje prihvata: " + ", ".join(stare),
            "Stare verzije imaju poznate slabosti i obaraju ocjenu sajta.",
            "Isključiti TLS 1.0 i 1.1 u konfiguraciji web servera ili na hostingu.",
            sati=0.5, trosak=30,
            dokaz=[f"podržano: {', '.join(podrzane) or 'ništa'}"]))
    elif podrzane:
        nalazi.append(nalaz(
            "Sajt firme", "Podržane su samo aktuelne verzije TLS-a", DOBRO,
            "Server prihvata: " + ", ".join(podrzane),
            dokaz=[f"podržano: {', '.join(podrzane)}"]))

    # --- zaglavlja i preusmjeravanje ---
    log("Sigurnosna zaglavlja")
    try:
        r = requests.get(f"https://{host}", timeout=10, allow_redirects=True,
                         headers={"User-Agent": "KestrelScan/1.0"})
        h = {k.lower(): v for k, v in r.headers.items()}
        sirovo["zaglavlja"] = h
        nedostaju = [(ime, tez, rizik) for kljuc, ime, tez, rizik in ZAGLAVLJA
                     if kljuc not in h]
        if nedostaju:
            najteze = SREDNJI if any(t == SREDNJI for _, t, _ in nedostaju) else NIZAK
            nalazi.append(nalaz(
                "Sajt firme", "Nedostaju sigurnosna HTTP zaglavlja", najteze,
                "Nedostaju: " + ", ".join(i for i, _, _ in nedostaju),
                "; ".join(r for _, _, r in nedostaju[:2]),
                "Dodati zaglavlja u konfiguraciji web servera ili kroz dodatak na CMS-u.",
                sati=0.5, trosak=30,
                dokaz=[f"{k}: {v}" for k, v in list(h.items())[:8]]))
        else:
            nalazi.append(nalaz(
                "Sajt firme", "Sva osnovna sigurnosna zaglavlja su postavljena", DOBRO,
                "Pronađena su sva zaglavlja sa liste.", dokaz=[]))

        # server banner
        if "server" in h:
            sirovo["server"] = h["server"]

        try:
            rh = requests.get(f"http://{host}", timeout=8, allow_redirects=False,
                              headers={"User-Agent": "KestrelScan/1.0"})
            lok = rh.headers.get("Location", "")
            sirovo["http_status"] = rh.status_code
            if rh.status_code in (301, 302, 307, 308) and lok.startswith("https://"):
                nalazi.append(nalaz(
                    "Sajt firme", "HTTP se preusmjerava na HTTPS", DOBRO,
                    f"Odgovor {rh.status_code} vodi na {lok}", dokaz=[f"Location: {lok}"]))
            else:
                nalazi.append(nalaz(
                    "Sajt firme", "HTTP se ne preusmjerava na HTTPS", SREDNJI,
                    f"Zahtjev na http://{host} vraća {rh.status_code}, bez preusmjerenja.",
                    "Posjetilac koji ukuca adresu bez https ostaje na nešifrovanoj vezi.",
                    "Uključiti trajno preusmjeravanje (301) sa HTTP na HTTPS.",
                    sati=0.25, trosak=30))
        except RequestException:
            pass
    except RequestException as e:
        sirovo["greska_http"] = str(e)

    return {"nalazi": nalazi, "sirovo": sirovo}
