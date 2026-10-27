# -*- coding: utf-8 -*-
"""Bežične mreže: šifrovanje, sačuvani profili, lozinke u čistom tekstu."""
import re
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")

SLABO = {
    "open": ("Otvorena mreža bez lozinke", VISOK),
    "wep": ("WEP — probija se za nekoliko minuta", VISOK),
    "wpa": ("WPA (prva verzija) — zastarjelo", SREDNJI),
    "wpa2-personal": ("WPA2 sa dijeljenom lozinkom", INFO),
    "wpa3": ("WPA3 — aktuelno", DOBRO),
}


def _netsh(args, timeout=25):
    if not JE_WINDOWS:
        return ""
    try:
        r = subprocess.run(["netsh"] + args, capture_output=True, text=True,
                           timeout=timeout, errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout or ""
    except Exception:
        return ""


def _polje(tekst, *kljucevi):
    for k in kljucevi:
        m = re.search(rf"{k}\s*:\s*(.+)", tekst, re.I)
        if m:
            return m.group(1).strip()
    return None


def provjeri(log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        return {"nalazi": [nalaz(
            "Mreža", "Provjera bežične mreže nije izvršena", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta.")], "sirovo": sirovo}

    log("Trenutna bežična veza")
    iface = _netsh(["wlan", "show", "interfaces"])
    sirovo["interfejs"] = iface
    if not iface.strip() or "There is no wireless" in iface or "nema" in iface.lower():
        nalazi.append(nalaz("Mreža", "Nema bežičnog adaptera", INFO,
                            "Mašina nema WiFi, pa je provjera preskočena."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    ssid = _polje(iface, r"^\s*SSID", "SSID")
    aut = _polje(iface, "Authentication", "Potvrda identiteta", "Autentikacija")
    sif = _polje(iface, "Cipher", "Šifra", "Šifriranje")
    sirovo.update({"ssid": ssid, "autentikacija": aut, "sifra": sif})

    if aut:
        k = aut.lower().replace(" ", "").replace("-personal", "-personal")
        tez, opis = INFO, aut
        if "open" in k or "otvoren" in k:
            tez = VISOK
            nalazi.append(nalaz(
                "Mreža", "Bežična mreža je bez lozinke", VISOK,
                f'Mreža "{ssid}" radi bez šifrovanja.',
                "Svako u dometu vidi saobraćaj i može se priključiti na mrežu firme.",
                "Uključiti WPA2 ili WPA3 sa lozinkom od najmanje 16 znakova.",
                sati=0.5, trosak=30, dokaz=[f"SSID {ssid}: {aut}"]))
        elif "wep" in k:
            nalazi.append(nalaz(
                "Mreža", "Bežična mreža koristi WEP", VISOK,
                f'Mreža "{ssid}" koristi WEP šifrovanje.',
                "WEP se probija za nekoliko minuta besplatnim alatom. Praktično je "
                "isto kao da mreža nema lozinku.",
                "Prebaciti na WPA2 ili WPA3. Ako oprema ne podržava, zamijeniti ruter.",
                sati=1, trosak=60, dokaz=[f"SSID {ssid}: {aut}"]))
        elif k.startswith("wpa") and "wpa2" not in k and "wpa3" not in k:
            nalazi.append(nalaz(
                "Mreža", "Bežična mreža koristi prvu verziju WPA", SREDNJI,
                f'Mreža "{ssid}" koristi {aut}.',
                "WPA prve generacije ima poznate slabosti i smatra se zastarjelim.",
                "Prebaciti na WPA2 ili WPA3.", sati=0.5, trosak=30))
        elif "wpa3" in k:
            nalazi.append(nalaz("Mreža", "Bežična mreža koristi WPA3", DOBRO,
                                f'Mreža "{ssid}" — {aut}, {sif}.'))
        else:
            nalazi.append(nalaz("Mreža", "Bežična mreža koristi WPA2", DOBRO,
                                f'Mreža "{ssid}" — {aut}, {sif}.'))

    log("Sačuvani profili")
    profili_txt = _netsh(["wlan", "show", "profiles"])
    profili = re.findall(r":\s*(.+)$", profili_txt, re.M)
    profili = [p.strip() for p in profili if p.strip()]
    sirovo["profili"] = profili

    otvoreni, sa_lozinkom = [], []
    for p in profili[:40]:
        det = _netsh(["wlan", "show", "profile", f"name={p}", "key=clear"], timeout=15)
        a = _polje(det, "Authentication", "Potvrda identiteta") or ""
        kljuc = _polje(det, "Key Content", "Sadržaj ključa")
        if "open" in a.lower() or "otvoren" in a.lower():
            otvoreni.append(p)
        if kljuc:
            sa_lozinkom.append(p)

    if otvoreni:
        nalazi.append(nalaz(
            "Mreža", "Mašina pamti otvorene bežične mreže", SREDNJI,
            "Sačuvane mreže bez lozinke: " + ", ".join(otvoreni),
            "Laptop se automatski priključi na mrežu istog naziva gdje god je sretne. "
            "Napadač može postaviti lažnu mrežu sa istim imenom i presresti saobraćaj.",
            "Obrisati profile mreža koje se više ne koriste, a za ostale isključiti "
            "automatsko povezivanje.",
            sati=0.5, dokaz=otvoreni))

    if sa_lozinkom:
        nalazi.append(nalaz(
            "Mreža", "Lozinke bežičnih mreža se mogu pročitati sa mašine", NIZAK,
            f"{len(sa_lozinkom)} sačuvanih profila otkriva lozinku komandom "
            "netsh wlan show profile key=clear.",
            "Svako ko dođe do otključane mašine može pročitati lozinku poslovne "
            "mreže i zapisati je.",
            "Nije greška u postavkama nego osobina sistema. Rješava se tako što se "
            "mašine zaključavaju i što se lozinka mreže mijenja pri odlasku zaposlenog.",
            dokaz=[f"{len(sa_lozinkom)} profila sa čitljivom lozinkom"]))

    if len(profili) > 25:
        nalazi.append(nalaz(
            "Mreža", "Mašina pamti mnogo bežičnih mreža", NIZAK,
            f"Sačuvano {len(profili)} profila.",
            "Svaki zapamćen profil je mreža na koju se uređaj sam povezuje.",
            "Obrisati profile koji se više ne koriste.", sati=0.25))

    return {"nalazi": nalazi, "sirovo": sirovo}
