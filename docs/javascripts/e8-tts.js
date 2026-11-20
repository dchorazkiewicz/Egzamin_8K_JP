/* English read-aloud controls: no external services, no audio files, user gesture only. */
(function () {
  "use strict";
  const root = () => document.querySelector(".e8-en-study");
  let activeButton = null;
  let activeText = "";
  let utterance = null;
  const api = ("speechSynthesis" in window) && ("SpeechSynthesisUtterance" in window);

  function status(message) {
    const live = document.getElementById("e8-tts-status");
    if (live) live.textContent = message;
  }
  function resetButtons() {
    document.querySelectorAll("[data-e8-speak]").forEach(button => {
      button.classList.remove("is-speaking");
      button.setAttribute("aria-pressed", "false");
      button.textContent = button.dataset.defaultLabel || "Odsłuchaj po angielsku";
    });
    activeButton = null;
    utterance = null;
  }
  function stop() {
    if (api) window.speechSynthesis.cancel();
    resetButtons();
    status("Odsłuch zatrzymany.");
  }
  function englishVoice() {
    const voices = window.speechSynthesis.getVoices();
    return voices.find(v => /^en[-_]GB/i.test(v.lang)) ||
      voices.find(v => /^en[-_]US/i.test(v.lang)) ||
      voices.find(v => /^en\b/i.test(v.lang)) || null;
  }
  function textFor(button) {
    const selector = button.dataset.e8Speak;
    if (!selector) return "";
    const target = document.querySelector(selector);
    if (!target || !root()?.contains(target)) return "";
    return target.dataset.speechText || target.innerText || target.textContent || "";
  }
  function speak(text, button) {
    if (!api) {
      status("Ta przeglądarka nie udostępnia syntezy mowy. Spróbuj Chrome, Edge lub Safari.");
      return;
    }
    const phrase = String(text).replace(/\s+/g, " ").trim();
    if (!phrase) { status("Nie znaleziono tekstu do odczytania."); return; }
    if (activeButton === button && window.speechSynthesis.speaking) {
      stop(); return;
    }
    window.speechSynthesis.cancel();
    resetButtons();
    activeButton = button;
    activeText = phrase;
    utterance = new window.SpeechSynthesisUtterance(phrase);
    utterance.lang = "en-GB";
    const voice = englishVoice();
    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    }
    const rate = parseFloat(document.getElementById("e8-tts-rate")?.value || "0.9");
    utterance.rate = Number.isFinite(rate) ? Math.min(1.3, Math.max(0.65, rate)) : 0.9;
    utterance.pitch = 1;
    utterance.onstart = () => {
      if (activeButton !== button) return;
      button.classList.add("is-speaking");
      button.setAttribute("aria-pressed", "true");
      button.textContent = "Zatrzymaj odsłuch";
      status("Czytanie po angielsku. Prędkość: " + utterance.rate + "×.");
    };
    utterance.onend = () => {
      if (activeButton !== button) return;
      resetButtons();
      status("Odsłuch zakończony.");
    };
    utterance.onerror = evt => {
      if (activeButton !== button) return;
      resetButtons();
      if (evt.error !== "canceled" && evt.error !== "interrupted")
        status("Nie udało się odczytać tekstu. Sprawdź głosy systemowe języka angielskiego.");
    };
    try {
      window.speechSynthesis.speak(utterance);
      status("Uruchamianie angielskiego głosu…");
    } catch (_) {
      resetButtons();
      status("Odsłuch jest niedostępny na tym urządzeniu.");
    }
  }
  function readSelection(button) {
    const selection = window.getSelection();
    const selected = selection?.toString()?.trim() || "";
    const container = selection?.anchorNode?.parentElement?.closest(".e8-speakable");
    if (!selected || !container || !root()?.contains(container)) {
      status("Najpierw zaznacz fragment angielskiego tekstu w opracowaniu.");
      return;
    }
    speak(selected, button);
  }
  function init() {
    if (!root()) return;
    document.querySelectorAll("[data-e8-speak]").forEach(button => {
      button.dataset.defaultLabel = button.textContent.trim();
      button.type = "button";
      if (!api) {
        button.disabled = true;
        button.title = "Synteza mowy niedostępna w tej przeglądarce";
      }
    });
    document.querySelectorAll("[data-e8-speak-selection]").forEach(button => {
      button.type = "button";
      button.dataset.defaultLabel = button.textContent.trim();
      if (!api) button.disabled = true;
    });
    const stopButton = document.getElementById("e8-tts-stop");
    if (stopButton && !api) stopButton.disabled = true;
    document.addEventListener("click", event => {
      const btn = event.target.closest("[data-e8-speak]");
      if (btn && root()?.contains(btn)) speak(textFor(btn), btn);
      const selectionBtn = event.target.closest("[data-e8-speak-selection]");
      if (selectionBtn && root()?.contains(selectionBtn)) readSelection(selectionBtn);
      const stopper = event.target.closest("#e8-tts-stop");
      if (stopper) stop();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && api && window.speechSynthesis.speaking) stop();
    });
    window.addEventListener("pagehide", () => { if (api) window.speechSynthesis.cancel(); });
    status(api ? "Gotowe. Wybierz Odsłuchaj albo zaznacz fragment tekstu." :
      "Twoja przeglądarka nie obsługuje syntezy mowy.");
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
