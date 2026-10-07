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
    stimmenInfo: "",
    statistik: null,
    wortListe: [],
    suche: "",
    wortArt: "alle",
    kiTab: "chat",
    chat: { thema: "frei", verlauf: [], eingabe: "", laedt: false, fehler: "", hoert: false },
    schreiben: { aufgabe: "", text: "", laedt: false, fehler: "", ergebnis: null },
    schreibVorschlaege: [
      "Stell dich in 5 Sätzen vor.",
      "Schreib dem Vermieter, dass die Heizung kaputt ist.",
      "Beschreib dein letztes Wochenende.",
      "Bitte einen Handwerker per E-Mail um einen Kostenvoranschlag.",
    ],

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
      this.page = ["start", "lektion", "fortschritt", "wortschatz", "gespraech", "einstellungen"].includes(name) ? name : "start";
      this.info = "";
      if (this.page === "lektion") {
        // Die Lektion (lesson.js) lädt sich daraufhin selbst. setTimeout, damit
        // die Lektions-Komponente beim allerersten Laden schon bereit ist.
        setTimeout(() => window.dispatchEvent(new CustomEvent("lektion-laden")), 0);
      } else {
        Sprache.stopp();
        this.refresh();
        if (this.page === "fortschritt") this.ladeStatistik();
        if (this.page === "wortschatz") this.ladeWortschatz();
        if (this.page === "gespraech" && !this.chat.verlauf.length) setTimeout(() => this.chatNeu(), 300);
      }
    },

    // --- Gespräch mit Claude ---
    async chatAnfrage() {
      this.chat.laedt = true;
      this.chat.fehler = "";
      try {
        const r = await api("/api/ki/gespraech", {
          method: "POST",
          body: JSON.stringify({ thema: this.chat.thema, verlauf: this.chat.verlauf.map(({ rolle, text }) => ({ rolle, text })) }),
        });
        // Korrektur gehört zur letzten eigenen Nachricht
        const letzte = [...this.chat.verlauf].reverse().find((m) => m.rolle === "ich");
        if (letzte && r.korrektur) letzte.korrektur = r.korrektur;
        this.chat.verlauf.push({ rolle: "claude", text: r.antwort_pt, de: r.uebersetzung_de, zeigeDe: false });
        Sprache.sprechen(r.antwort_pt);
      } catch (e) {
        this.chat.fehler = e.message;
      }
      this.chat.laedt = false;
    },

    chatNeu() {
      if (!this.overview.claude_aktiv) return;
      this.chat.verlauf = [];
      this.chatAnfrage();
    },

    chatSenden() {
      const text = this.chat.eingabe.trim();
      if (!text || this.chat.laedt) return;
      this.chat.verlauf.push({ rolle: "ich", text });
      this.chat.eingabe = "";
      this.chatAnfrage();
    },

    async chatSprechen() {
      this.chat.hoert = true;
      try {
        const v = await Erkennung.hoeren();
        this.chat.eingabe = v[0];
      } catch (e) {
        this.chat.fehler = e.message;
      }
      this.chat.hoert = false;
    },

    async korrigieren() {
      this.schreiben.laedt = true;
      this.schreiben.fehler = "";
      this.schreiben.ergebnis = null;
      try {
        this.schreiben.ergebnis = await api("/api/ki/korrektur", {
          method: "POST", body: JSON.stringify({ text: this.schreiben.text, aufgabe: this.schreiben.aufgabe }),
        });
      } catch (e) {
        this.schreiben.fehler = e.message;
      }
      this.schreiben.laedt = false;
    },

    async ladeStatistik() {
      try { this.statistik = await api("/api/statistik"); } catch (e) { /* Hinweis kommt über refresh */ }
    },

    async ladeWortschatz() {
      const q = encodeURIComponent(this.suche || "");
      try { this.wortListe = await api(`/api/wortschatz?q=${q}&art=${this.wortArt}`); } catch (e) { /* s. o. */ }
    },

    // --- Helfer für die Diagramme ---
    maxMinuten() {
      const m = Math.max(...(this.statistik?.lernzeit.tage || []).map((t) => t.minuten), 0);
      return Math.max(40, m);   // Skala mindestens bis 40 Min., damit das 30-Min.-Ziel sichtbar ist
    },

    stufe(minuten) {
      if (!minuten) return 0;
      if (minuten < 10) return 1;
      if (minuten < 20) return 2;
      if (minuten < 30) return 3;
      return 4;
    },

    datumKurz(iso) {
      const [j, m, t] = iso.split("-");
      return `${Number(t)}.${Number(m)}.`;
    },

    prozent(wert) {
      return wert == null ? "–" : `${Math.round(wert * 100)} %`;
    },

    bereichName(skill) {
      return { hoeren: "Hören", lesen: "Lesen", schreiben: "Schreiben", sprechen: "Sprechen",
               wortschatz: "Wortschatz & Grammatik", gesamt: "Gesamt" }[skill] || skill;
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

    async stimmeTesten() {
      this.stimmenInfo = "Spiele ab …";
      await Sprache.sprechen("Olá! Bom dia. Vamos aprender português europeu.");
      this.stimmenInfo = Sprache.quelle === "server"
        ? "✓ Hochwertige Stimme (aus dem Internet geladen und gespeichert)."
        : "Gerade ohne Internet-Stimme – es spricht die Stimme des Mac.";
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
