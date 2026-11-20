/* Accessible client-side catalog enhancement; original Markdown remains as a no-JS fallback. */
(function () {
  "use strict";

  const subjectInfo = {
    "jezyk-polski": { name: "Język polski", short: "PL", order: 0 },
    "matematyka": { name: "Matematyka", short: "MAT", order: 1 },
    "jezyk-angielski": { name: "Język angielski", short: "EN", order: 2 }
  };
  const subjectSlugs = {
    "Język polski": "jezyk-polski",
    "Matematyka": "matematyka",
    "Język angielski": "jezyk-angielski"
  };
  const months = {
    styczen: "Styczeń", luty: "Luty", marzec: "Marzec", kwiecien: "Kwiecień",
    maj: "Maj", czerwiec: "Czerwiec", lipiec: "Lipiec", sierpien: "Sierpień",
    wrzesien: "Wrzesień", pazdziernik: "Październik", listopad: "Listopad", grudzien: "Grudzień"
  };
  const clean = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ł/g, "l").trim();
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function readCatalog(article) {
    const grouped = new Map();
    let activeSubject = "";
    for (const node of Array.from(article.children)) {
      if (node.tagName === "H2") {
        activeSubject = subjectSlugs[node.textContent.trim()] || "";
        continue;
      }
      if (node.tagName !== "DETAILS" || !activeSubject) continue;
      const year = (node.querySelector("summary")?.textContent || "").trim();
      if (!/^20\d{2}$/.test(year)) continue;

      for (const link of node.querySelectorAll("li > a[href$='.pdf']")) {
        const href = link.href;
        const filename = decodeURIComponent(new URL(href).pathname.split("/").pop() || "");
        let stem = filename.replace(/\.pdf$/i, "");
        let kind = "exam";
        if (stem.endsWith("-odpowiedzi")) {
          kind = "answers";
          stem = stem.slice(0, -"-odpowiedzi".length);
        } else if (stem.endsWith("-transkrypcja")) {
          kind = "transcript";
          stem = stem.slice(0, -"-transkrypcja".length);
        }
        const key = [activeSubject, year, stem].join("|");
        let record = grouped.get(key);
        if (!record) {
          const core = stem.replace(new RegExp("^" + activeSubject + "-" + year + "-"), "");
          const first = core.split("-")[0];
          const month = months[first] || "";
          const type = core.includes("probny") ? "probny" : core.includes("dodatkowy") ? "dodatkowy" : "glowny";
          const title = type === "probny" ? "Egzamin próbny" : type === "dodatkowy" ? "Termin dodatkowy" : "Egzamin główny";
          record = {
            subject: activeSubject, year: Number(year), core, type, title, month,
            links: {}, monthSort: Object.keys(months).indexOf(first)
          };
          grouped.set(key, record);
        }
        record.links[kind] = href;
      }
    }
    return Array.from(grouped.values()).sort((a,b) =>
      b.year-a.year || subjectInfo[a.subject].order-subjectInfo[b.subject].order ||
      ({glowny:0,probny:1,dodatkowy:2}[a.type]-{glowny:0,probny:1,dodatkowy:2}[b.type]) ||
      (a.monthSort-b.monthSort) || a.core.localeCompare(b.core)
    );
  }

  function renderCard(record) {
    const info = subjectInfo[record.subject];
    const card = el("article", "e8-exam-card");
    card.dataset.subject = record.subject;

    const head = el("div", "e8-card-meta");
    const subject = el("span", "e8-card-subject");
    subject.append(el("span", "e8-card-avatar", info.short), document.createTextNode(info.name));
    head.append(subject, el("span", "e8-card-year", String(record.year)));
    card.append(head);

    const content = el("div", "");
    content.append(el("span", "e8-card-type",
      record.type === "probny" ? "Arkusz próbny" : record.type === "dodatkowy" ? "Sesja dodatkowa" : "Sesja główna"
    ));
    content.append(el("h3", "", record.title));
    content.append(el("p", "", record.month ? record.month + " " + record.year : "Rok " + record.year));
    card.append(content);

    const links = el("div", "e8-card-links");
    const makeLink = (href, label, primary) => {
      if (!href) return;
      const a = el("a", "e8-file-link" + (primary ? " e8-file-link--main" : ""), label);
      a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
      a.setAttribute("aria-label", label + " — " + info.name + ", " + record.title + " " + record.year);
      links.append(a);
    };
    makeLink(record.links.exam, "Arkusz PDF ↗", true);
    makeLink(record.links.answers, "Odpowiedzi ↗", false);
    makeLink(record.links.transcript, "Transkrypcja ↗", false);
    // Show links only to pages that exist; Polish is an edition,
    // English 2026 is a clearly labelled educational pilot with TTS.
    if (record.year === 2026 && record.links.exam && record.links.answers) {
      const fileName = decodeURIComponent(new URL(record.links.exam).pathname.split("/").pop() || "");
      const stem = fileName.replace(/\.pdf$/i, "");
      const published = {
        "jezyk-polski-2026-egzamin-osmoklasisty": {
          url:"../opracowania/polski-2026/",
          title:"Czytaj opracowanie →",
          aria:"Pełne opracowanie HTML — język polski, egzamin główny 2026"
        },
        "matematyka-2026-egzamin-osmoklasisty": {
          url:"../opracowania/matematyka-2026/",
          title:"Czytaj rozwiązania →",
          aria:"Pełne rozwiązania HTML krok po kroku — matematyka 2026"
        },
        "jezyk-angielski-2026-egzamin-osmoklasisty": {
          url:"../opracowania/angielski-2026/",
          title:"Czytaj i odsłuchaj →",
          aria:"Pilotażowe opracowanie HTML z odsłuchem — język angielski 2026"
        }
      }[stem];
      if (published) {
        const a = el("a", "e8-file-link e8-file-link-study", published.title);
        a.href = new URL(published.url, location.href).href;
        a.setAttribute("aria-label", published.aria);
        links.append(a);
      }
    }
    card.append(links);
    return card;
  }

  function enhanceCatalog(article) {
    const records = readCatalog(article);
    if (!records.length) return;
    const paramSubject = new URLSearchParams(location.search).get("subject");
    const state = {
      subject: subjectInfo[paramSubject] ? paramSubject : "all",
      year: "all", type: "all", query: "", showAll: false
    };
    const years = [...new Set(records.map(item => item.year))].sort((a,b) => b-a);
    const fileCount = records.reduce((sum, item) => sum + Object.keys(item.links).length, 0);
    const source = el("div", "e8-catalog-source");
    while (article.firstChild) source.appendChild(article.firstChild);

    const root = el("div", "e8-catalog-root");
    root.innerHTML = [
      '<section class="e8-catalog-hero" aria-labelledby="e8-catalog-heading">',
      '  <div><span class="e8-kicker">Biblioteka egzaminacyjna</span>',
      '    <h1 id="e8-catalog-heading">Wszystkie arkusze.<br>Jedno miejsce.</h1>',
      '    <p>Wybierz przedmiot, rok i termin. Otwieraj arkusze, klucze odpowiedzi oraz transkrypcje bez przekopywania się przez listy plików.</p></div>',
      '  <div class="e8-catalog-count"><strong id="e8-total-exams"></strong><span>zestawów egzaminacyjnych</span></div>',
      '</section>',
      '<section class="e8-toolbar" aria-label="Filtry arkuszy">',
      ' <div class="e8-toolbar-row">',
      '  <div class="e8-filters" role="group" aria-label="Przedmiot">',
      '   <button type="button" class="e8-chip" data-filter-subject="all">Wszystkie</button>',
      '   <button type="button" class="e8-chip" data-filter-subject="jezyk-polski">Język polski</button>',
      '   <button type="button" class="e8-chip" data-filter-subject="matematyka">Matematyka</button>',
      '   <button type="button" class="e8-chip" data-filter-subject="jezyk-angielski">Angielski</button>',
      '  </div>',
      '  <div class="e8-toolbar-fields">',
      '   <label><span class="visually-hidden">Rok</span><select class="e8-select" id="e8-year"><option value="all">Wszystkie lata</option></select></label>',
      '   <label><span class="visually-hidden">Termin</span><select class="e8-select" id="e8-type"><option value="all">Wszystkie terminy</option><option value="glowny">Główny</option><option value="probny">Próbny</option><option value="dodatkowy">Dodatkowy</option></select></label>',
      '   <label><span class="visually-hidden">Szukaj arkuszy</span><input class="e8-input" id="e8-search" type="search" placeholder="Szukaj, np. maj 2025..." autocomplete="off"></label>',
      '  </div>',
      ' </div>',
      ' <div class="e8-toolbar-foot"><span id="e8-result-count" aria-live="polite"></span><span id="e8-file-count"></span></div>',
      '</section>',
      '<div id="e8-results"></div>',
      '<p class="e8-smallprint">Pliki PDF są otwierane bezpośrednio z repozytorium Egzamin_8K_JP.</p>'
    ].join("\n");
    article.append(root, source);
    document.body.classList.add("e8-catalog-page");

    root.querySelector("#e8-total-exams").textContent = String(records.length);
    root.querySelector("#e8-file-count").textContent = fileCount + " plików PDF · " + years.length + " roczników";
    const yearSelect = root.querySelector("#e8-year");
    years.forEach(year => { const option = el("option", "", String(year)); option.value = String(year); yearSelect.append(option); });
    const resultNode = root.querySelector("#e8-results");
    const chips = Array.from(root.querySelectorAll("[data-filter-subject]"));
    // Keep the top navigation and catalog headline consistent with the filter.
    function syncSubjectNavigation() {
      const navs = document.querySelectorAll(".md-tabs__item, .md-nav--primary > .md-nav__list > .md-nav__item");
      for (const item of navs) {
        // Data attributes are present on the live navigation. After a
        // full MkDocs rebuild the same links are rendered without them.
        const link = item.querySelector("a[data-e8-menu], a.md-tabs__link, a.md-nav__link");
        if (!link) continue;
        let target = link.getAttribute("data-e8-menu");
        if (!target) {
          const href = new URL(link.href, location.href);
          if (href.pathname.endsWith("/pdfs/")) target = href.searchParams.get("subject") || "arkusze";
          else if (href.pathname.endsWith("/Egzamin_8K_JP/")) target = "start";
        }
        const desired = state.subject === "all" ? "arkusze" : state.subject;
        const active = target === desired;
        item.classList.toggle("md-tabs__item--active", active && item.classList.contains("md-tabs__item"));
        item.classList.toggle("md-nav__item--active", active && item.classList.contains("md-nav__item"));
        link.classList.toggle("md-nav__link--active", active && link.classList.contains("md-nav__link"));
        if (active) link.setAttribute("aria-current","page");
        else link.removeAttribute("aria-current");
      }
      const name = state.subject === "all" ? "Wszystkie arkusze" : "Arkusze · " + subjectInfo[state.subject].name;
      root.querySelector("#e8-catalog-heading").textContent = name;
      const description = state.subject === "all"
        ? "Wybierz przedmiot, rok i termin. Każdy egzamin ma swój kafelek z arkuszem i odpowiedziami."
        : "Wybierz rocznik i termin. Otwórz odpowiedni kafelek, aby przejść do arkusza, odpowiedzi lub dostępnego opracowania.";
      root.querySelector(".e8-catalog-hero p").textContent = description;
    }


    function render() {
      syncSubjectNavigation();
      for (const button of chips) {
        const active = button.dataset.filterSubject === state.subject;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      }
      const q = clean(state.query);
      const filtered = records.filter(record => {
        if (state.subject !== "all" && record.subject !== state.subject) return false;
        if (state.year !== "all" && String(record.year) !== state.year) return false;
        if (state.type !== "all" && record.type !== state.type) return false;
        const haystack = clean([
          subjectInfo[record.subject].name, record.year, record.title, record.core,
          record.month, record.type, "egzamin osmoklasisty"
        ].join(" "));
        return !q || q.split(/\s+/).every(word => haystack.includes(word));
      });
      const filteredActive = state.subject !== "all" || state.year !== "all" || state.type !== "all" || q !== "";
      const shown = filteredActive || state.showAll ? filtered : filtered.slice(0,18);
      root.querySelector("#e8-result-count").textContent =
        "Znaleziono " + filtered.length + " zestawów" +
        (shown.length < filtered.length ? " · wyświetlono " + shown.length : "");
      resultNode.replaceChildren();

      if (!filtered.length) {
        const empty = el("div", "e8-empty");
        empty.append(el("strong", "", "Brak arkuszy dla wybranych filtrów"));
        empty.append(el("p", "", "Zmień rok, przedmiot, termin lub wpisaną frazę."));
        resultNode.append(empty);
        return;
      }

      const byYear = new Map();
      shown.forEach(record => {
        if (!byYear.has(record.year)) byYear.set(record.year, []);
        byYear.get(record.year).push(record);
      });
      for (const [year, items] of byYear) {
        const heading = el("div", "e8-list-title");
        heading.append(el("h2", "", String(year)), el("span", "", items.length + " zestawów"));
        resultNode.append(heading);
        const grid = el("div", "e8-card-grid");
        items.forEach(record => grid.append(renderCard(record)));
        resultNode.append(grid);
      }

      if (shown.length < filtered.length) {
        const row = el("div", "e8-actions");
        row.style.justifyContent = "center";
        row.style.margin = "1.8rem 0 2rem";
        const btn = el("button", "e8-chip is-active", "Pokaż pozostałe " + (filtered.length - shown.length) + " zestawy");
        btn.type = "button";
        btn.addEventListener("click", () => { state.showAll = true; render(); });
        row.append(btn);
        resultNode.append(row);
      }
    }

    chips.forEach(button => button.addEventListener("click", () => {
      state.subject = button.dataset.filterSubject;
      state.showAll = false;
      render();
      const url = new URL(location.href);
      if (state.subject === "all") url.searchParams.delete("subject");
      else url.searchParams.set("subject", state.subject);
      history.replaceState(null, "", url);
    }));
    yearSelect.addEventListener("change", () => { state.year = yearSelect.value; state.showAll = false; render(); });
    root.querySelector("#e8-type").addEventListener("change", (e) => { state.type = e.target.value; state.showAll = false; render(); });
    root.querySelector("#e8-search").addEventListener("input", (e) => { state.query = e.target.value; state.showAll = false; render(); });
    render();
  }

  function init() {
    const article = document.querySelector(".md-content__inner");
    if (!article) return;
    if (article.querySelector(".e8-hero")) document.body.classList.add("e8-landing-page");
    if (article.querySelector("#arkusze-pdf")) enhanceCatalog(article);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
