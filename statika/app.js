const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

const NAZIV = {visok:"VISOK", srednji:"SREDNJI", nizak:"NIZAK", info:"INFO", dobro:"U REDU"};
let ANKETA = null;

/* ---------- početno punjenje iz postavki ---------- */
(async () => {
  try {
    const p = await (await fetch("/api/postavke")).json();
    if (p.izvrsio) $("#izvrsio").placeholder = p.izvrsio;
    $("#dno-kontakt").textContent = p.kontakt || "";
  } catch (e) { /* bez postavki radi normalno */ }
})();

/* ---------- pitanja za razgovor ---------- */
function osvjeziBrojace(){
  $$(".grupa").forEach(g => {
    const uk = g.querySelectorAll(".pitanje").length;
    const od = [...g.querySelectorAll(".pitanje")]
      .filter(p => p.querySelector("input[type=radio]:checked")).length;
    const b = g.querySelector(".brojač");
    b.textContent = od + "/" + uk;
    b.classList.toggle("puno", od === uk && uk > 0);
  });
}

document.addEventListener("change", e => {
  if (e.target.type !== "radio" || !e.target.name.startsWith("q_")) return;
  e.target.closest(".pitanje").classList.add("odgovoreno");
  osvjeziBrojace();
});

function skupiOdgovore(){
  const odgovori = {}, biljeske = {};
  $$(".pitanje").forEach(p => {
    const id = p.dataset.id;
    const r = p.querySelector("input[type=radio]:checked");
    if (!r) return;
    odgovori[id] = r.value;
    const b = p.querySelector(".biljeska").value.trim();
    if (b) biljeske[id] = b;
  });
  return {odgovori, biljeske};
}

/* ---------- pokretanje ---------- */
$("#saglasan").addEventListener("change", e => {
  $("#btn-start").disabled = !e.target.checked;
});

$("#btn-start").addEventListener("click", async () => {
  const provjere = $$(".grupa-provjera input[type=checkbox]:checked").map(i => i.value);
  if (!provjere.length) { alert("Izaberi bar jednu provjeru."); return; }

  const podaci = {
    firma:    $("#firma").value.trim(),
    regija:      $("#regija").value.trim(),
    lokacija:    $("#lokacija").value.trim(),
    podlokacija: $("#podlokacija").value.trim(),
    napomena:    $("#napomena").value.trim(),
    domena:   $("#domena").value.trim(),
    sajt:     $("#sajt").value.trim(),
    dkim_selektor: $("#dkim_selektor").value.trim(),
    adrese:   $("#adrese").value.trim(),
    opseg:    $("#opseg").value.trim(),
    domen_ad: $("#domen_ad").value.trim(),
    izvrsio:  $("#izvrsio").value.trim(),
    kontakt_osoba: $("#kontakt_osoba").value.trim(),
    javna_ip: $("#javna_ip").value.trim(),
    kontakt: $("#kontakt").value.trim(),
    ad_korisnik: $("#ad_korisnik").value.trim(),
    ad_lozinka: $("#ad_lozinka").value,
    provjere,
    ...skupiOdgovore()
  };
  if (!podaci.firma) { alert("Upiši naziv firme — ide na izvještaj."); return; }

  const r = await fetch("/api/pokreni", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify(podaci)
  });
  if (!r.ok) { alert((await r.json()).greska || "Greška."); return; }

  $("#prazno").classList.add("sakrij");
  $("#rezultat").classList.add("sakrij");
  $("#tok").classList.remove("sakrij");
  $("#btn-start").disabled = true;
  $("#btn-start").textContent = "Pregled u toku…";
  ANKETA = setInterval(osvjezi, 900);
  osvjezi();
});

/* ---------- osvježavanje stanja ---------- */
async function osvjezi() {
  const s = await (await fetch("/api/stanje")).json();

  $("#traka").style.width = s.napredak + "%";
  $("#posto").textContent = s.napredak + "%";
  $("#korak").textContent = s.korak || "Radim…";
  const d = $("#dnevnik");
  const dole = d.scrollTop + d.clientHeight >= d.scrollHeight - 30;
  d.textContent = s.dnevnik.join("\n");
  if (dole) d.scrollTop = d.scrollHeight;

  if (s.gotovo) {
    clearInterval(ANKETA);
    prikaziRezultat(s);
    $("#btn-start").disabled = false;
    $("#btn-start").textContent = "Pokreni pregled";
  }
}

