# -*- coding: utf-8 -*-
"""Popis uređaja na mreži i provjera otvorenih servisa.

Čisti Python — ne traži Nmap ni Npcap drajver, pa radi sa USB-a bez instalacije.
Koristi TCP connect, isto što radi `nmap -sT`.
"""
import concurrent.futures as cf
import ipaddress
import re
import socket
import subprocess
import sys

from .nalaz import nalaz, VISOK, SREDNJI, NIZAK, INFO, DOBRO
from . import mak as m_mak

PORTOVI = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 135: "MS RPC", 139: "NetBIOS", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 465: "SMTPS", 587: "SMTP", 993: "IMAPS", 995: "POP3S",
    1433: "MS SQL", 1521: "Oracle", 2049: "NFS", 3000: "web app",
    3306: "MySQL", 3389: "Udaljena radna površina", 5000: "web app",
    5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8000: "web app",
    8006: "Proxmox", 8080: "web app", 8443: "HTTPS alt", 9100: "Štampanje",
    27017: "MongoDB", 5985: "WinRM", 5986: "WinRM TLS", 161: "SNMP",
    554: "RTSP kamera", 1900: "UPnP", 111: "RPC",
}

# servisi koji ne smiju biti dostupni sa interneta
OPASNO_SPOLJA = {3389: "Udaljena radna površina", 445: "SMB", 23: "Telnet",
                 21: "FTP", 3306: "MySQL", 5432: "PostgreSQL", 1433: "MS SQL",
                 5900: "VNC", 6379: "Redis", 27017: "MongoDB", 135: "MS RPC",
                 139: "NetBIOS", 5985: "WinRM"}

# servisi koji su problem i unutar mreže
NESIGURNI = {23: "Telnet šalje lozinku u čistom tekstu",
             21: "FTP šalje lozinku u čistom tekstu",
             161: "SNMP često radi sa fabričkom zajednicom 'public'",
             6379: "Redis je često bez lozinke",
             27017: "MongoDB je često bez lozinke"}


def _ziv(ip, portovi=(445, 80, 443, 22, 135, 3389, 139, 8006, 8080, 8000,
                      5000, 3000, 21, 23, 9100, 554, 62078), timeout=0.6):
    for p in portovi:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                if s.connect_ex((ip, p)) == 0:
                    return True
        except OSError:
            pass
    return _ping(ip)


def _ping(ip, timeout=1):
    zastava = "-n" if sys.platform.startswith("win") else "-c"
    cek = "-w" if sys.platform.startswith("win") else "-W"
    vr = str(timeout * 1000) if sys.platform.startswith("win") else str(timeout)
    try:
        r = subprocess.run(["ping", zastava, "1", cek, vr, ip],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=timeout + 2)
        return r.returncode == 0
    except Exception:
        return False


