# -*- coding: utf-8 -*-
"""Provjera i ugradnja nove verzije alata.

Alat na pokretanju pročita jedan mali JSON sa interneta i uporedi broj verzije
sa svojim. Ako je objavljena novija, javi to u sučelju i ponudi ugradnju —
preuzme zip, raspakuje ga preko sebe i sačuva postavke i rezultate.

Oblik fajla `verzija.json` koji stoji na serveru:

    {
      "verzija": "1.6.0",
      "datum": "20.10.2026.",
      "promjene": ["Dodata provjera licenci", "Popravljen DKIM"],
      "zip": "https://kestrelsec.io/alat/KestrelScan.zip"
    }
"""
import io
import os
import re
import shutil
import sys
import zipfile

import requests

# ne diraj ove pri ugradnji — to je rad tehničara, ne program
CUVAJ = {"postavke.json", "rezultati", "tools", "_prethodna"}


def _broj(v):
    """'1.10.2' -> (1, 10, 2); poređenje mora biti po brojevima, ne po slovima,
    inače je '1.9' veće od '1.10'."""
    d = re.findall(r"\d+", str(v or "0"))
    return tuple(int(x) for x in d[:4]) or (0,)


def puna_adresa(vrijednost):
    """Dozvoli da se upiše samo `korisnik/repozitorij` umjesto cijele adrese.

    Skraćeni oblik se raširi u raw.githubusercontent.com adresu grane main,
    koja uvijek daje zadnje objavljeno stanje — adresa se nikad ne mijenja.
    """
    v = (vrijednost or "").strip()
    if not v:
        return ""
    if "://" in v:
        return v
    v = v.strip("/")
    if re.fullmatch(r"[\w.-]+/[\w.-]+", v):
        return f"https://raw.githubusercontent.com/{v}/main/verzija.json"
    return v


def provjeri(url, moja_verzija, timeout=8):
    url = puna_adresa(url)
    """Vrati šta se zna o novoj verziji. Nikad ne baca grešku — provjera
    ažuriranja ne smije spriječiti rad alata."""
    out = {"moja": moja_verzija, "ima_novu": False, "verzija": None,
           "datum": "", "promjene": [], "zip": "", "greska": ""}
    if not (url or "").strip():
        out["greska"] = "Nije podešena adresa za provjeru ažuriranja."
        return out
    try:
        r = requests.get(url.strip(), timeout=timeout,
                         headers={"Cache-Control": "no-cache"})
        if r.status_code != 200:
            out["greska"] = f"Server je vratio {r.status_code}."
            return out
        d = r.json()
    except Exception as e:
        out["greska"] = f"{type(e).__name__}: {e}"
        return out

    out["verzija"] = str(d.get("verzija") or "").strip()
    out["datum"] = str(d.get("datum") or "")
    out["promjene"] = [str(x) for x in (d.get("promjene") or [])][:12]
    out["zip"] = str(d.get("zip") or "").strip()
    out["ima_novu"] = bool(out["verzija"]) and _broj(out["verzija"]) > _broj(moja_verzija)
    return out


def _bezbjedni_clanovi(z):
    """Zip sa interneta ne smije pisati van svog foldera."""
    for c in z.infolist():
        ime = c.filename.replace("\\", "/")
        if ime.startswith("/") or ".." in ime.split("/"):
            continue
        yield c, ime


def ugradi(zip_url, korijen, log=lambda s: None, timeout=120):
    """Preuzmi zip i raspakuj ga preko alata. Vrati (ok, poruka)."""
    if getattr(sys, "frozen", False):
        # .exe nosi cijeli program u sebi i ne može sam sebe zamijeniti dok
        # radi. Raspakivanje .py fajlova pored njega ne bi promijenilo ništa,
        # pa je poštenije reći šta treba uraditi.
        return False, (
            "Ovo je .exe verzija i ona se ne može sama ažurirati — program je "
            "zapakovan u jedan fajl. Ažuriraj izvornu verziju na svom računaru "
            "(tamo ovo dugme radi), pa pokreni NAPRAVI_EXE.bat i novi "
            "KestrelScan.exe prekopiraj na USB.")

    if not (zip_url or "").strip():
        return False, "U verzija.json ne stoji adresa zip fajla."

    log("Preuzimam novu verziju")
    try:
        r = requests.get(zip_url.strip(), timeout=timeout)
        if r.status_code != 200:
            return False, f"Preuzimanje nije uspjelo — server je vratio {r.status_code}."
        podaci = io.BytesIO(r.content)
        z = zipfile.ZipFile(podaci)
    except Exception as e:
        return False, f"Preuzimanje nije uspjelo — {type(e).__name__}: {e}"

    # --- je li ovo uopšte KestrelScan ---
    imena = [i.replace("\\", "/") for _, i in _bezbjedni_clanovi(z)]
    korijen_u_zipu = ""
    if not any(i == "app.py" for i in imena):
        vrhovi = {i.split("/")[0] for i in imena if "/" in i}
        for v in vrhovi:
            if f"{v}/app.py" in imena and any(i.startswith(f"{v}/skener/") for i in imena):
                korijen_u_zipu = v + "/"
                break
        if not korijen_u_zipu:
            return False, "Preuzeti fajl nije KestrelScan paket."
    log(f"Paket ima {len(imena)} fajlova")

    # --- kopija zatečenog stanja, da se ima čemu vratiti ---
    rezerva = os.path.join(korijen, "_prethodna")
    try:
        shutil.rmtree(rezerva, ignore_errors=True)
        os.makedirs(rezerva, exist_ok=True)
        for ime in os.listdir(korijen):
            if ime in CUVAJ:
                continue
            izvor = os.path.join(korijen, ime)
            cilj = os.path.join(rezerva, ime)
            if os.path.isdir(izvor):
                shutil.copytree(izvor, cilj, dirs_exist_ok=True)
            else:
                shutil.copy2(izvor, cilj)
    except Exception as e:
        log(f"   kopija zatečenog stanja nije napravljena: {e}")

    # --- raspakuj preko ---
    upisano, preskoceno = 0, 0
    for clan, ime in _bezbjedni_clanovi(z):
        if korijen_u_zipu:
            if not ime.startswith(korijen_u_zipu):
                continue
            ime = ime[len(korijen_u_zipu):]
        if not ime or ime.endswith("/"):
            continue
        vrh = ime.split("/")[0]
        if vrh in CUVAJ:
            preskoceno += 1
            continue
        cilj = os.path.join(korijen, *ime.split("/"))
        try:
            os.makedirs(os.path.dirname(cilj), exist_ok=True)
            with z.open(clan) as u, open(cilj, "wb") as izl:
                shutil.copyfileobj(u, izl)
            upisano += 1
        except Exception as e:
            log(f"   {ime} — {type(e).__name__}: {e}")
            preskoceno += 1

    if not upisano:
        return False, "Nijedan fajl nije upisan. Alat je ostao na staroj verziji."
    log(f"Upisano {upisano} fajlova, preskočeno {preskoceno}")
    return True, (f"Ugrađeno {upisano} fajlova. Postavke i rezultati nisu dirani. "
                  f"Zatvori prozor alata i pokreni ga ponovo da nova verzija "
                  f"počne da radi.")