/* ---------- rezultat ---------- */
function prikaziRezultat(s) {
  $("#rezultat").classList.remove("sakrij");
  $("#prazno").classList.add("sakrij");

  const g = $("#greske");
  if (s.greske && s.greske.length) {
    g.classList.remove("sakrij");
    g.innerHTML = "<b>Nešto nije prošlo</b>"
      + "<ul>" + s.greske.map(x => `<li>${esc(x)}</li>`).join("") + "</ul>"
      + "<i>Ostale provjere su izvršene i izvještaj je napravljen od njih.</i>";
  } else {
    g.classList.add("sakrij");
  }

  const mj = s.ocjena.mjerljivo !== false;
  $("#bodovi").textContent = mj ? s.ocjena.bodovi : "—";
  $("#nivo").textContent = s.ocjena.nivo;
  $("#nivo-opis").textContent = s.ocjena.opis;
  $(".bodovi small").style.display = mj ? "" : "none";

  // dnevnik se skupi kad pregled završi — rezultat je sad bitniji
  $("#dnevnik").classList.add("skupljen");

  const broj = t => s.nalazi.filter(n => n.tezina === t).length;
  $("#br-visok").textContent   = broj("visok");
  $("#br-srednji").textContent = broj("srednji");
  $("#br-nizak").textContent   = broj("nizak");
  $("#br-dobro").textContent   = broj("dobro");

  if (s.sazetak) {
    $("#btn-sazetak").href = "/preuzmi/" + encodeURIComponent(s.sazetak);
    $("#btn-sazetak").style.display = "";
  } else {
    $("#btn-sazetak").style.display = "none";
  }

  if (s.pdf) {
    $("#btn-pdf").href = "/preuzmi/" + encodeURIComponent(s.pdf);
    $("#btn-pdf").style.display = "";
  } else {
    $("#btn-pdf").style.display = "none";
  }

  $("#pojas-ponovo").classList.toggle("sakrij", !s.treba_izvjestaj);

  $("#nalazi").innerHTML = s.nalazi.map((n, i) => {
    const dijelovi = [];
    if (n.utvrdjeno) dijelovi.push(`<p><b>Šta je utvrđeno:</b> ${esc(n.utvrdjeno)}</p>`);
    if (n.rizik)     dijelovi.push(`<p><b>Zašto je to rizik:</b> ${esc(n.rizik)}</p>`);
    if (n.preporuka) dijelovi.push(`<p><b>Preporuka:</b> ${esc(n.preporuka)}</p>`);
    const pr = [];
    if (n.sati)   pr.push(n.sati + " h rada");
    if (n.trosak) pr.push("oko " + n.trosak + " KM");
    if (pr.length) dijelovi.push(`<p><b>Procjena:</b> ${pr.join(" · ")}</p>`);

    if (n.komentar)
      dijelovi.push(`<p class="komentar"><b>Napomena tehničara:</b> ${esc(n.komentar)}</p>`);
    if (n.izvorno) {
      const im = {sati:"sati", trosak:"trošak (KM)", tezina:"težina"};
      dijelovi.push('<p class="izvorno"><b>Ispravljeno:</b> '
        + Object.keys(n.izvorno).map(k =>
            `${im[k] || k}: ${n.izvorno[k] === null ? "—" : esc(n.izvorno[k])} → ${esc(n[k])}`)
          .join(" · ") + "</p>");
    }
    if (n.dokaz && n.dokaz.length)
      dijelovi.push(`<pre>${esc(n.dokaz.join("\n"))}</pre>`);

    dijelovi.push(`
      <div class="ispravka" data-indeks="${i}">
        <b class="zag-ispravke">Ispravi procjenu i dodaj stručni komentar</b>
        <div class="tri">
          <label>Sati
            <input class="i-sati" value="${n.sati == null ? "" : esc(n.sati)}" placeholder="—"></label>
          <label>Trošak (KM)
            <input class="i-trosak" value="${n.trosak == null ? "" : esc(n.trosak)}" placeholder="—"></label>
          <label>Težina
            <select class="i-tezina">
              ${["visok","srednji","nizak","info","dobro"].map(t =>
                `<option value="${t}"${t === n.tezina ? " selected" : ""}>${NAZIV[t]}</option>`).join("")}
            </select></label>
        </div>
        <label>Stručni komentar <span class="nag">ide u izvještaj uz nalaz</span>
          <textarea class="i-komentar" rows="2" placeholder="zašto je procjena drugačija — šta si zatekao na licu mjesta">${esc(n.komentar || "")}</textarea></label>
        <button class="tiho i-snimi">Snimi ispravku</button>
        <span class="i-stanje"></span>
      </div>`);

    return `<details class="nalaz ${n.tezina}${n.izmijenjeno ? " izmijenjen" : ""}${n.rucni ? " rucni" : ""}">
      <summary>
        <span class="naslov">${esc(n.naslov)}<span class="oblast">${esc(n.oblast)}${
          n.rucni ? ' · <i class="oznaka">ručni unos</i>' : ""}${
          n.izmijenjeno ? ' · <i class="oznaka">ispravljeno</i>' : ""}</span></span>
        <span class="znacka ${n.tezina}">${NAZIV[n.tezina] || n.tezina}</span>
      </summary>
      <div class="tijelo">${dijelovi.join("")}</div>
    </details>`;
  }).join("");
}

