# -*- coding: utf-8 -*-
"""Spremnost za Windows 11 — TPM, Secure Boot, procesor, memorija, disk.

Odgovara na pitanje koje svaki klijent postavi kad mu kažeš da je sistem van
podrške: može li se mašina nadograditi ili se mora mijenjati.
"""
import json
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO
from . import starost as m_starost

JE_WINDOWS = sys.platform.startswith("win")

# Microsoft traži Intel 8. generacije ili noviji, odnosno AMD Ryzen 2000 ili noviji
NAJSTARIJI_INTEL = 2017
NAJSTARIJI_AMD = 2018


def _ps(skripta, timeout=45):
    if not JE_WINDOWS:
        return None
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
             "Bypass", "-Command", skripta],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        izlaz = (r.stdout or "").strip()
        return json.loads(izlaz) if izlaz else None
    except Exception:
        return None


def procesor_podrzan(cpu):
    """Vrati (True/False/None, objašnjenje)."""
    g, opis = m_starost.godina_procesora(cpu)
    if g is None:
        return None, "Generacija procesora nije prepoznata."
    t = (cpu or "").lower()
    prag = NAJSTARIJI_AMD if ("ryzen" in t or "amd" in t) else NAJSTARIJI_INTEL
    if g >= prag:
        return True, f"{opis} Zadovoljava uslov."
    return False, (f"{opis} Microsoft traži Intel 8. generacije ili AMD Ryzen "
                   f"2000 i novije.")


def provjeri(hardver_sirovo=None, log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Uređaji", "Provjera spremnosti za Windows 11 nije izvršena", INFO,
            "Ova provjera radi samo na Windowsu.",
            preporuka="Pokrenuti alat na mašini klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    h = hardver_sirovo or {}
    sistem = str(h.get("sistem") or "")
    if "windows 11" in sistem.lower():
        nalazi.append(nalaz(
            "Uređaji", "Mašina je već na Windowsu 11", DOBRO, sistem))
        return {"nalazi": nalazi, "sirovo": {"vec_11": True}}

    log("TPM i Secure Boot")
    tpm = _ps("Get-CimInstance -Namespace root/CIMV2/Security/MicrosoftTpm "
              "-ClassName Win32_Tpm | Select-Object SpecVersion,"
              "IsEnabled_InitialValue,IsActivated_InitialValue | "
              "ConvertTo-Json -Compress")
    sb = _ps("try { @{secure=[bool](Confirm-SecureBootUEFI)} | ConvertTo-Json "
             "-Compress } catch { @{secure=$null} | ConvertTo-Json -Compress }")

    prepreke, uslovi = [], []

    # --- TPM ---
    tpm_ok = None
    if tpm:
        verzija = str(tpm.get("SpecVersion") or "")
        ukljucen = bool(tpm.get("IsEnabled_InitialValue"))
        aktiviran = bool(tpm.get("IsActivated_InitialValue"))
        sirovo["tpm"] = {"verzija": verzija, "ukljucen": ukljucen,
                         "aktiviran": aktiviran}
        ima_20 = "2.0" in verzija
        tpm_ok = ima_20 and ukljucen and aktiviran
        if not ima_20:
            prepreke.append("TPM 2.0 ne postoji")
            uslovi.append(f"TPM: {verzija or 'nema'} — ne zadovoljava")
        elif not (ukljucen and aktiviran):
            prepreke.append("TPM je prisutan ali isključen")
            uslovi.append(f"TPM 2.0: prisutan, ali nije uključen u BIOS-u")
        else:
            uslovi.append("TPM 2.0: uključen i aktiviran")
    else:
        sirovo["tpm"] = None
        prepreke.append("TPM nije pronađen")
        uslovi.append("TPM: nije pronađen")

    # --- Secure Boot ---
    if sb and sb.get("secure") is not None:
        sirovo["secure_boot"] = bool(sb["secure"])
        if sb["secure"]:
            uslovi.append("Secure Boot: uključen")
        else:
            prepreke.append("Secure Boot je isključen")
            uslovi.append("Secure Boot: isključen")
    else:
        sirovo["secure_boot"] = None
        uslovi.append("Secure Boot: nije očitan (mašina je vjerovatno u "
                      "starom BIOS režimu)")
        prepreke.append("Secure Boot nije potvrđen")

    # --- procesor ---
    cpu_ok, cpu_opis = procesor_podrzan(h.get("cpu"))
    sirovo["procesor_podrzan"] = cpu_ok
    uslovi.append(f"Procesor: {h.get('cpu') or 'nepoznat'} — {cpu_opis}")
    if cpu_ok is False:
        prepreke.append("procesor nije na Microsoftovoj listi")

    # --- memorija i disk ---
    ram = h.get("ram_gb")
    if ram is not None:
        uslovi.append(f"Memorija: {ram:g} GB — "
                      + ("zadovoljava" if ram >= 4 else "traži se najmanje 4 GB"))
        if ram < 4:
            prepreke.append("manje od 4 GB memorije")
    sistemska = next((p for p in h.get("particije", []) if p.get("gb")), None)
    if sistemska:
        uslovi.append(f'Sistemski disk: {sistemska["gb"]:g} GB — '
                      + ("zadovoljava" if sistemska["gb"] >= 64
                         else "traži se najmanje 64 GB"))
        if sistemska["gb"] < 64:
            prepreke.append("sistemski disk manji od 64 GB")

    # --- presuda ---
    nerjesive = [p for p in prepreke
                 if "procesor" in p or "ne postoji" in p or "nije pronađen" in p]
    rjesive = [p for p in prepreke if p not in nerjesive]

    if not prepreke:
        nalazi.append(nalaz(
            "Uređaji", "Mašina ispunjava uslove za Windows 11", DOBRO,
            "Svi uslovi su zadovoljeni — nadogradnja je moguća bez zamjene opreme.",
            dokaz=uslovi))
    elif nerjesive:
        nalazi.append(nalaz(
            "Uređaji", "Mašina se ne može nadograditi na Windows 11", VISOK,
            "Prepreke: " + ", ".join(prepreke) + ".",
            "Sistem na ovoj mašini je van podrške i ne dobija sigurnosne zakrpe, "
            "a hardver ne dozvoljava nadogradnju. Jedino rješenje je zamjena "
            "uređaja ili prelazak na drugi sistem.",
            "Uvrstiti mašinu u plan zamjene. Do zamjene je izdvojiti u zaseban "
            "mrežni segment i obavezno šifrovati disk.",
            sati=1, dokaz=uslovi))
    else:
        nalazi.append(nalaz(
            "Uređaji", "Windows 11 je moguć, ali treba podesiti BIOS", SREDNJI,
            "Treba riješiti: " + ", ".join(rjesive) + ".",
            "Hardver zadovoljava uslove — prepreka je samo u postavkama firmvera. "
            "Dok se to ne uradi, mašina ostaje na sistemu koji ne dobija zakrpe.",
            "Uključiti TPM i Secure Boot u BIOS-u, pa pokrenuti nadogradnju. "
            "Prije toga obavezno napraviti kopiju podataka.",
            sati=1.5, trosak=90, dokaz=uslovi))

    sirovo["prepreke"] = prepreke
    sirovo["uslovi"] = uslovi
    return {"nalazi": nalazi, "sirovo": sirovo}
