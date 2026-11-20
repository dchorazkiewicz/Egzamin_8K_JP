/* Load MathJax only for the complete mathematics longread. */
(function () {
  "use strict";
  function init() {
    const root = document.querySelector(".e8-math-longread");
    if (!root) return;
    const status = document.createElement("p");
    status.id = "e8-mathjax-status";
    status.setAttribute("role", "status");
    status.className = "e8-mathjax-status";
    status.textContent = "Przygotowywanie czytelnego zapisu wzorów…";
    root.querySelector(".e8-m-intro")?.append(status);

    window.MathJax = {
      tex: {
        inlineMath: [["\\(", "\\)"]],
        displayMath: [["\\[", "\\]"]],
        processEscapes: true,
        packages: {"[+]": ["ams"]}
      },
      chtml: {scale: 1, displayAlign: "left", displayIndent: "0"},
      options: {skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"]},
      startup: {typeset: true}
    };

    const sources = [
      "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js",
      "https://unpkg.com/mathjax@3.2.2/es5/tex-chtml.js"
    ];
    function tryLoad(i) {
      if (i >= sources.length) {
        status.textContent = "Nie udało się pobrać silnika MathJax. Sprawdź połączenie lub blokadę skryptów zewnętrznych.";
        status.classList.add("is-error");
        return;
      }
      const s = document.createElement("script");
      s.src = sources[i];
      s.defer = true;
      s.onload = () => {
        const typeset = window.MathJax?.startup?.promise || Promise.resolve();
        Promise.resolve(typeset).then(() => {
          if (!document.querySelector(".e8-m-eq mjx-container")) {
            return window.MathJax.typesetPromise?.([root]);
          }
        }).then(() => {
          const rendered = root.querySelectorAll(".e8-m-eq mjx-container").length;
          if (rendered < 74) {
            status.textContent = "Uwaga: wyrenderowano " + rendered + " z 74 wzorów. Spróbuj ponownie odświeżyć stronę.";
            status.classList.add("is-error");
          } else {
            status.remove();
          }
        }).catch(() => {
          status.textContent = "Niektóre wzory LaTeX nie zostały wyrenderowane. Odśwież stronę.";
          status.classList.add("is-error");
        });
      };
      s.onerror = () => {s.remove(); tryLoad(i+1);};
      document.head.appendChild(s);
    }
    tryLoad(0);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded",init);
  else init();
})();