/* ---------- ispravka procjene ---------- */
document.addEventListener("click", async e => {
  const b = e.target.closest(".i-snimi");
  if (!b) return;
  const box = b.closest(".ispravka");
  const stanje = box.querySelector(".i-stanje");
  stanje.textContent = "snimam…";
  stanje.className = "i-stanje";
  const r = await fetch("/api/izmijeni", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      indeks:   parseInt(box.dataset.indeks, 10),
      sati:     box.querySelector(".i-sati").value.trim(),
      trosak:   box.querySelector(".i-trosak").value.trim(),
      tezina:   box.querySelector(".i-tezina").value,
      komentar: box.querySelector(".i-komentar").value.trim()
    })
  });
  const o = await r.json();
  if (!o.ok) { stanje.textContent = o.greska || "Nije snimljeno."; stanje.classList.add("loše"); return; }
  if (!o.promjena) { stanje.textContent = "Ništa se nije promijenilo."; return; }
  const s = await (await fetch("/api/stanje")).json();
  prikaziRezultat(s);
  obavijesti("Ispravka je snimljena.",
    "<small>Ostalo je još da se izvještaj napravi ponovo — dugme je ispod ocjene.</small>");
}, false);

/* ---------- ponovno pravljenje izvještaja ---------- */
$("#btn-ponovo").addEventListener("click", async () => {
  const b = $("#btn-ponovo");
  b.disabled = true; b.textContent = "Pravim…";
  const r = await fetch("/api/izvjestaj-ponovo", {method: "POST"});
  const o = await r.json();
  b.disabled = false; b.textContent = "Napravi izvještaj ponovo";
  if (!o.ok) { obavijesti("Izvještaj nije napravljen.", `<small>${esc(o.greska || "")}</small>`, true); return; }
  prikaziRezultat(await (await fetch("/api/stanje")).json());
  obavijesti("Izvještaj je napravljen ponovo.",
    "<small>Oba PDF-a su prepisana sa ispravkama. Preuzmi ih dugmadima iznad — "
    + "stari fajl je zamijenjen, pa pazi ako si ga već poslao klijentu."
    + `<br>${esc(o.pdf || "")}${o.sazetak ? " · " + esc(o.sazetak) : ""}</small>`);
});