def _ime(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def _skeniraj_host(ip, portovi, timeout=0.7):
    otvoreni = []
    for p in portovi:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                if s.connect_ex((ip, p)) == 0:
                    otvoreni.append(p)
        except OSError:
            pass
    return otvoreni


def moja_mreza():
    """Pogodi lokalni opseg, npr. 192.168.1.0/24."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        return str(ipaddress.ip_network(ip + "/24", strict=False))
    except Exception:
        return "192.168.1.0/24"



# imena po kojima se prepoznaje tunel ili VPN adapter
VPN_TRAGOVI = ("vpn", "tap-", "tap0", "openvpn", "wireguard", "wg0",
               "fortinet", "forticlient", "anyconnect", "cisco",
               "globalprotect", "pulse", "juniper", "sonicwall", "checkpoint",
               "zerotier", "tailscale", "softether", "ppp", "l2tp", "pptp",
               "sstp", "ikev2", "nordlynx", "proton", "mullvad", "tunnel",
               "teredo", "hamachi", "radmin vpn")


def _lokalne_mreze():
    """Mreže na koje je ova mašina direktno priključena — sve van toga ide
    preko rutera ili tunela."""
    out = []
    if JE_WINDOWS:
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command",
                 "Get-NetIPAddress -AddressFamily IPv4 | Select-Object "
                 "IPAddress,PrefixLength,InterfaceAlias | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=25,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            import json as _j
            d = _j.loads((r.stdout or "").strip() or "[]")
            for a in (d if isinstance(d, list) else [d]):
                ip, duz = a.get("IPAddress"), a.get("PrefixLength")
                if not ip or duz in (None, ""):
                    continue
                try:
                    out.append((ipaddress.ip_network(f"{ip}/{duz}", strict=False),
                                a.get("InterfaceAlias") or ""))
                except ValueError:
                    pass
        except Exception:
            pass
    else:
        try:
            r = subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True,
                               text=True, timeout=15)
            for red in (r.stdout or "").splitlines():
                d = red.split()
                if len(d) >= 4 and "/" in d[3]:
                    try:
                        out.append((ipaddress.ip_network(d[3], strict=False), d[1]))
                    except ValueError:
                        pass
        except Exception:
            pass
    return [(m, i) for m, i in out if not m.is_loopback]


def _vpn_veze(lokalne):
    """Adapteri čije ime odaje tunel. Ne mjeri se saobraćaj — samo se gleda
    šta na mašini postoji."""
    nadjeni = []
    for mreza_, ime in lokalne:
        n = (ime or "").lower()
        if any(tr in n for tr in VPN_TRAGOVI):
            nadjeni.append({"adapter": ime, "mreza": str(mreza_)})
    return nadjeni


def razdvoji(tekst):
    """Jedan ili više opsega, odvojenih zarezom, tačka-zarezom ili razmakom.

    Firma sa kamerama na svom VLAN-u i gostima na trećem nema jednu mrežu nego
    tri. Vraća (ispravni_opsezi, neispravni_unosi).
    """
    dijelovi = [d.strip() for d in re.split(r"[,;\s]+", (tekst or "").strip()) if d.strip()]
    mreze, lose = [], []
    for d in dijelovi:
        try:
            m = ipaddress.ip_network(d, strict=False)
        except ValueError:
            lose.append(d)
            continue
        if m not in mreze:
            mreze.append(m)
    return mreze, lose


def provjeri(opseg, log=lambda s: None, max_hostova=512):
    nalazi = []
    mreze, lose = razdvoji(opseg)

    if not mreze:
        return {"nalazi": [nalaz(
            "Mreža", "Neispravan mrežni opseg", INFO,
            f'Uneseno: {opseg}. Nijedan dio nije prepoznat kao mrežni opseg.',
            preporuka="Upisati u obliku 192.168.1.0/24. Više mreža se odvaja "
                      "zarezom: 192.168.1.0/24, 192.168.10.0/24")], "sirovo": {}}

    if lose:
        nalazi.append(nalaz(
            "Mreža", "Dio unesenih opsega nije prepoznat", INFO,
            "Preskočeno: " + ", ".join(lose) + ". Skenirano je ostalo: "
            + ", ".join(str(m) for m in mreze),
            preporuka="Opseg se piše kao 192.168.1.0/24. Raspon sa crticom "
                      "(192.168.1.10-50) se ne podržava."))

    # --- je li traženi opseg uopšte na ovoj mašini ---
    lokalne = _lokalne_mreze()
    dodatno = {"lokalne_mreze": [str(m) for m, _ in lokalne]}
    vpn = _vpn_veze(lokalne)
    if vpn:
        dodatno["vpn"] = vpn
        log("Pažnja: na mašini postoji VPN/tunel adapter — "
            + ", ".join(v["adapter"] for v in vpn))
        nalazi.append(nalaz(
            "Mreža", "Mašina ima VPN ili tunel prema drugoj mreži", INFO,
            "Prepoznati adapteri: "
            + ", ".join(f'{v["adapter"]} ({v["mreza"]})' for v in vpn) + ".",
            "Preko tunela se dolazi do mreže koja nije klijentova — centralni "
            "sistem, laboratorija, matična ustanova, dobavljač. Saglasnost "
            "klijenta ne pokriva tu mrežu, a skeniranje preko tunela je "
            "skeniranje tuđeg sistema.",
            "Ne skenirati opsege koji se dobijaju preko tunela. U razgovoru "
            "utvrditi čemu VPN služi, ko sve može da se spoji, ima li "
            "dvofaktorsku prijavu i da li dobavljač ima stalan pristup.",
            dokaz=[f'{v["adapter"]} — {v["mreza"]}' for v in vpn]))

    van_masine = [m for m in mreze
                  if not any(m.subnet_of(l) or l.subnet_of(m) or m == l
                             for l, _ in lokalne)]
    if lokalne and van_masine:
        log("Pažnja: traženi opseg nije na ovoj mašini — "
            + ", ".join(str(m) for m in van_masine))
        nalazi.append(nalaz(
            "Mreža", "Traženi opseg nije mreža ove mašine", INFO,
            "Skenira se: " + ", ".join(str(m) for m in van_masine)
            + ". Mašina je priključena na: "
            + ", ".join(str(m) for m, _ in lokalne) + ".",
            "Opseg do kojeg se dolazi preko rutera ili tunela može pripadati "
            "drugoj organizaciji. Saglasnost se odnosi samo na mrežu klijenta.",
            "Provjeriti da li uneseni opseg zaista pripada klijentu. Ako se do "
            "njega dolazi preko VPN-a, ne skenirati ga bez posebne pismene "
            "saglasnosti vlasnika te mreže.",
            dokaz=[f"traženo: {m}" for m in van_masine]
                  + [f"na mašini: {m} ({i})" for m, i in lokalne]))

    # jedinstvene adrese iz svih opsega, redom kako su unesene
    hostovi, vidjeno = [], set()
    for m in mreze:
        for h in (list(m.hosts()) or [m.network_address]):
            if h not in vidjeno:
                vidjeno.add(h)
                hostovi.append(h)
    ukupno = len(hostovi)
    hostovi = hostovi[:max_hostova]
    if ukupno > max_hostova:
        log(f"Ukupno {ukupno} adresa — skeniram prvih {max_hostova}")
        nalazi.append(nalaz(
            "Mreža", "Opseg je veći od granice pregleda", INFO,
            f"Uneseni opsezi imaju {ukupno} adresa, a pregled ide do "
            f"{max_hostova}. Skenirano je prvih {max_hostova}.",
            preporuka="Podijeliti pregled po mrežama i spojiti ih kroz zbirni "
                      "izvještaj."))

    opis_opsega = ", ".join(str(m) for m in mreze)

    if len(hostovi) <= 8:
        # Mali opseg — skeniraj sve, bez provjere da li uređaj "odgovara".
        # Host iza firewalla ume da ćuti na probna pitanja a da ima otvorene portove.
        zivi = [str(h) for h in hostovi]
        log(f"Mali opseg ({len(zivi)}) — skeniram sve adrese bez prethodne provjere")
    else:
        log(f"Tražim aktivne uređaje u {opis_opsega} ({len(hostovi)} adresa)")
        zivi = []
        with cf.ThreadPoolExecutor(max_workers=128) as ex:
            for ip, ok in zip(hostovi, ex.map(lambda h: _ziv(str(h)), hostovi)):
                if ok:
                    zivi.append(str(ip))
        log(f"Pronađeno {len(zivi)} aktivnih uređaja")

    uredjaji = []
    portovi = sorted(PORTOVI)
    with cf.ThreadPoolExecutor(max_workers=48) as ex:
        bud = {ex.submit(_skeniraj_host, ip, portovi): ip for ip in zivi}
        for f in cf.as_completed(bud):
            ip = bud[f]
            try:
                otv = f.result()
            except Exception:
                otv = []
            uredjaji.append({
                "ip": ip, "ime": _ime(ip),
                "portovi": [{"port": p, "servis": PORTOVI.get(p, "?")} for p in otv],
            })
            log(f"  {ip}  {len(otv)} otvorenih")

    # MAC se čita iz ARP tabele — skeniranje je upravo prošlo kroz nju
    arp = m_mak.tabela()
    for u in uredjaji:
        u["mac"] = arp.get(u["ip"], "")
        u["proizvodjac"], u["vrsta"] = m_mak.proizvodjac(u["mac"])

    uredjaji.sort(key=lambda u: tuple(int(x) for x in u["ip"].split(".")))
    sirovo = {"opseg": opis_opsega, "opsezi": [str(m) for m in mreze],
              "broj_uredjaja": len(uredjaji), "uredjaji": uredjaji}
    sirovo.update(dodatno)

    if not uredjaji:
        nalazi.append(nalaz(
            "Mreža", "Nijedan uređaj nije odgovorio", INFO,
            f"U opsegu {opis_opsega} nijedna adresa nije odgovorila.",
            preporuka="Provjeriti da li je računar na istoj mreži i da li firewall "
                      "blokira odlazne pokušaje povezivanja."))
        return {"nalazi": nalazi, "sirovo": sirovo}

    sa_mac = [u for u in uredjaji if u["mac"]]
    nalazi.append(nalaz(
        "Mreža", f"Popisano {len(uredjaji)} aktivnih uređaja", INFO,
        f"U opsegu {opis_opsega} odgovorilo je {len(uredjaji)} uređaja. "
        f"Za {len(sa_mac)} je očitana i MAC adresa."
        + ("" if len(sa_mac) == len(uredjaji) else
           " MAC se ne vidi za uređaje iza rutera — oni su u drugoj mreži."),
        preporuka="Uporediti spisak sa onim što zaposleni prepoznaju. Svaki uređaj "
                  "koji niko ne prepoznaje treba identifikovati. MAC adresa se ne "
                  "mijenja, pa po njoj uređaj prepoznaješ i na sljedećem pregledu.",
        tabela={"zaglavlje": ["IP adresa", "Ime", "MAC adresa", "Proizvođač",
                              "Otvoreni portovi"],
                "redovi": [[u["ip"], (u["ime"] or "—")[:26], u["mac"] or "—",
                            m_mak.opis(u["mac"]) if u["mac"] else "—",
                            ", ".join(str(p["port"]) for p in u["portovi"]) or "—"]
                           for u in uredjaji],
                "sirine": [16, 22, 20, 24, 18]},
        dokaz=[f'{u["ip"]:<16}{u["mac"] or "":<19}{u["ime"] or "(bez imena)":<24}'
               f'{", ".join(str(p["port"]) for p in u["portovi"]) or "-"}'
               for u in uredjaji]))

    # --- uređaji koje je sistem vidio, a nisu odgovorili na skeniranje ---
    # ARP tabela pamti svakog sa kim je mašina skoro komunicirala. Ako je
    # adresa tu, a skeniranje je nije našlo, uređaj postoji ali ćuti —
    # najčešće firewall koji odbija sve, uspavana mašina ili uređaj koji se
    # javio pa se ugasio.
    nadjene = {u["ip"] for u in uredjaji}
    u_opsegu = []
    for ip, mac in arp.items():
        if ip in nadjene:
            continue
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if any(a in m for m in mreze):
            u_opsegu.append((ip, mac))

    if u_opsegu:
        u_opsegu.sort(key=lambda x: tuple(int(y) for y in x[0].split(".")))
        sirovo["cute"] = [{"ip": i, "mac": m} for i, m in u_opsegu]
        nalazi.append(nalaz(
            "Mreža", f"Još {len(u_opsegu)} uređaja postoji ali nije odgovorilo",
            INFO,
            "Ove adrese stoje u ARP tabeli ove mašine — znači neko je na njima "
            "nedavno bio — ali na skeniranje nisu odgovorile: "
            + ", ".join(f"{i} ({m_mak.opis(m)})" for i, m in u_opsegu[:8])
            + (" …" if len(u_opsegu) > 8 else ""),
            "Uređaj koji ne odgovara nije nužno problem — češće je ugašen ili "
            "ima firewall koji odbija sve. Ali to znači da popis mreže nije "
            "potpun, pa ni izvještaj ne pokriva sve što firma ima.",
            "Provjeriti spisak dodijeljenih adresa na ruteru i uporediti ga sa "
            "ovim popisom. Uređaje koji nedostaju unijeti ručno ili ponoviti "
            "pregled kad budu uključeni.",
            tabela={"zaglavlje": ["IP adresa", "MAC adresa", "Proizvođač"],
                    "redovi": [[i, m, m_mak.opis(m)] for i, m in u_opsegu],
                    "sirine": [22, 26, 52]},
            dokaz=[f"{i}  {m}  {m_mak.opis(m)}" for i, m in u_opsegu]))

    # uređaj koji se ne može svrstati ni po imenu ni po proizvođaču
    neprepoznati = [u for u in uredjaji if u["mac"] and not u["proizvodjac"]
                    and not u["ime"]]
    if neprepoznati:
        nalazi.append(nalaz(
            "Mreža", f"{len(neprepoznati)} uređaja se ne može prepoznati", NIZAK,
            "Bez imena i bez poznatog proizvođača: "
            + ", ".join(f'{u["ip"]} ({u["mac"]})' for u in neprepoznati[:10]),
            "Uređaj na mreži koji se ne zna šta je, ne znači da je napadač — češće "
            "je privatni telefon, stari laptop ili nešto što je neko donio i "
            "zaboravio. Ali dok se ne utvrdi šta je, firma ima opremu na mreži o "
            "kojoj ne zna ništa.",
            "Proći kroz spisak sa nekim iz firme i identifikovati svaki uređaj. "
            "Ono što nije njihovo — isključiti sa mreže.",
            sati=0.5 * len(neprepoznati),
            dokaz=[f'{u["ip"]} — {u["mac"]} — '
                   + ("nasumična adresa" if m_mak.je_nasumican(u["mac"])
                      else "nepoznat proizvođač")
                   for u in neprepoznati]))

    # nesigurni protokoli
    for port, zasto in NESIGURNI.items():
        pogodjeni = [u["ip"] for u in uredjaji if any(p["port"] == port for p in u["portovi"])]
        if pogodjeni:
            nalazi.append(nalaz(
                "Mreža", f"Otvoren {PORTOVI.get(port, port)} na mreži", SREDNJI,
                f"Port {port} je otvoren na: " + ", ".join(pogodjeni),
                zasto + ".",
                f"Isključiti {PORTOVI.get(port, port)} na tim uređajima ili ih "
                "izdvojiti u zaseban mrežni segment ako se ne mogu isključiti.",
                sati=1, trosak=60, dokaz=[f"{ip}:{port} otvoren" for ip in pogodjeni]))

    # RDP unutar mreže — informativno, bitno je da li je izložen spolja
    rdp = [u["ip"] for u in uredjaji if any(p["port"] == 3389 for p in u["portovi"])]
    if rdp:
        nalazi.append(nalaz(
            "Mreža", "Udaljena radna površina je aktivna", NIZAK,
            "Port 3389 otvoren na: " + ", ".join(rdp),
            "Unutar mreže je uobičajeno. Problem nastaje ako je isti port "
            "dostupan i sa interneta — to je najčešći put ulaska ransomwarea.",
            "Provjeriti na ruteru da port 3389 nije proslijeđen prema internetu. "
            "Za rad od kuće koristiti VPN.",
            sati=0.5, dokaz=[f"{ip}:3389" for ip in rdp]))

    # uređaji sa web sučeljem bez HTTPS-a
    goli_web = [u["ip"] for u in uredjaji
                if any(p["port"] == 80 for p in u["portovi"])
                and not any(p["port"] == 443 for p in u["portovi"])]
    if len(goli_web) >= 2:
        nalazi.append(nalaz(
            "Mreža", "Uređaji sa nešifrovanim web sučeljem", NIZAK,
            "Samo HTTP, bez HTTPS: " + ", ".join(goli_web),
            "Obično su to štampači, kamere i mrežna oprema. Lozinka za prijavu "
            "na takav uređaj putuje mrežom u čitljivom obliku.",
            "Gdje uređaj podržava, uključiti HTTPS. Gdje ne podržava, izdvojiti "
            "ga u zaseban segment.",
            sati=1, dokaz=[f"{ip}:80" for ip in goli_web]))

    return {"nalazi": nalazi, "sirovo": sirovo}


def javna_izlozenost(log=lambda s: None):
    """Javna adresa firme + upozorenje da se izloženost mjeri izvana."""
    nalazi, sirovo = [], {}
    adresa = None
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip",
                "https://icanhazip.com"):
        try:
            import requests
            r = requests.get(url, timeout=6)
            if r.ok and r.text.strip():
                adresa = r.text.strip()
                break
        except Exception:
            continue
    sirovo["javna_ip"] = adresa
    if adresa:
        log(f"Javna adresa: {adresa}")
        nalazi.append(nalaz(
            "Mreža", "Javna adresa firme", INFO,
            f"Firma prema internetu izlazi sa adrese {adresa}.",
            preporuka="Izloženost se mjeri izvan mreže klijenta. Pokreni skeniranje "
                      "ove adrese sa svoje veze (nmap -Pn --top-ports 1000) i "
                      "provjeri je li 3389 ili 445 otvoren.",
            dokaz=[f"javna IP: {adresa}"]))
    return {"nalazi": nalazi, "sirovo": sirovo}


def izlozenost(javna_ip, log=lambda s: None):
    """Skenira javnu adresu klijenta — pokreće se SA SVOJE veze, ne iz njegove mreže.

    Iz klijentove mreže ruter često sam odgovori na vlastitu javnu adresu, pa
    rezultat ne znači ništa. Zato ovo ide kao zaseban korak, od kuće.
    """
    nalazi, sirovo = [], {"meta": javna_ip}
    meta = (javna_ip or "").strip()
    if not meta:
        return {"nalazi": nalazi, "sirovo": sirovo}

    try:
        meta = socket.gethostbyname(meta)
    except OSError:
        return {"nalazi": [nalaz("Mreža", "Javna adresa nije razriješena", INFO,
                                 f"Adresa {javna_ip} se ne može razriješiti.")],
                "sirovo": sirovo}

    log(f"Skeniram javnu adresu {meta}")
    portovi = sorted(set(PORTOVI) | set(OPASNO_SPOLJA))
    otvoreni = _skeniraj_host(meta, portovi, timeout=2.0)
    sirovo["otvoreni"] = [{"port": p, "servis": PORTOVI.get(p, "?")} for p in otvoreni]
    log(f"Otvoreno spolja: {otvoreni or 'ništa'}")

    opasni = [p for p in otvoreni if p in OPASNO_SPOLJA]
    ostali = [p for p in otvoreni if p not in OPASNO_SPOLJA]

    if opasni:
        imena = ", ".join(f"{OPASNO_SPOLJA[p]} (port {p})" for p in opasni)
        nalazi.append(nalaz(
            "Mreža", "Opasni servisi su dostupni sa interneta", VISOK,
            f"Na adresi {meta} otvoreno je: {imena}.",
            "Ovo nije teorijski rizik. Automatizovane skripte non-stop skeniraju "
            "internet tražeći upravo ove portove i odmah počinju pogađati lozinke. "
            "Izložena udaljena radna površina je i dalje najčešći način na koji "
            "ransomware uđe u malu firmu.",
            "Zatvoriti portove na ruteru i udaljeni pristup prebaciti na VPN sa "
            "dvofaktorskom zaštitom. Ako se port mora ostaviti, ograničiti ga na "
            "poznate adrese.",
            sati=3, trosak=180,
            dokaz=[f"{meta}:{p} otvoren — {OPASNO_SPOLJA[p]}" for p in opasni]))

    if ostali:
        nalazi.append(nalaz(
            "Mreža", "Servisi dostupni sa interneta", INFO,
            "Otvoreno: " + ", ".join(f"{p} ({PORTOVI.get(p, '?')})" for p in ostali),
            preporuka="Provjeriti da je svaki od ovih servisa namjerno otvoren i "
                      "da je ažuriran.",
            dokaz=[f"{meta}:{p} — {PORTOVI.get(p, '?')}" for p in ostali]))

    if not otvoreni:
        nalazi.append(nalaz(
            "Mreža", "Prema internetu nije otvoren nijedan provjereni port", DOBRO,
            f"Skenirano {len(portovi)} portova na adresi {meta} — svi su zatvoreni "
            f"ili filtrirani.",
            dokaz=[f"skenirano: {len(portovi)} portova"]))

    return {"nalazi": nalazi, "sirovo": sirovo}
