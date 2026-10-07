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

    async start() {
      this.route();
      window.addEventListener("hashchange", () => this.route());
      await this.refresh();
    },

    route() {
      const name = location.hash.replace(/^#\/?/, "") || "start";
      this.page = ["start", "fortschritt", "wortschatz", "einstellungen"].includes(name) ? name : "start";
      if (this.page !== "start") this.info = "";
    },

    async refresh() {
      try {
        [this.overview, this.settings] = await Promise.all([api("/api/overview"), api("/api/settings")]);
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

    startLesson() {
      // Der Lektionsablauf entsteht in Etappe (b).
      this.info = "Der Lektionsablauf wird in der nächsten Etappe eingebaut – bis gleich!";
    },

    async saveSettings() {
      try {
        this.settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(this.settings) });
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