/* ---------- ručni unos uređaja ---------- */
(async () => {
  try {
    const v = await (await fetch("/api/vrste-uredjaja")).json();
    $("#u-vrsta").innerHTML = v.vrste.map(x => `<option>${esc(x)}</option>`).join("");
    $("#u-stanje").innerHTML = v.stanja.map(x =>
      `<option value="${esc(x.kljuc)}">${esc(x.opis)}</option>`).join("");
  } catch (e) { /* popunjava se pri prvom pregledu */ }
})();

$("#btn-uredjaj").addEventListener("click", async () => {
  const u = {};
  for (const k of ["vrsta","naziv","proizvodjac","model","serijski","ip",
                   "lokacija","starost","stanje","sati","trosak","napomena"])
    u[k] = $("#u-" + k).value.trim();
  if (!u.naziv) { alert("Upiši naziv ili oznaku uređaja — po tome se prepoznaje u izvještaju."); return; }

  const r = await fetch("/api/uredjaj", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(u)
  });
  const o = await r.json();
  if (!o.ok) { alert(o.greska || "Greška."); return; }
  for (const k of ["naziv","proizvodjac","model","serijski","ip","starost",
                   "sati","trosak","napomena"]) $("#u-" + k).value = "";
  prikaziRezultat(await (await fetch("/api/stanje")).json());
  obavijesti(`Uređaj „${u.naziv}" je dodan u izvještaj.`,
    "<small>Ušao je u spisak nalaza, označen kao ručni unos. "
    + "Da uđe i u PDF, pritisni <b>Napravi izvještaj ponovo</b>.</small>");
});

/* ---------- zapisi ---------- */
$("#btn-zapisi").addEventListener("click", async () => {
  const el = $("#zapisi");
  if (!el.classList.contains("sakrij")) {
    el.classList.add("sakrij");
    $("#btn-zapisi").textContent = "Prikaži zapise";
    return;
  }
  const lista = await (await fetch("/api/zapisi")).json();
  el.innerHTML = lista.length
    ? lista.map(z => `<div class="zapis ${esc(z.vrsta)}">
        <span class="kad">${esc((z.vrijeme || "").replace("T", " ").slice(0, 19))}</span>
        <span class="sta"><b>${esc(z.opis)}</b>${z.sazetak ? " — " + esc(z.sazetak) : ""}</span>
        <span class="ko">${esc(z.tehnicar || "")}</span>
      </div>`).join("")
    : '<p class="nag">Još nema zapisa.</p>';
  el.classList.remove("sakrij");
  $("#btn-zapisi").textContent = "Sakrij zapise";
});

/* ---------- obavijest o uspjehu ---------- */
let SAT_OBAVIJESTI = null;
function obavijesti(naslov, tijelo, lose) {
  const el = $("#obavijest");
  el.className = "obavijest" + (lose ? " loše" : "");
  el.innerHTML = `<span><b>${esc(naslov)}</b>${tijelo || ""}</span>`
    + `<button class="zatvori" title="Zatvori">×</button>`;
  el.querySelector(".zatvori").onclick = () => el.classList.add("sakrij");
  el.scrollIntoView({behavior: "smooth", block: "center"});
  clearTimeout(SAT_OBAVIJESTI);
  SAT_OBAVIJESTI = setTimeout(() => el.classList.add("sakrij"), 12000);
}

function esc(t) {
  return String(t).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
}

/* ---------- dugmad ---------- */
$("#btn-folder").addEventListener("click", () => fetch("/api/otvori-folder", {method:"POST"}));
$("#btn-novo").addEventListener("click", () => location.reload());

/* ---------- postavke ---------- */
$("#btn-postavke").addEventListener("click", async () => {
  const p = await (await fetch("/api/postavke")).json();
  $("#p-izvrsio").value = p.izvrsio || "";
  $("#p-kontakt").value = p.kontakt || "";
  $("#p-kljuc").placeholder = p.ima_kljuc
    ? "ključ je snimljen — ostavi prazno da ostane isti"
    : "nije unesen";
  $("#p-azur-url").value = p.azuriranje_url || "";
  $("#p-azur-auto").checked = p.azuriranje_automatski !== false;
  $("#p-shodan").placeholder = p.ima_shodan
    ? "ključ je snimljen — ostavi prazno da ostane isti"
    : "nije unesen — koristi se besplatni InternetDB";
  $("#dlg-postavke").showModal();
});

