/* English study audio: best available browser voice, manual selection and sample.
   Web Speech API quality is supplied by the browser/OS, not this web page. */
(function () {
  "use strict";
  if (!document.querySelector(".e8-en-study")) return;
  const synthOK = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  const synth = synthOK ? window.speechSynthesis : null;
  const voiceSelect = document.getElementById("e8-tts-voice");
  const rateSelect = document.getElementById("e8-tts-rate");
  const statusBox = document.getElementById("e8-tts-status");
  const helpBox = document.getElementById("e8-tts-voice-help");
  const previewButton = document.getElementById("e8-tts-preview");
  const stopButton = document.getElementById("e8-tts-stop");
  const selectionButton = document.querySelector("[data-e8-speak-selection]");
  const readButtons = Array.from(document.querySelectorAll(".e8-en-study [data-e8-speak]"));
  const preferenceKey = "e8-english-voice";
  let voices = [];
  let activeUtterance = null;
  let activeButton = null;
  let playToken = 0;
  let selectedText = "";

  const voiceKey = v => [v.voiceURI, v.name, v.lang].join("|");
  function status(value) { if (statusBox) statusBox.textContent = value; }
  function getSavedVoice() {
    try { return window.localStorage.getItem(preferenceKey); } catch (_) { return null; }
  }
  function saveVoice(value) {
    try { window.localStorage.setItem(preferenceKey, value); } catch (_) { /* privacy mode */ }
  }
  function qualityScore(v) {
    const name = v.name.toLowerCase();
    let score = 0;
    if (/natural|neural|premium|enhanced|online/.test(name)) score += 100;
    if (/siri|aria|jenny|ryan|sonia|libby|microsoft|google|samantha/.test(name)) score += 20;
    if (/^en[-_]gb$/i.test(v.lang)) score += 6;
    if (/^en[-_]us$/i.test(v.lang)) score += 5;
    return score;
  }
  function resetButtons() {
    for (const b of readButtons) {
      b.classList.remove("is-speaking");
      b.setAttribute("aria-pressed", "false");
      b.textContent = b.dataset.defaultLabel || "Odsłuchaj po angielsku";
    }
    if (previewButton) {
      previewButton.classList.remove("is-speaking");
      previewButton.textContent = "Sprawdź głos";
      previewButton.setAttribute("aria-pressed", "false");
    }
    if (selectionButton) {
      selectionButton.classList.remove("is-speaking");
      selectionButton.textContent = "Odsłuchaj zaznaczenie";
      selectionButton.setAttribute("aria-pressed", "false");
    }
    activeButton = null;
    activeUtterance = null;
  }
  function stop(announce = true) {
    playToken++;
    if (synth) synth.cancel();
    resetButtons();
    if (announce) status("Odsłuch zatrzymany.");
  }
  function chosenVoice() {
    const key = voiceSelect?.value;
    return voices.find(v => voiceKey(v) === key) || voices[0] || null;
  }
  function populateVoices() {
    if (!synth || !voiceSelect) return;
    const found = synth.getVoices().filter(v => /^en(?:[-_]|$)/i.test(v.lang));
    found.sort((a, b) => qualityScore(b)-qualityScore(a) ||
      (a.name || "").localeCompare(b.name || ""));
    if (!found.length) {
      voiceSelect.replaceChildren(new Option("Brak dostępnych głosów angielskich", ""));
      voiceSelect.disabled = true;
      if (previewButton) previewButton.disabled = true;
      if (helpBox) helpBox.textContent = "Brak głosu angielskiego w przeglądarce. Zainstaluj głos angielski w systemie lub spróbuj funkcji Czytaj na głos w Microsoft Edge.";
      return;
    }
    const current = voiceSelect.value || getSavedVoice();
    voices = found;
    voiceSelect.replaceChildren();
    for (const v of voices) {
      const option = new Option(v.name + " (" + v.lang + ")", voiceKey(v));
      voiceSelect.append(option);
    }
    const preferred = voices.find(v => voiceKey(v) === current) || voices[0];
    voiceSelect.value = voiceKey(preferred);
    voiceSelect.disabled = false;
    if (previewButton) previewButton.disabled = false;
    if (helpBox) {
      const premium = /natural|neural|premium|enhanced|online/i.test(preferred.name);
      helpBox.textContent = premium
        ? "Wybrano głos oznaczony przez system jako naturalny lub ulepszony. Kliknij „Sprawdź głos”, aby ocenić brzmienie."
        : "Przeglądarka nie udostępnia tu rozpoznanego głosu naturalnego. Wypróbuj inne głosy z listy; jakość zależy od systemu i przeglądarki.";
    }
  }
  function readText(button) {
    const selector = button.dataset.e8Speak;
    const node = selector ? document.querySelector(selector) : null;
    if (!node || !document.querySelector(".e8-en-study")?.contains(node)) return "";
    return node.dataset.speechText || node.innerText || node.textContent || "";
  }
  function play(raw, button) {
    if (!synth) {
      status("Odsłuch niedostępny w tej przeglądarce.");
      return;
    }
    const voice = chosenVoice();
    if (!voice) {
      populateVoices();
      status("Brak angielskiego głosu. Sprawdź ustawienia mowy w systemie lub skorzystaj z funkcji Czytaj na głos w Edge.");
      return;
    }
    const text = String(raw || "").replace(/\s+/g, " ").trim();
    if (!text) { status("Brak tekstu do odsłuchania."); return; }
    if (activeButton === button) { stop(); return; }
    stop(false);
    const token = ++playToken;
    activeButton = button;
    const u = new SpeechSynthesisUtterance(text);
    activeUtterance = u;
    u.voice = voice;
    u.lang = voice.lang;
    u.pitch = 1;
    const rate = Number(rateSelect?.value || "1");
    u.rate = Number.isFinite(rate) ? Math.min(1.2,Math.max(0.8,rate)) : 1;
    const resetIfCurrent = () => {
      if (token !== playToken) return false;
      resetButtons();
      return true;
    };
    u.onstart = () => {
      if (token !== playToken) return;
      button.classList.add("is-speaking");
      button.textContent = "Zatrzymaj odsłuch";
      button.setAttribute("aria-pressed","true");
      status("Odtwarzanie: " + voice.name + " · " + u.rate + "×.");
    };
    u.onend = () => { if (resetIfCurrent()) status("Odsłuch zakończony."); };
    u.onerror = event => {
      if (!resetIfCurrent()) return;
      if (event.error !== "canceled" && event.error !== "interrupted")
        status("Nie udało się uruchomić głosu. Zmień głos w menu lub użyj funkcji Czytaj na głos w Edge.");
    };
    try {
      synth.speak(u);
      status("Uruchamianie głosu: " + voice.name + "…");
    } catch (_) {
      if (resetIfCurrent()) status("Nie udało się uruchomić tego głosu.");
    }
  }
  function selectedEnglishText() {
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : "";
    if (!text) return "";
    const anchor = selection.anchorNode;
    const element = anchor?.nodeType === 1 ? anchor : anchor?.parentElement;
    if (!element?.closest(".e8-en-study .e8-speakable")) return "";
    return text;
  }
  function init() {
    for (const button of readButtons) {
      button.dataset.defaultLabel = button.textContent.trim();
      button.type = "button";
      button.setAttribute("aria-pressed","false");
      if (!synthOK) button.disabled = true;
    }
    if (selectionButton && !synthOK) selectionButton.disabled = true;
    if (stopButton && !synthOK) stopButton.disabled = true;
    if (voiceSelect && !synthOK) voiceSelect.disabled = true;
    if (previewButton && !synthOK) previewButton.disabled = true;

    if (synthOK) {
      populateVoices();
      if ("onvoiceschanged" in synth) synth.addEventListener("voiceschanged", populateVoices);
      window.setTimeout(populateVoices, 500);
      window.setTimeout(populateVoices, 1800);
    } else {
      status("Twoja przeglądarka nie obsługuje syntezy mowy.");
    }
    document.addEventListener("selectionchange", () => {
      const now = selectedEnglishText();
      if (now) selectedText = now;
    });
    document.addEventListener("click", event => {
      const read = event.target.closest(".e8-en-study [data-e8-speak]");
      if (read) { play(readText(read),read); return; }
      if (event.target.closest("#e8-tts-preview")) {
        play("Hello! Welcome to your English exam practice. Choose the voice you like best, then listen to the text at a comfortable speed.",previewButton);
        return;
      }
      if (event.target.closest("[data-e8-speak-selection]")) {
        const selected = selectedEnglishText() || selectedText;
        if (selected) play(selected,selectionButton);
        else status("Zaznacz fragment angielskiego tekstu, a potem kliknij „Odsłuchaj zaznaczenie”.");
        return;
      }
      if (event.target.closest("#e8-tts-stop")) stop();
    });
    voiceSelect?.addEventListener("change", () => {
      stop(false);
      saveVoice(voiceSelect.value);
      const v = chosenVoice();
      if (helpBox && v) helpBox.textContent = "Głos: " + v.name + ". Kliknij „Sprawdź głos”, aby go posłuchać.";
      status("Wybrany głos: " + (v?.name || "brak") + ".");
    });
    window.addEventListener("pagehide", () => { if (synth) synth.cancel(); });
    if (synthOK) status("Wybierz głos i kliknij „Sprawdź głos”, a potem odsłuchaj tekst.");
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
