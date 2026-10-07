// Oberfläche der App (Alpine.js). Jede "Seite" ist ein Abschnitt in index.html,
// welcher angezeigt wird, steht im Teil hinter dem # in der Adresse.

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail || ""; } catch (e) { /* egal */ }
    throw new Error(detail || `Fehler ${response.status}`);
  }
  return response.json();
}

function app() {
  return {
    page: "start",
    overview: {},
    settings: { lektionsdauer_min: 30 },
    error: "",
    info: "",
    savedFlash: false,

    // Hell/Dunkel: "auto" folgt der Einstellung des Mac.
    get theme() {
      if (this.settings.design === "hell") return "light";
      if (this.settings.design === "dunkel") return "dark";
      return "";
    },

    start() {
      window.addEventListener("hashchange", () => this.route());
      this.route();
      if (this.page === "lektion") this.refresh();  // Einstellungen (Audiotempo) laden
    },

    route() {
      const name = (location.hash.replace(/^#\/?/, "") || "start").split("/")[0];
      this.page = ["start", "lektion", "fortschritt", "wortschatz", "einstellungen"].includes(name) ? name : "start";
      this.info = "";
      if (this.page === "lektion") {
        // Die Lektion (lesson.js) lädt sich daraufhin selbst. setTimeout, damit
        // die Lektions-Komponente beim allerersten Laden schon bereit ist.
        setTimeout(() => window.dispatchEvent(new CustomEvent("lektion-laden")), 0);
      } else {
        Sprache.stopp();
        this.refresh();
      }
    },

    async refresh() {
      try {
        [this.overview, this.settings] = await Promise.all([api("/api/overview"), api("/api/settings")]);
        Sprache.tempo = Number(this.settings.audio_tempo) || 1;
        this.error = "";
      } catch (e) {
        this.error = "Bitte Start.command erneut per Doppelklick öffnen.";
      }
    },

    levelText() {
      const f = this.overview.fortschritt;
      if (!f) return "";
      return `${f.erledigt} von ${f.gesamt} Lektionen`;
    },

    // Beschriftung des großen Buttons je nach Stand
    get startText() {
      const n = this.overview.naechste_lektion;
      if (!n) return "Wiederholen";
      if (n.begonnen) return "Lektion fortsetzen";
      if (this.overview.heute_erledigt > 0) return "Noch eine Lektion";
      return "Heutige Lektion starten";
    },

    startLesson() {
      if (!this.overview.naechste_lektion) {
        location.hash = "#/lektion/wiederholung";
        return;
      }
      location.hash = "#/lektion";
    },

    startWiederholung() {
      location.hash = "#/lektion/wiederholung";
    },

    async saveSettings() {
      try {
        this.settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(this.settings) });
        Sprache.tempo = Number(this.settings.audio_tempo) || 1;
        this.savedFlash = true;
        setTimeout(() => (this.savedFlash = false), 1500);
      } catch (e) {
        alert("Speichern hat nicht geklappt: " + e.message);
      }
    },

    async importBackup(event) {
      const file = event.target.files[0];
      event.target.value = "";
      if (!file) return;
      if (!confirm("Damit wird dein aktueller Lernstand durch die Sicherung ersetzt. " +
                   "(Der jetzige Stand wird vorher automatisch gesichert.) Fortfahren?")) return;
      try {
        await api("/api/import", { method: "POST", body: await file.text() });
        await this.refresh();
        alert("Sicherung wurde wiederhergestellt.");
      } catch (e) {
        alert("Wiederherstellen hat nicht geklappt: " + e.message);
      }
    },
  };
}