$("#dlg-postavke").addEventListener("close", async e => {
  if ($("#dlg-postavke").returnValue !== "snimi") return;
  const telo = {
    izvrsio: $("#p-izvrsio").value.trim(),
    kontakt: $("#p-kontakt").value.trim()
  };
  telo.hibp_razmak = parseFloat($("#p-razmak").value);
  telo.azuriranje_url = $("#p-azur-url").value.trim();
  telo.azuriranje_automatski = $("#p-azur-auto").checked;
  const k = $("#p-kljuc").value.trim();
  if (k) telo.hibp_kljuc = k;
  const sk = $("#p-shodan").value.trim();
  if (sk) telo.shodan_kljuc = sk;
  await fetch("/api/postavke", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify(telo)
  });
  $("#p-kljuc").value = "";
  $("#p-shodan").value = "";
  if (k || sk) location.reload();
});


/* ---------- zbirni izvještaj ---------- */
async function ucitajPreglede() {
  const lista = await (await fetch("/api/pregledi")).json();
  const el = $("#pregledi");
  if (!lista.length) {
    el.innerHTML = '<p class="nag">Još nema snimljenih pregleda.</p>';
    return;
  }
  el.innerHTML = lista.map(p => `
    <label class="pregled">
      <input type="checkbox" value="${esc(p.folder)}">
      <span>
        <b>${esc(p.masina || p.firma || p.folder)}</b>
        <em>${esc(p.firma)} · ${esc(p.datum)} · ${p.nalaza} nalaza</em>
        <i>${esc(p.obim)}</i>
      </span>
    </label>`).join("");
  el.querySelectorAll("input").forEach(i =>
    i.addEventListener("change", () => {
      const n = el.querySelectorAll("input:checked").length;
      $("#btn-spoji").disabled = n < 2;
      $("#btn-spoji").textContent = n > 1
        ? `Napravi zbirni izvještaj (${n} pregleda)`
        : "Napravi zbirni izvještaj";
    }));
}

$("#btn-osvjezi").addEventListener("click", ucitajPreglede);
ucitajPreglede();

$("#btn-spoji").addEventListener("click", async () => {
  const folderi = [...$("#pregledi").querySelectorAll("input:checked")]
    .map(i => i.value);
  const r = await fetch("/api/spoji", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({folderi})
  });
  const o = await r.json();
  if (!o.ok) {
    obavijesti("Zbirni izvještaj nije napravljen.",
      `<small>${esc(o.greska || "")}</small>`, true);
    return;
  }
  $("#prazno").classList.add("sakrij");
  $("#tok").classList.add("sakrij");
  await osvjezi();
  obavijesti(`Zbirni izvještaj je napravljen — ${o.masina} mašina, ${o.nalaza} nalaza.`,
    `<small>Mašine: ${esc((o.masine || []).map(m => m.masina || m.firma || "?").join(", "))}.<br>`
    + `Folder: <b>rezultati\\${esc(o.folder)}</b> — preuzmi PDF dugmadima iznad, `
    + `ili otvori folder.</small>`);
  ucitajPreglede();
});

/* ---------- uvoz pregleda sa druge mašine ---------- */
function uvozPoruka(o, kakoJe) {
  const el = $("#uvoz-poruka");
  el.classList.remove("sakrij", "loše");
  if (!o.ok) {
    el.classList.add("loše");
    el.innerHTML = `<b>Nije uvezeno.</b> ${esc(o.greska || "Nepoznata greška.")}`;
    return;
  }
  const red = o.uvezeno.map(u =>
    `<li>${esc(u.masina || u.firma || u.folder)} — ${esc(u.firma)}${
      u.datum ? " · " + esc(u.datum) : ""} · ${u.nalaza} nalaza</li>`).join("");
  el.innerHTML = `<b>Uvezeno ${o.uvezeno.length} pregleda</b> (${esc(kakoJe)})`
    + `<ul>${red}</ul>`
    + (o.duplikata ? `<i>${o.duplikata} pregleda je već bilo u spisku, preskočeni su.</i>` : "")
    + (o.greske && o.greske.length ? `<i>${esc(o.greske.join("; "))}</i>` : "");
  ucitajPreglede();
}

