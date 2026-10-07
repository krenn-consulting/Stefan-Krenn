// Sprachausgabe und Spracherkennung auf Portugiesisch (pt-PT).
//
// Ausgabe: zuerst die hochwertigen Stimmen vom eigenen Server (edge-tts,
// zwischengespeichert). Klappt das nicht (z. B. kein Internet beim ersten
// Abspielen eines Satzes), spricht die Stimme des Mac ("Joana").
//
// Erkennung: Chrome-Spracherkennung (pt-PT). Braucht Internet und die
// Erlaubnis für das Mikrofon.

const Sprache = {
  tempo: 1.0,
  macStimmen: [],
  serverAusBis: 0,        // nach einem Fehler eine Weile direkt die Mac-Stimme nehmen
  aktuell: null,          // gerade spielendes <audio>
  quelle: "",             // "server" | "mac" | "" – für den Hinweis in den Einstellungen

  init() {
    if (!("speechSynthesis" in window)) return;
    const laden = () => {
      this.macStimmen = speechSynthesis.getVoices().filter((v) => v.lang.replace("_", "-") === "pt-PT");
    };
    laden();
    speechSynthesis.addEventListener("voiceschanged", laden);
  },

  hatMacStimme() {
    return this.macStimmen.length > 0;
  },

  stopp() {
    if (this.aktuell) {
      this.aktuell.pause();
      this.aktuell.dispatchEvent(new Event("ended"));
      this.aktuell = null;
    }
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  },

  // Spricht einen Text. stimme: "f", "m" oder "standard" (aus den Einstellungen).
  // Gibt ein Promise zurück, das erfüllt ist, wenn der Text zu Ende gesprochen ist.
  async sprechen(text, { stimme = "standard" } = {}) {
    if (!text) return;
    if (Date.now() > this.serverAusBis) {
      const ok = await this._server(text, stimme);
      if (ok) return;
      this.serverAusBis = Date.now() + 2 * 60 * 1000;   // 2 Minuten lang nicht erneut versuchen
    }
    await this._mac(text, stimme);
  },

  _server(text, stimme) {
    return new Promise((fertig) => {
      const a = new Audio(`/api/audio?stimme=${encodeURIComponent(stimme)}&text=${encodeURIComponent(text)}`);
      a.playbackRate = this.tempo;
      a.preservesPitch = true;
      this.aktuell = a;
      let erledigt = false;
      const ende = (ok) => {
        if (erledigt) return;
        erledigt = true;
        if (this.aktuell === a) this.aktuell = null;
        if (ok) this.quelle = "server";
        fertig(ok);
      };
      a.addEventListener("ended", () => ende(true));
      a.addEventListener("error", () => ende(false));
      a.play().catch(() => ende(false));
    });
  },

  _mac(text, stimme) {
    return new Promise((fertig) => {
      if (!("speechSynthesis" in window)) return fertig();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "pt-PT";
      u.rate = this.tempo;
      if (this.macStimmen.length) {
        u.voice = this.macStimmen[stimme === "m" && this.macStimmen.length > 1 ? 1 : 0];
        if (stimme === "m" && this.macStimmen.length === 1) u.pitch = 0.8;
      }
      this.quelle = "mac";
      u.onend = fertig;
      u.onerror = fertig;
      speechSynthesis.speak(u);
    });
  },

  // Mehrere Zeilen nacheinander (Dialog)
  async dialog(zeilen, beiZeile = () => {}) {
    this.stopp();
    const lauf = (this._lauf = (this._lauf || 0) + 1);
    for (let i = 0; i < zeilen.length; i++) {
      if (lauf !== this._lauf) return;     // inzwischen neu gestartet
      beiZeile(i);
      await this.sprechen(zeilen[i].pt, { stimme: zeilen[i].stimme || "f" });
      await new Promise((r) => setTimeout(r, 350));
    }
    beiZeile(-1);
  },

  // Audios einer Lektion im Voraus erzeugen lassen
  vorladen(eintraege) {
    if (!eintraege.length) return;
    fetch("/api/audio/vorladen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texte: eintraege }),
    }).catch(() => {});
  },
};

const Erkennung = {
  get verfuegbar() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  },

  // Hört einmal zu. Ergebnis: Liste möglicher Texte (beste zuerst).
  hoeren() {
    return new Promise((fertig, fehler) => {
      const Klasse = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Klasse) return fehler(new Error("Spracherkennung wird von diesem Browser nicht unterstützt. Bitte Google Chrome verwenden."));
      Sprache.stopp();
      const r = new Klasse();
      r.lang = "pt-PT";
      r.interimResults = false;
      r.maxAlternatives = 5;
      let ergebnis = null;
      let fehlerGemeldet = false;
      r.onresult = (e) => {
        ergebnis = Array.from(e.results[0]).map((alt) => alt.transcript);
      };
      r.onerror = (e) => {
        fehlerGemeldet = true;
        const texte = {
          "not-allowed": "Chrome darf das Mikrofon nicht benutzen. Klicke oben links in der Adresszeile auf das Schloss-Symbol und erlaube das Mikrofon.",
          "service-not-allowed": "Chrome darf das Mikrofon nicht benutzen (Systemeinstellungen → Datenschutz & Sicherheit → Mikrofon → Google Chrome).",
          "network": "Die Spracherkennung braucht Internet. Du kannst dich stattdessen selbst bewerten.",
          "no-speech": "Ich habe nichts gehört. Bitte noch einmal – etwas lauter und näher am Mikrofon.",
          "audio-capture": "Kein Mikrofon gefunden.",
        };
        fehler(new Error(texte[e.error] || "Spracherkennung fehlgeschlagen: " + e.error));
      };
      r.onend = () => {
        if (ergebnis) fertig(ergebnis);
        else if (!fehlerGemeldet) fehler(new Error("Ich habe nichts gehört. Bitte noch einmal versuchen."));
      };
      r.start();
    });
  },
};

Sprache.init();
