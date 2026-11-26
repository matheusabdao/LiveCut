/* LiveCut — web UI logic (bridges to Python via pywebview.api) */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const state = {
    view: "home",
    running: false,
    phrases: [], // [{text, fromImage}]
    settings: {
      theme: "light",
      quality: "best",
      sensitivity: 60,
      precision: 50,
      max_clips: 8,
      keep_downloaded: false,
      skip_whisper: false,
      skip_cut: false,
    },
  };

  const api = window.pywebview?.api;
  const isPywebview = !!api;

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------
  const $ = (id) => document.getElementById(id);

  function showToast(msg, ms = 2200) {
    const t = $("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove("show"), ms);
  }

  function setTheme(theme) {
    document.body.classList.remove("theme-light", "theme-dark");
    document.body.classList.add("theme-" + theme);
    state.settings.theme = theme;
    localStorage.setItem("livecut_theme", theme);
  }

  function setStatus(text, kind) {
    $("statusText").textContent = text;
    const dot = $("statusDot");
    dot.classList.remove("running", "done", "error");
    if (kind) dot.classList.add(kind);
  }

  function setRunning(running) {
    state.running = running;
    $("btnRun").disabled = running;
    $("btnStop").disabled = !running;
    $("progressWrap").classList.toggle("visible", running);
    if (running) setStatus("Executando…", "running");
  }

  // Called from Python: window.onLog(line, level)
  window.onLog = function (line, level) {
    appendLog(line, level);
  };

  function appendLog(line, level) {
    const log = $("logOutput");
    const span = document.createElement("span");
    if (level) span.className = level;
    span.textContent = line + (line.endsWith("\n") ? "" : "\n");
    log.appendChild(span);
    log.scrollTop = log.scrollHeight;
  }

  // ---------------------------------------------------------------------------
  // Settings persistence
  // ---------------------------------------------------------------------------
  async function loadSettings() {
    try {
      if (isPywebview) {
        const saved = await api.get_settings();
        if (saved && typeof saved === "object") {
          state.settings = Object.assign(state.settings, saved);
        }
        const v = await api.get_version();
        if (v) $("appVersion").textContent = "v" + v;
      }
    } catch (e) {
      console.warn("loadSettings failed", e);
    }
    // local theme override if present
    const localTheme = localStorage.getItem("livecut_theme");
    if (localTheme) state.settings.theme = localTheme;
    applySettingsToUI();
  }

  function applySettingsToUI() {
    const s = state.settings;
    setTheme(s.theme);
    $("quality").value = s.quality || "best";
    $("sensitivity").value = s.sensitivity;
    $("sensitivityValue").textContent = s.sensitivity;
    $("precision").value = s.precision;
    $("precisionValue").value = s.precision;
    $("maxClips").value = s.max_clips;
    $("keepDownloaded").checked = !!s.keep_downloaded;
    $("skipWhisper").checked = !!s.skip_whisper;
    $("skipCut").checked = !!s.skip_cut;
    if (s.phrases && Array.isArray(s.phrases)) {
      state.phrases = s.phrases.map((p) =>
        typeof p === "string" ? { text: p, fromImage: false } : p
      );
    }
    renderPhrases();
  }

  function collectSettingsFromUI() {
    return {
      theme: state.settings.theme,
      quality: $("quality").value,
      sensitivity: parseInt($("sensitivity").value, 10),
      precision: parseInt($("precision").value, 10),
      max_clips: parseInt($("maxClips").value, 10),
      keep_downloaded: $("keepDownloaded").checked,
      skip_whisper: $("skipWhisper").checked,
      skip_cut: $("skipCut").checked,
      phrases: state.phrases,
    };
  }

  async function saveSettings(silent) {
    const s = collectSettingsFromUI();
    state.settings = Object.assign({}, state.settings, s);
    if (isPywebview) {
      try {
        await api.save_settings(s);
      } catch (e) {
        console.warn("save_settings failed", e);
      }
    }
    if (!silent) {
      $("saveHint").textContent = "Configurações salvas ✓";
      setTimeout(() => ($("saveHint").textContent = ""), 2500);
    }
  }

  // ---------------------------------------------------------------------------
  // Phrases
  // ---------------------------------------------------------------------------
  function renderPhrases() {
    const list = $("phrasesList");
    list.innerHTML = "";
    state.phrases.forEach((p, idx) => {
      const chip = document.createElement("div");
      chip.className = "phrase-chip" + (p.fromImage ? " from-image" : "");
      const span = document.createElement("span");
      span.textContent = p.text;
      span.title = p.text + (p.fromImage ? " (de screenshot)" : "");
      const btn = document.createElement("button");
      btn.textContent = "×";
      btn.title = "Remover";
      btn.onclick = () => {
        state.phrases.splice(idx, 1);
        renderPhrases();
        saveSettings(true);
      };
      chip.appendChild(span);
      chip.appendChild(btn);
      list.appendChild(chip);
    });
  }

  function addPhrase(text, fromImage) {
    text = (text || "").trim();
    if (!text) return;
    // avoid duplicates
    if (state.phrases.some((p) => p.text.toLowerCase() === text.toLowerCase())) {
      showToast("Frase já adicionada");
      return;
    }
    state.phrases.push({ text, fromImage: !!fromImage });
    renderPhrases();
    saveSettings(true);
  }

  // ---------------------------------------------------------------------------
  // View switching
  // ---------------------------------------------------------------------------
  function showView(name) {
    state.view = name;
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    $("view-" + name).classList.add("active");
    document.querySelectorAll(".nav-item").forEach((n) => {
      n.classList.toggle("active", n.dataset.view === name);
    });
  }

  // ---------------------------------------------------------------------------
  // Pipeline
  // ---------------------------------------------------------------------------
  async function runPipeline() {
    const source = $("sourceInput").value.trim();
    if (!source) {
      showToast("Cole um link ou escolha um arquivo primeiro");
      return;
    }
    const output = $("outputInput").value.trim();

    await saveSettings(true);
    setRunning(true);
    $("logOutput").innerHTML = "";
    appendLog("▶ Iniciando pipeline…\n");

    if (isPywebview) {
      try {
        await api.run_pipeline(source, output, state.settings);
      } catch (e) {
        appendLog("❌ Erro ao iniciar: " + e.message, "err");
        setRunning(false);
        setStatus("Erro", "error");
      }
    } else {
      // dev fallback: simulate
      appendLog("[dev mode] pywebview não disponível", "warn");
      setTimeout(() => {
        setRunning(false);
        setStatus("Pronto", "done");
      }, 1500);
    }
  }

  async function stopPipeline() {
    if (!isPywebview) return;
    try {
      await api.stop_pipeline();
      appendLog("⏹ Parando…\n", "warn");
    } catch (e) {
      console.warn(e);
    }
  }

  // ---------------------------------------------------------------------------
  // File dialogs
  // ---------------------------------------------------------------------------
  async function browseFile() {
    if (!isPywebview) return;
    try {
      const path = await api.browse_file();
      if (path) $("sourceInput").value = path;
    } catch (e) {
      console.warn(e);
    }
  }

  async function browseOutput() {
    if (!isPywebview) return;
    try {
      const path = await api.browse_output();
      if (path) $("outputInput").value = path;
    } catch (e) {
      console.warn(e);
    }
  }

  async function openOutput() {
    const path = $("outputInput").value.trim();
    if (!path || !isPywebview) return;
    try {
      await api.open_output(path);
    } catch (e) {
      showToast("Não foi possível abrir a pasta");
    }
  }

  async function pasteUrl() {
    if (!isPywebview) {
      showToast("Modo desenvolvimento: cole manualmente");
      return;
    }
    try {
      const text = await api.paste_clipboard();
      if (text) $("sourceInput").value = text.trim();
    } catch (e) {
      console.warn(e);
    }
  }

  async function ocrImage() {
    if (!isPywebview) {
      showToast("Modo desenvolvimento: OCR indisponível");
      return;
    }
    showToast("Analisando imagem…");
    try {
      const text = await api.ocr_image();
      if (text && text.trim()) {
        addPhrase(text.trim(), true);
        showToast("Texto extraído e adicionado ✓");
      } else {
        showToast("Nenhum texto encontrado na imagem");
      }
    } catch (e) {
      showToast("Erro ao ler a imagem: " + (e.message || e));
    }
  }

  // ---------------------------------------------------------------------------
  // Wiring
  // ---------------------------------------------------------------------------
  function wire() {
    // nav
    document.querySelectorAll(".nav-item").forEach((btn) => {
      btn.onclick = () => showView(btn.dataset.view);
    });

    // theme
    $("themeToggle").onclick = () => {
      const next = state.settings.theme === "light" ? "dark" : "light";
      setTheme(next);
      saveSettings(true);
    };

    // home
    $("btnRun").onclick = runPipeline;
    $("btnStop").onclick = stopPipeline;
    $("btnBrowseFile").onclick = browseFile;
    $("btnPasteUrl").onclick = pasteUrl;
    $("btnBrowseOutput").onclick = browseOutput;
    $("btnOpenOutput").onclick = openOutput;
    $("btnClearLog").onclick = () => ($("logOutput").innerHTML = "");

    // settings
    $("btnAddPhrase").onclick = () => {
      const input = $("phraseInput");
      addPhrase(input.value, false);
      input.value = "";
      input.focus();
    };
    $("phraseInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") $("btnAddPhrase").click();
    });
    $("btnOcrImage").onclick = ocrImage;
    $("btnSaveSettings").onclick = () => saveSettings(false);

    // live sliders
    $("sensitivity").addEventListener("input", (e) => {
      $("sensitivityValue").textContent = e.target.value;
    });
    $("precision").addEventListener("input", (e) => {
      $("precisionValue").textContent = e.target.value;
    });

    // save on blur of numeric fields
    ["quality", "maxClips", "keepDownloaded", "skipWhisper", "skipCut"].forEach((id) => {
      $(id).addEventListener("change", () => saveSettings(true));
    });
  }

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------
  window.addEventListener("DOMContentLoaded", () => {
    wire();
    loadSettings().then(() => {
      if (!isPywebview) {
        appendLog("Modo desenvolvimento (pywebview não conectado).\n", "warn");
      }
    });
  });

  // Allow Python to signal pipeline completion/error
  window.onPipelineDone = function (ok, message) {
    setRunning(false);
    if (ok) {
      setStatus("Concluído", "done");
      if (message) appendLog(message, "ok");
    } else {
      setStatus("Erro", "error");
      if (message) appendLog(message, "err");
    }
  };
})();