$("#btn-uvoz-fajl").addEventListener("click", async () => {
  const f = $("#uvoz-fajl").files[0];
  if (!f) { alert("Prvo izaberi nalazi.json ili zip pregleda."); return; }
  const telo = new FormData();
  telo.append("fajl", f);
  const b = $("#btn-uvoz-fajl");
  b.disabled = true; b.textContent = "Uvozim…";
  try {
    const r = await fetch("/api/uvezi-fajl", {method: "POST", body: telo});
    uvozPoruka(await r.json(), f.name);
    $("#uvoz-fajl").value = "";
  } finally {
    b.disabled = false; b.textContent = "Uvezi izabrani fajl";
  }
});

$("#btn-uvoz-putanja").addEventListener("click", async () => {
  const p = $("#uvoz-putanja").value.trim();
  if (!p) { alert("Upiši putanju do foldera sa pregledima."); return; }
  const b = $("#btn-uvoz-putanja");
  b.disabled = true; b.textContent = "Uvozim…";
  try {
    const r = await fetch("/api/uvezi-putanju", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({putanja: p})
    });
    uvozPoruka(await r.json(), p);
  } finally {
    b.disabled = false; b.textContent = "Uvezi sa putanje";
  }
});

$("#uvoz-putanja").addEventListener("keydown", e => {
  if (e.key === "Enter") $("#btn-uvoz-putanja").click();
});

/* ---------- nova verzija alata ---------- */
async function provjeriVerziju(rucno) {
  let v;
  try {
    v = await (await fetch("/api/verzija" + (rucno ? "?sam=1" : ""))).json();
  } catch (e) { return; }

  $("#dno-verzija").textContent = "KestrelScan " + (v.moja || "");
  const el = $("#pojas-verzija");

  if (!v.ima_novu) {
    el.classList.add("sakrij");
    if (rucno) {
      obavijesti(v.greska ? "Provjera ažuriranja nije uspjela."
                          : `Imaš najnoviju verziju (${esc(v.moja)}).`,
                 v.greska ? `<small>${esc(v.greska)}</small>` : "", !!v.greska);
    }
    return;
  }

  el.classList.remove("sakrij");
  el.innerHTML = `
    <span>
      <b>Dostupna je verzija ${esc(v.verzija)}</b>
      — ti imaš ${esc(v.moja)}${v.datum ? ", objavljeno " + esc(String(v.datum).replace(/\.+$/, "")) : ""}.
      ${v.promjene && v.promjene.length
        ? "<ul>" + v.promjene.map(x => `<li>${esc(x)}</li>`).join("") + "</ul>" : ""}
    </span>
    <span class="dugmad">
      <button id="btn-azuriraj" class="glavno">Ugradi sad</button>
      <button id="btn-kasnije" class="tiho">Kasnije</button>
    </span>`;

  $("#btn-kasnije").onclick = () => el.classList.add("sakrij");
  $("#btn-azuriraj").onclick = async () => {
    const b = $("#btn-azuriraj");
    b.disabled = true; b.textContent = "Ugrađujem…";
    let o;
    try {
      o = await (await fetch("/api/azuriraj", {method: "POST"})).json();
    } catch (e) {
      o = {ok: false, greska: String(e)};
    }
    b.disabled = false; b.textContent = "Ugradi sad";
    if (!o.ok) {
      obavijesti("Ažuriranje nije uspjelo.", `<small>${esc(o.greska || "")}</small>`, true);
      return;
    }
    el.classList.add("sakrij");
    obavijesti(`Ugrađena je verzija ${esc(o.verzija || "")}.`,
      `<small>${esc(o.poruka || "")}</small>`);
  };
}

$("#veza-provjeri").addEventListener("click", e => {
  e.preventDefault();
  provjeriVerziju(true);
});
provjeriVerziju(false);
