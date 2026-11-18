// Lecteur de dictée : démarre uniquement lorsque l'utilisateur clique sur « Lancer la dictée ».
(function () {
  const cfg = JSON.parse(document.getElementById("session-config").textContent);
  const segments = cfg.segments;
  const form = document.getElementById("dictation-form");
  const box = document.getElementById("typed_text");
  const replayInput = document.getElementById("replay_count");
  const timerEl = document.getElementById("timer");
  const statusEl = document.getElementById("player-status");
  const btnPlay = document.getElementById("btn-play");
  const btnRepeat = document.getElementById("btn-repeat");
  const btnPrev = document.getElementById("btn-prev");
  const btnRestart = document.getElementById("btn-restart");
  const btnSubmit = document.getElementById("btn-submit");
  const submitHint = document.getElementById("submit-hint");
  const slowBox = document.getElementById("chk-slow");
  const voiceSelect = document.getElementById("voice-select");
  const csrfInput = form ? form.querySelector('input[name="csrfmiddlewaretoken"]') : null;
  const csrfToken = csrfInput ? csrfInput.value : "";
  const synth = window.speechSynthesis;
  const draftKey = "dictee-draft-" + cfg.sessionId;
  const voiceStorageKey = "dictee-preferred-voice";

  const START_HTML = "Lancer la dictée";
  const PLAY_HTML = "Lecture";
  const PAUSE_HTML = "Pause";

  let voice = null,
      runId = 0,
      idx = 0,
      playing = false,
      finishedOnce = false,
      replays = 0,
      submitted = false,
      hasStarted = false,
      timer = null,
      endAt = null;

  let preferredVoiceName = cfg.preferredVoice || "";
  try {
    if (preferredVoiceName) {
      localStorage.setItem(voiceStorageKey, preferredVoiceName);
    } else {
      preferredVoiceName = localStorage.getItem(voiceStorageKey) || "";
    }
  } catch (e) {}

  function fmt(s) {
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  }

  // Affiche la durée totale configurée sans lancer le décompte tant que l'utilisateur n'a pas cliqué sur « Lancer la dictée »
  const initialDuration = cfg.maxDuration || cfg.remaining || 300;
  timerEl.textContent = fmt(initialDuration);

  // --- Brouillon local ---
  try {
    const d = localStorage.getItem(draftKey);
    if (d && !box.value) box.value = d;
  } catch (e) {}
  box.addEventListener("input", function () {
    try { localStorage.setItem(draftKey, box.value); } catch (e) {}
  });
  ["paste", "drop"].forEach(function (ev) {
    box.addEventListener(ev, function (e) { e.preventDefault(); });
  });

  // --- Voix (avec sélection personnalisée) ---
  function pickVoice() {
    const all = synth.getVoices() || [];
    const lang = (cfg.lang || "en-US").toLowerCase();
    const enVoices = all.filter(function (v) { return v.lang && v.lang.toLowerCase().indexOf("en") === 0; });
    const list = enVoices.length ? enVoices : all;

    if (voiceSelect && list.length) {
      voiceSelect.innerHTML = '<option value="">Automatique (' + (cfg.lang || "en-US") + ')</option>';
      list.forEach(function (v) {
        const opt = document.createElement("option");
        opt.value = v.name;
        opt.textContent = v.name + " (" + v.lang.replace("_", "-") + ")";
        if (preferredVoiceName && v.name === preferredVoiceName) {
          opt.selected = true;
        }
        voiceSelect.appendChild(opt);
      });
    }

    voice = (preferredVoiceName && all.find(function (v) { return v.name === preferredVoiceName; })) ||
            all.find(function (v) { return v.lang.replace("_", "-").toLowerCase() === lang; }) ||
            all.find(function (v) { return v.lang.toLowerCase().indexOf("en") === 0; }) || null;
  }

  if (voiceSelect) {
    voiceSelect.addEventListener("change", function () {
      preferredVoiceName = voiceSelect.value;
      try { localStorage.setItem(voiceStorageKey, preferredVoiceName); } catch (e) {}
      const all = synth ? synth.getVoices() : [];
      const lang = (cfg.lang || "en-US").toLowerCase();
      voice = (preferredVoiceName && all.find(function (v) { return v.name === preferredVoiceName; })) ||
              all.find(function (v) { return v.lang.replace("_", "-").toLowerCase() === lang; }) ||
              all.find(function (v) { return v.lang.toLowerCase().indexOf("en") === 0; }) || null;
    });
  }

  if (!synth) {
    document.getElementById("no-speech").hidden = false;
    [btnPlay, btnPrev, btnRepeat, btnRestart].forEach(function (b) {
      if (b) b.disabled = true;
    });
  } else {
    pickVoice();
    synth.onvoiceschanged = pickVoice;
  }

  function speak(text) {
    return new Promise(function (resolve) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = voice ? voice.lang : cfg.lang;
      if (voice) u.voice = voice;
      u.rate = Math.max(0.5, cfg.speed * (slowBox.checked ? 0.75 : 1));
      u.onend = resolve;
      u.onerror = resolve;
      synth.speak(u);
    });
  }
  const wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  function setStatus(msg) { statusEl.textContent = msg; }
  function refresh() {
    btnPlay.innerHTML = playing ? PAUSE_HTML : (hasStarted ? PLAY_HTML : START_HTML);
    if (playing) setStatus("Lecture : segment " + (idx + 1) + " sur " + segments.length);
  }

  // --- Minuteur (ne démarre qu'après clic sur « Lancer la dictée ») ---
  function tick() {
    if (!hasStarted || !endAt) return;
    const left = Math.max(0, Math.round((endAt - Date.now()) / 1000));
    timerEl.textContent = fmt(left);
    timerEl.classList.toggle("low", left <= 30);
    if (left <= 0) {
      clearInterval(timer);
      setStatus("Temps écoulé : envoi de votre dictée…");
      lockAndSubmit();
    }
  }

  function startSessionTimerAndUnlock() {
    if (hasStarted) return;
    hasStarted = true;
    endAt = Date.now() + initialDuration * 1000;
    box.disabled = false;
    box.placeholder = "Écoutez attentivement et saisissez le texte en anglais ici...";
    box.focus();
    if (btnRepeat) btnRepeat.disabled = false;
    if (btnPrev) btnPrev.disabled = false;
    if (btnRestart) btnRestart.disabled = false;
    if (btnSubmit) btnSubmit.disabled = false;
    if (submitHint) submitHint.textContent = "Vous pouvez envoyer votre texte dès que vous avez terminé.";

    if (cfg.beginUrl && csrfToken) {
      fetch(cfg.beginUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      }).catch(function () {});
    }

    timer = setInterval(tick, 1000);
    tick();
  }

  async function playFrom(start) {
    if (submitted || !synth) return;
    synth.cancel();
    const my = ++runId;
    playing = true;
    for (let i = start; i < segments.length; i++) {
      idx = i;
      refresh();
      for (let r = 0; r < cfg.repeats; r++) {
        if (my !== runId) return;
        await speak(segments[i]);
        if (my !== runId) return;
        if (r < cfg.repeats - 1) await wait(cfg.pause * 1000);
      }
      if (my !== runId) return;
      if (i < segments.length - 1) await wait(cfg.pause * 1000);
    }
    if (my === runId) {
      playing = false;
      finishedOnce = true;
      idx = 0;
      btnPlay.innerHTML = PLAY_HTML;
      setStatus("Lecture terminée. Vous pouvez tout réécouter ou répéter une phrase.");
    }
  }

  function stop() {
    runId++;
    playing = false;
    if (synth) synth.cancel();
  }

  btnPlay.addEventListener("click", function () {
    if (!hasStarted) {
      startSessionTimerAndUnlock();
      playFrom(0);
      return;
    }
    if (playing) {
      stop();
      btnPlay.innerHTML = PLAY_HTML;
      setStatus("En pause (segment " + (idx + 1) + " sur " + segments.length + ").");
      return;
    }
    if (finishedOnce) {
      replays++;
      finishedOnce = false;
    }
    playFrom(idx);
  });

  if (btnRepeat) {
    btnRepeat.addEventListener("click", function () {
      if (!hasStarted) return;
      replays++;
      playFrom(idx);
    });
  }
  if (btnPrev) {
    btnPrev.addEventListener("click", function () {
      if (!hasStarted) return;
      replays++;
      playFrom(Math.max(0, idx - 1));
    });
  }
  if (btnRestart) {
    btnRestart.addEventListener("click", function () {
      if (!hasStarted) return;
      replays++;
      finishedOnce = false;
      playFrom(0);
    });
  }

  // --- Envoi ---
  function lockAndSubmit() {
    if (submitted || !hasStarted) return;
    submitted = true;
    stop();
    if (timer) clearInterval(timer);
    box.disabled = false;
    box.readOnly = true;
    replayInput.value = replays;
    try { localStorage.removeItem(draftKey); } catch (e) {}
    form.submit();
  }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!hasStarted) return;
    lockAndSubmit();
  });

  // Si l'utilisateur quitte la page en cliquant sur un lien sans avoir lancé la dictée,
  // on annule silencieusement la session en attente pour que rien ne soit pris en compte.
  function cancelUnstartedSession() {
    if (hasStarted || submitted || !cfg.cancelUrl || !csrfToken) return;
    try {
      const fd = new FormData();
      fd.append("csrfmiddlewaretoken", csrfToken);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(cfg.cancelUrl + "?beacon=1", fd);
      } else {
        fetch(cfg.cancelUrl + "?beacon=1", {
          method: "POST",
          body: fd,
          keepalive: true,
          credentials: "same-origin",
        });
      }
    } catch (e) {}
  }

  document.addEventListener("click", function (e) {
    const link = e.target.closest("a[href]");
    if (!link) return;
    const href = link.getAttribute("href") || "";
    if (!href || href.charAt(0) === "#" || href.indexOf("javascript:") === 0) return;
    cancelUnstartedSession();
  });

  window.addEventListener("pagehide", function () {
    cancelUnstartedSession();
  });
})();
