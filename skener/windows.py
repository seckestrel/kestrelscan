# -*- coding: utf-8 -*-
"""Provjere na Windows mašini — sve kroz PowerShell, bez instalacije.

Na Linuxu i macOS-u modul se tiho preskače.
"""
import json
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO

JE_WINDOWS = sys.platform.startswith("win")


def _ps(skripta, timeout=60):
    """Pokrene PowerShell i vrati raščlanjen JSON ili None."""
    if not JE_WINDOWS:
        return None
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", skripta],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        izlaz = (r.stdout or "").strip()
        if not izlaz:
            return None
        return json.loads(izlaz)
    except Exception:
        return None


def provjeri(log=lambda s: None):
    nalazi, sirovo = [], {}

    if not JE_WINDOWS:
        nalazi.append(nalaz(
            "Uređaji", "Provjere Windows mašine nisu izvršene", INFO,
            f"Alat je pokrenut na {sys.platform}, a ove provjere rade samo na Windowsu.",
            preporuka="Pokrenuti alat sa USB-a na mašini u domenu klijenta."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    # --- BitLocker ---
    log("Šifrovanje diska")
    bl = _ps("Get-BitLockerVolume | Select-Object MountPoint,VolumeStatus,"
             "ProtectionStatus | ConvertTo-Json -Compress")
    if bl is not None:
        bl = bl if isinstance(bl, list) else [bl]
        sirovo["bitlocker"] = bl
        nesifrovani = [v.get("MountPoint") for v in bl
                       if str(v.get("VolumeStatus")) not in ("1", "FullyEncrypted")]
        if nesifrovani:
            nalazi.append(nalaz(
                "Uređaji", "Disk nije šifrovan", SREDNJI,
                "Nešifrovani volumeni: " + ", ".join(str(x) for x in nesifrovani),
                "Ako se računar izgubi ili bude ukraden, svako ko dođe do njega "
                "može izvaditi disk i pročitati sve. Lozinka za prijavu ga ne zaustavlja.",
                "Uključiti BitLocker i sačuvati ključeve za oporavak van te mašine.",
                sati=1, trosak=60, dokaz=[json.dumps(bl, ensure_ascii=False)]))
        else:
            nalazi.append(nalaz("Uređaji", "Disk je šifrovan", DOBRO,
                                "Svi volumeni su potpuno šifrovani."))

    # --- SMB ---
    log("SMB postavke")
    smb = _ps("Get-SmbServerConfiguration | Select-Object RequireSecuritySignature,"
              "EnableSecuritySignature,EnableSMB1Protocol | ConvertTo-Json -Compress")
    if smb:
        sirovo["smb"] = smb
        if smb.get("EnableSMB1Protocol"):
            nalazi.append(nalaz(
                "Uređaji", "SMBv1 je i dalje uključen", VISOK,
                "Stari SMBv1 protokol je aktivan na ovoj mašini.",
                "SMBv1 je protokol kroz koji se širio WannaCry. Nema razloga da "
                "bude uključen na sistemu iz ovog vijeka.",
                "Isključiti: Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol",
                sati=0.5, dokaz=["EnableSMB1Protocol = True"]))
        if not smb.get("RequireSecuritySignature"):
            nalazi.append(nalaz(
                "Uređaji", "SMB potpisivanje nije obavezno", SREDNJI,
                "RequireSecuritySignature je isključen.",
                "Napadač na istoj mreži može presresti prijavu i proslijediti je "
                "serveru. Rizik je stvaran ako mreža nije segmentirana.",
                "Uključiti obavezno potpisivanje kroz GPO, uz prethodno testiranje "
                "na starijim mrežnim štampačima.",
                sati=1.5, trosak=90,
                dokaz=[json.dumps(smb, ensure_ascii=False)]))
        else:
            nalazi.append(nalaz("Uređaji", "SMB potpisivanje je obavezno", DOBRO,
                                "RequireSecuritySignature je uključen."))

    # --- lokalni administratori ---
    log("Lokalni administratori")
    adm = _ps("Get-LocalGroupMember -Group (Get-LocalGroup -SID "
              "'S-1-5-32-544').Name | Select-Object Name,ObjectClass | "
              "ConvertTo-Json -Compress")
    if adm is not None:
        adm = adm if isinstance(adm, list) else [adm]
        sirovo["lokalni_admini"] = adm
        imena = [a.get("Name", "") for a in adm]
        if len(imena) > 3:
            nalazi.append(nalaz(
                "Lozinke i pristupi", "Previše lokalnih administratora", SREDNJI,
                f"U grupi Administrators ima {len(imena)} članova: " + ", ".join(imena),
                "Svaki administratorski nalog je dodatna meta. Zlonamjerni program "
                "pokrenut pod administratorom može sve na toj mašini.",
                "Svesti na najmanji broj. Svakodnevni rad treba ići pod nalogom "
                "bez administratorskih prava.",
                sati=1, trosak=60, dokaz=imena))
        else:
            nalazi.append(nalaz("Lozinke i pristupi", "Broj lokalnih administratora je u redu",
                                DOBRO, ", ".join(imena)))

    # --- gost nalog ---
    gost = _ps("Get-LocalUser -Name Guest | Select-Object Enabled | ConvertTo-Json -Compress")
    if gost and gost.get("Enabled"):
        nalazi.append(nalaz(
            "Lozinke i pristupi", "Nalog Guest je uključen", SREDNJI,
            "Ugrađeni nalog Guest je aktivan.",
            "Pristup sistemu bez lozinke i bez traga ko je šta radio.",
            "Isključiti: Disable-LocalUser -Name Guest", sati=0.25))

    # --- firewall ---
    log("Firewall")
    fw = _ps("Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json -Compress")
    if fw:
        fw = fw if isinstance(fw, list) else [fw]
        sirovo["firewall"] = fw
        iskljuceni = [p.get("Name") for p in fw if not p.get("Enabled")]
        if iskljuceni:
            nalazi.append(nalaz(
                "Uređaji", "Firewall je isključen", VISOK,
                "Isključeni profili: " + ", ".join(str(x) for x in iskljuceni),
                "Mašina prihvata veze sa mreže bez ikakve kontrole.",
                "Uključiti sve profile: Set-NetFirewallProfile -All -Enabled True",
                sati=0.25, dokaz=[json.dumps(fw, ensure_ascii=False)]))
        else:
            nalazi.append(nalaz("Uređaji", "Firewall je uključen na svim profilima", DOBRO, ""))

    # --- antivirus ---
    # Windows Security Center vodi SVE registrovane antiviruse. Ako se čita samo
    # Defender, mašina sa Kasperskyjem ili ESET-om izgleda kao nezaštićena —
    # Defender tada pređe u pasivni režim i prijavi da mu je zaštita isključena.
    log("Zaštita od zlonamjernog softvera")
    sc = _ps("Get-CimInstance -Namespace root/SecurityCenter2 "
             "-ClassName AntiVirusProduct | Select-Object displayName,"
             "productState,pathToSignedProductExe,timestamp | ConvertTo-Json -Compress")
    av = _ps("Get-MpComputerStatus | Select-Object AMServiceEnabled,"
             "RealTimeProtectionEnabled,AntivirusSignatureAge,AMRunningMode | "
             "ConvertTo-Json -Compress")
    sirovo["antivirus_defender"] = av

    proizvodi = []
    if sc:
        sc = sc if isinstance(sc, list) else [sc]
        for p in sc:
            stanje = p.get("productState")
            # productState je bitna maska: bajt 2 = je li zaštita aktivna,
            # bajt 3 = jesu li definicije svježe
            aktivan = osvjezen = None
            try:
                v = int(stanje)
                aktivan = ((v >> 12) & 0xF) in (1, 2, 3)
                osvjezen = ((v >> 4) & 0xF) == 0
            except (TypeError, ValueError):
                pass
            proizvodi.append({"naziv": p.get("displayName"), "stanje": stanje,
                              "aktivan": aktivan, "definicije_svjeze": osvjezen})
    sirovo["antivirus"] = proizvodi

    if proizvodi:
        imena = [p["naziv"] for p in proizvodi if p.get("naziv")]
        aktivni = [p for p in proizvodi if p.get("aktivan")]
        neaktivni = [p for p in proizvodi if p.get("aktivan") is False]
        zastarjeli = [p for p in proizvodi
                      if p.get("aktivan") and p.get("definicije_svjeze") is False]

        if not aktivni:
            nalazi.append(nalaz(
                "Uređaji", "Nijedan antivirus nije aktivan", VISOK,
                "Registrovano: " + ", ".join(imena) + " — nijedan ne prijavljuje "
                "aktivnu zaštitu.",
                "Zlonamjerni fajl se ne provjerava u trenutku pokretanja. Mašina "
                "je otvorena za sve što stigne mailom ili USB-om.",
                "Uključiti zaštitu, ili ukloniti proizvod koji je istekao pa "
                "vratiti ugrađeni Defender.",
                sati=0.5, trosak=30,
                dokaz=[f'{p["naziv"]}: productState={p["stanje"]}' for p in proizvodi]))
        else:
            nalazi.append(nalaz(
                "Uređaji", "Zaštita od zlonamjernog softvera je aktivna", DOBRO,
                "Aktivno: " + ", ".join(p["naziv"] for p in aktivni if p.get("naziv")),
                dokaz=[f'{p["naziv"]}: {"aktivan" if p.get("aktivan") else "neaktivan"}'
                       for p in proizvodi]))

        if zastarjeli:
            nalazi.append(nalaz(
                "Uređaji", "Definicije antivirusa nisu svježe", SREDNJI,
                "Zastarjele definicije: "
                + ", ".join(p["naziv"] for p in zastarjeli if p.get("naziv")),
                "Nove prijetnje se ne prepoznaju. Antivirus radi, ali gleda "
                "staru listu.",
                "Provjeriti zašto ažuriranje ne prolazi — obično je istekla "
                "licenca ili firewall blokira servis proizvođača.",
                sati=0.5, trosak=30))

        if len(aktivni) > 1:
            nalazi.append(nalaz(
                "Uređaji", "Više antivirusa aktivno u isto vrijeme", SREDNJI,
                "Aktivni: " + ", ".join(p["naziv"] for p in aktivni if p.get("naziv")),
                "Dva antivirusa koja istovremeno prate fajlove usporavaju mašinu "
                "i znaju se međusobno blokirati, pa zaštita bude slabija nego sa "
                "jednim.",
                "Ostaviti jedan proizvod aktivan, ostale ukloniti.",
                sati=1, trosak=60))

    elif av:
        # Security Center nije dostupan (obično na serverskim izdanjima) —
        # tada je Defender jedino što se može očitati
        rezim = str(av.get("AMRunningMode") or "")
        if "Passive" in rezim or "SxS" in rezim:
            nalazi.append(nalaz(
                "Uređaji", "Defender je u pasivnom režimu", INFO,
                f"AMRunningMode: {rezim}. To znači da je instaliran drugi "
                "antivirus koji je preuzeo zaštitu.",
                preporuka="Potvrditi sa klijentom koji proizvod je u upotrebi i "
                          "da li mu licenca važi.",
                dokaz=[json.dumps(av, ensure_ascii=False)]))
        elif not av.get("RealTimeProtectionEnabled"):
            nalazi.append(nalaz(
                "Uređaji", "Zaštita u stvarnom vremenu je isključena", VISOK,
                "Defender prijavljuje da zaštita u stvarnom vremenu ne radi, a "
                "nijedan drugi antivirus nije registrovan.",
                "Zlonamjerni fajl se ne provjerava u trenutku pokretanja.",
                "Uključiti zaštitu.", sati=0.25,
                dokaz=[json.dumps(av, ensure_ascii=False)]))
        else:
            nalazi.append(nalaz(
                "Uređaji", "Zaštita od zlonamjernog softvera je aktivna", DOBRO,
                "Windows Defender, zaštita u stvarnom vremenu uključena."))
        starost = av.get("AntivirusSignatureAge")
        if isinstance(starost, int) and starost > 7:
            nalazi.append(nalaz(
                "Uređaji", "Definicije antivirusa su zastarjele", SREDNJI,
                f"Definicije su stare {starost} dana.",
                "Nove prijetnje se ne prepoznaju.",
                "Provjeriti zašto ažuriranje ne prolazi.", sati=0.5))

    # --- ažuriranja ---
    log("Ažuriranja sistema")
    hf = _ps("Get-HotFix | Sort-Object InstalledOn -Descending | "
             "Select-Object -First 1 HotFixID,InstalledOn | ConvertTo-Json -Compress")
    if hf:
        sirovo["zadnja_zakrpa"] = hf
        import datetime
        try:
            tekst = str(hf.get("InstalledOn", ""))
            ms = int("".join(c for c in tekst if c.isdigit())[:13])
            d = datetime.datetime.fromtimestamp(ms / 1000)
            dana = (datetime.datetime.now() - d).days
            if dana > 60:
                nalazi.append(nalaz(
                    "Uređaji", "Sistem dugo nije ažuriran", VISOK,
                    f"Zadnja zakrpa ({hf.get('HotFixID')}) instalirana prije {dana} dana.",
                    "Poznate ranjivosti ostaju otvorene. Većina napada koristi "
                    "propuste za koje zakrpa postoji mjesecima.",
                    "Uključiti automatsko ažuriranje i provjeriti zašto je stalo.",
                    sati=1, trosak=60, dokaz=[json.dumps(hf, ensure_ascii=False)]))
            else:
                nalazi.append(nalaz(
                    "Uređaji", "Ažuriranja se instaliraju redovno", DOBRO,
                    f"Zadnja zakrpa prije {dana} dana."))
        except Exception:
            pass

    # --- neuspjele prijave ---
    log("Evidencija prijava")
    ev = _ps("""
$e = Get-WinEvent -FilterHashtable @{LogName='Security';ID=4625} -MaxEvents 2000 -ErrorAction SilentlyContinue
if ($e) {
  $g = $e | Group-Object -Property {$_.Properties[19].Value} |
       Sort-Object Count -Descending | Select-Object -First 8 Count,Name
  $g | ConvertTo-Json -Compress
} else { '[]' }
""", timeout=90)
    if ev:
        ev = ev if isinstance(ev, list) else [ev]
        sirovo["neuspjele_prijave"] = ev
        spolja = [g for g in ev if str(g.get("Name") or "").strip()
                  and not str(g.get("Name")).startswith(("192.168.", "10.", "172.", "-", "::"))
                  and int(g.get("Count") or 0) > 50]
        ukupno = sum(int(g.get("Count") or 0) for g in ev)
        if spolja:
            nalazi.append(nalaz(
                "Lozinke i pristupi", "Masovni pokušaji prijave sa stranih adresa", VISOK,
                "Najaktivnije adrese: " + ", ".join(
                    f'{g["Name"]} ({g["Count"]} pokušaja)' for g in spolja[:5]),
                "Ovo nije teorija — neko aktivno pogađa lozinke na ovoj mašini. "
                "Obično znači da je neki servis izložen prema internetu.",
                "Utvrditi koji servis je izložen i zatvoriti ga ili staviti iza VPN-a. "
                "Uključiti zaključavanje naloga nakon niza neuspjelih pokušaja.",
                sati=2, trosak=120,
                dokaz=[f'{g["Name"]}: {g["Count"]}' for g in ev]))
        elif ukupno:
            nalazi.append(nalaz(
                "Lozinke i pristupi", "Neuspjele prijave u evidenciji", INFO,
                f"Ukupno {ukupno} neuspjelih prijava u dostupnom periodu, "
                "sve sa adresa lokalne mreže.",
                preporuka="Uobičajeno je da korisnici pogriješe lozinku. Vrijedi "
                          "provjeriti ako je broj neočekivano velik.",
                dokaz=[f'{g.get("Name")}: {g.get("Count")}' for g in ev]))

    # --- veličina evidencije ---
    vel = _ps("Get-WinEvent -ListLog Security | Select-Object MaximumSizeInBytes,"
              "RecordCount | ConvertTo-Json -Compress")
    if vel:
        sirovo["evidencija"] = vel
        mb = int(vel.get("MaximumSizeInBytes") or 0) / 1048576
        if mb and mb < 128:
            nalazi.append(nalaz(
                "Nadzor", "Evidencija prijava je premala", NIZAK,
                f"Security evidencija je ograničena na {mb:.0f} MB.",
                "Stari zapisi se brišu za nekoliko dana. Ako se nešto desi, nema "
                "se šta pogledati unazad.",
                "Povećati na najmanje 512 MB.", sati=0.25))

    # --- domen ---
    log("Active Directory")
    dom = _ps("(Get-CimInstance Win32_ComputerSystem) | Select-Object Domain,"
              "PartOfDomain | ConvertTo-Json -Compress")
    if dom:
        sirovo["domen"] = dom
        if dom.get("PartOfDomain"):
            da = _ps("""
try {
  Import-Module ActiveDirectory -ErrorAction Stop
  $m = Get-ADGroupMember 'Domain Admins' | Select-Object -Expand SamAccountName
  $d = Search-ADAccount -AccountInactive -TimeSpan 90.00:00:00 -UsersOnly |
       Where-Object {$_.Enabled -eq $true} | Select-Object -Expand SamAccountName
  @{admins=@($m); dormantni=@($d)} | ConvertTo-Json -Compress
} catch { '{}' }
""", timeout=90)
            if da and da.get("admins"):
                sirovo["ad"] = da
                admini = da.get("admins") or []
                dorm = da.get("dormantni") or []
                if len(admini) > 2:
                    nalazi.append(nalaz(
                        "Lozinke i pristupi", "Previše naloga u grupi Domain Admins", SREDNJI,
                        f"{len(admini)} naloga: " + ", ".join(admini),
                        "Kompromitacija bilo kog od njih znači kompromitaciju cijelog "
                        "domena, a ne jedne mašine.",
                        "Svesti na najviše dva. Servisnim nalozima dodijeliti samo "
                        "prava koja im stvarno trebaju.",
                        sati=1.5, trosak=90, dokaz=admini))
                if dorm:
                    nalazi.append(nalaz(
                        "Lozinke i pristupi", "Nalozi bivših zaposlenih nisu ugašeni", SREDNJI,
                        f"{len(dorm)} aktivnih naloga bez prijave preko 90 dana: "
                        + ", ".join(dorm[:10]),
                        "Dormantni nalog je otvorena vrata koja niko ne gleda. "
                        "Lozinka se ne mijenja, a prijava se ne primjećuje.",
                        "Onemogućiti naloge i uvesti obavezan korak gašenja pri odlasku zaposlenog.",
                        sati=1, trosak=60, dokaz=dorm))
            else:
                nalazi.append(nalaz(
                    "Lozinke i pristupi", "Provjera domena nije izvršena", INFO,
                    f"Mašina je u domenu {dom.get('Domain')}, ali PowerShell modul "
                    "ActiveDirectory nije dostupan.",
                    preporuka="Pokrenuti PingCastle (dugme u alatu) ili instalirati "
                              "RSAT alate na jednoj administratorskoj mašini."))

    return {"nalazi": nalazi, "sirovo": sirovo}
