/* Paired visual PDFs + checked explanations. Preserves PDF typography and diagrams. */
(function () {
  "use strict";
  const subjects = {"jezyk-polski":"Język polski","matematyka":"Matematyka","jezyk-angielski":"Język angielski"};
  function element(tag, cls, text) {
    const node=document.createElement(tag);
    if (cls) node.className=cls;
    if (text!==undefined) node.textContent=text;
    return node;
  }
  function init() {
    const root=document.querySelector("#e8-study-root");
    if(!root) return;
    document.body.classList.add("e8-study-page");
    const q=new URLSearchParams(location.search);
    const subject=q.get("subject")||"";
    const year=q.get("year")||"";
    const name=q.get("name")||"";
    if(!subjects[subject] || !/^20\d{2}$/.test(year) || !/^[a-z0-9-]+$/.test(name) ||
      !name.startsWith(subject+"-"+year+"-")) {
      root.append(element("p","e8-study-error","Niepoprawne dane opracowania. Wróć do katalogu arkuszy."));
      return;
    }
    const base=new URL("../pdf/"+subject+"/"+year+"/",location.href);
    const pdf=new URL(name+".pdf",base).href;
    const keyPdf=new URL(name+"-odpowiedzi.pdf",base).href;
    const demo=subject==="matematyka" && year==="2026" && name==="matematyka-2026-egzamin-osmoklasisty";
    const tasks=demo ? (window.E8_STUDY_MATH_2026||[]) : [];
    root.innerHTML=[
      '<section class="e8-study-hero">',
      ' <div><a class="e8-study-back" href="../pdfs/">← Powrót do katalogu</a>',
      ' <span class="e8-kicker">Ucz się na prawdziwych egzaminach</span>',
      ' <h1 id="e8-study-title"></h1><p id="e8-study-intro"></p></div>',
      ' <div class="e8-study-hero-links"><a id="e8-full-pdf" target="_blank" rel="noopener noreferrer">Cały arkusz ↗</a>',
      ' <a id="e8-full-key" target="_blank" rel="noopener noreferrer">Klucz CKE ↗</a></div>',
      '</section>',
      '<div id="e8-study-math" class="e8-study-layout" hidden>',
      ' <aside class="e8-study-nav"><strong>20 zadań</strong><span>Matematyka · maj 2026</span><nav id="e8-task-nav" aria-label="Nawigacja po zadaniach"></nav></aside>',
      ' <main class="e8-study-main">',
      ' <div class="e8-study-task-top"><div><span id="e8-task-category"></span><h2 id="e8-task-heading"></h2></div><span id="e8-task-points"></span></div>',
      ' <div class="e8-study-panes">',
      '  <section class="e8-study-pane"><div class="e8-study-panel-head"><strong>Treść i rysunki z arkusza</strong><a id="e8-question-external" target="_blank" rel="noopener noreferrer">Otwórz PDF ↗</a></div>',
      '    <iframe id="e8-question-view" title="Oryginalny arkusz egzaminacyjny" loading="lazy"></iframe><p class="e8-panel-foot">Zachowano wygląd oryginalnego PDF, w tym zakres pierwiastków, kursywę, pogrubienia i rysunki.</p></section>',
      '  <section class="e8-study-pane e8-study-lesson"><div class="e8-study-panel-head"><strong>Rozwiązanie krok po kroku</strong><span>Klucz CKE · wersja X</span></div>',
      '    <p class="e8-study-hint">Spróbuj rozwiązać zadanie samodzielnie, zanim sprawdzisz odpowiedź.</p>',
      '    <button type="button" class="e8-study-reveal" id="e8-reveal" aria-expanded="false">Pokaż odpowiedź i omówienie</button>',
      '    <div id="e8-solution" hidden><div id="e8-task-answer" class="e8-study-answer"></div><h3>Jak dojść do wyniku?</h3>',
      '      <ol id="e8-task-steps"></ol><div class="e8-study-trap"><strong>Typowy błąd</strong><p id="e8-task-tip"></p></div>',
      '      <a id="e8-key-external" target="_blank" rel="noopener noreferrer">Sprawdź fragment oficjalnego klucza ↗</a></div>',
      '  </section>',
      ' </div>',
      ' <div class="e8-study-pager"><button id="e8-prev" type="button">← Poprzednie</button><span id="e8-counter"></span><button id="e8-next" type="button">Następne →</button></div>',
      ' </main>',
      '</div>',
      '<section id="e8-study-compare" class="e8-study-compare" hidden>',
      ' <div class="e8-study-notice"><strong>Porównanie dokumentów źródłowych</strong><p>Widok łączy oryginalny arkusz oraz zasady oceniania. Szczegółowe opisy krok po kroku są przygotowywane osobno i nie zostały jeszcze zweryfikowane dla tego egzaminu.</p></div>',
      ' <div class="e8-study-duo"><div class="e8-study-pane"><div class="e8-study-panel-head"><strong>Arkusz</strong><a id="e8-compare-question-open" target="_blank" rel="noopener noreferrer">Otwórz ↗</a></div><iframe id="e8-compare-question" title="PDF arkusza" loading="lazy"></iframe></div>',
      ' <div class="e8-study-pane"><div class="e8-study-panel-head"><strong>Zasady oceniania CKE</strong><a id="e8-compare-key-open" target="_blank" rel="noopener noreferrer">Otwórz ↗</a></div><iframe id="e8-compare-key" title="PDF odpowiedzi" loading="lazy"></iframe></div></div></section>',
      '<p class="e8-study-source">Źródło zadań i zasad oceniania: PDF-y CKE w repozytorium. Dydaktyczne omówienia są autorskie i nie stanowią oficjalnego stanowiska CKE.</p>'
    ].join("");
    root.querySelector("#e8-study-title").textContent="Opracowanie · "+subjects[subject]+" "+year;
    root.querySelector("#e8-full-pdf").href=pdf;
    root.querySelector("#e8-full-key").href=keyPdf;
    if(!tasks.length) {
      root.querySelector("#e8-study-intro").textContent="Pracuj z oryginalnym arkuszem i kluczem CKE w jednym miejscu. Weryfikowane komentarze dydaktyczne są dodawane sukcesywnie.";
      root.querySelector("#e8-study-compare").hidden=false;
      root.querySelector("#e8-compare-question").src=pdf;
      root.querySelector("#e8-compare-key").src=keyPdf;
      root.querySelector("#e8-compare-question-open").href=pdf;
      root.querySelector("#e8-compare-key-open").href=keyPdf;
      return;
    }
    root.querySelector("#e8-study-intro").textContent="Pełne opracowanie 20 zadań z 12 maja 2026 r. · odpowiedzi dla wersji X · oryginalny układ PDF i wyjaśnienia sprawdzone z kluczem CKE.";
    root.querySelector("#e8-study-math").hidden=false;
    let current=0;
    const nav=root.querySelector("#e8-task-nav");
    const buttons=[];
    for(let i=0;i<tasks.length;i++){
      const t=tasks[i];
      const b=element("button","e8-task-nav-button");
      b.type="button";
      b.append(element("strong","","Zadanie "+t.n),element("span","",t.topic));
      b.addEventListener("click",()=>select(i));
      nav.append(b);buttons.push(b);
    }
    const reveal=root.querySelector("#e8-reveal");
    const solution=root.querySelector("#e8-solution");
    function select(i){
      current=Math.max(0,Math.min(tasks.length-1,i));
      const t=tasks[current];
      root.querySelector("#e8-task-heading").textContent="Zadanie "+t.n;
      root.querySelector("#e8-task-category").textContent=t.topic;
      root.querySelector("#e8-task-points").textContent=t.n<15?"0–1 pkt":({15:"0–2 pkt",16:"0–3 pkt",17:"0–3 pkt",18:"0–2 pkt",19:"0–3 pkt",20:"0–3 pkt"}[t.n]);
      const pageUrl=pdf+"#page="+t.page;
      root.querySelector("#e8-question-view").src=pageUrl;
      root.querySelector("#e8-question-external").href=pageUrl;
      root.querySelector("#e8-task-answer").textContent="Odpowiedź: "+t.answer;
      const list=root.querySelector("#e8-task-steps"); list.replaceChildren();
      t.steps.forEach(step=>list.append(element("li","",step)));
      root.querySelector("#e8-task-tip").textContent=t.tip;
      root.querySelector("#e8-key-external").href=keyPdf+"#page="+t.key;
      root.querySelector("#e8-counter").textContent=(current+1)+" / "+tasks.length;
      root.querySelector("#e8-prev").disabled=current===0;
      root.querySelector("#e8-next").disabled=current===tasks.length-1;
      buttons.forEach((button,index)=>{
        button.classList.toggle("is-active",index===current);
        button.setAttribute("aria-current",index===current?"step":"false");
      });
      solution.hidden=true;
      reveal.textContent="Pokaż odpowiedź i omówienie";
      reveal.setAttribute("aria-expanded","false");
      const url=new URL(location.href);url.hash="zadanie-"+t.n;history.replaceState(null,"",url);
    }
    reveal.addEventListener("click",()=>{
      solution.hidden=!solution.hidden;
      reveal.textContent=solution.hidden?"Pokaż odpowiedź i omówienie":"Ukryj omówienie";
      reveal.setAttribute("aria-expanded",String(!solution.hidden));
    });
    root.querySelector("#e8-prev").addEventListener("click",()=>select(current-1));
    root.querySelector("#e8-next").addEventListener("click",()=>select(current+1));
    const hash=location.hash.match(/^#zadanie-(\d{1,2})$/);
    const initial=hash?Number(hash[1])-1:0;
    select(initial>=0&&initial<tasks.length?initial:0);
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",init);
  else init();
})();
