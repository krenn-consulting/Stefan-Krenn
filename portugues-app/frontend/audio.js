// Sprachausgabe auf Portugiesisch (pt-PT).
//
// Etappe (b): Stimme des Mac über Chrome (Web Speech API).
// Etappe (c) ergänzt hochwertige Stimmen vom Server mit Zwischenspeicher.

const Sprache = {
  tempo: 1.0,
  stimmen: [],
  bereit: false,

  init() {
    if (!("speechSynthesis" in window)) return;
    const laden = () => {
      this.stimmen = speechSynthesis.getVoices().filter((v) => v.lang.replace("_", "-") === "pt-PT");
      this.bereit = true;
    };
    laden();
    speechSynthesis.addEventListener("voiceschanged", laden);
  },

  // Gibt es eine europäisch-portugiesische Stimme?
  hatStimme() {
    return this.stimmen.length > 0;
  },

  stopp() {
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  },

  // Spricht einen Text. stimme: "f" oder "m" (soweit vorhanden). Gibt ein Promise zurück,
  // das erfüllt wird, wenn der Text zu Ende gesprochen ist.
  sprechen(text, { stimme = "f", tempo = null } = {}) {
    return new Promise((fertig) => {
      if (!text || !("speechSynthesis" in window)) return fertig();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "pt-PT";
      u.rate = tempo ?? this.tempo;
      if (this.stimmen.length) {
        // Bei nur einer Stimme: für Männer etwas tiefer sprechen lassen
        u.voice = this.stimmen[stimme === "m" && this.stimmen.length > 1 ? 1 : 0];
        if (stimme === "m" && this.stimmen.length === 1) u.pitch = 0.8;
      }
      u.onend = fertig;
      u.onerror = fertig;
      speechSynthesis.speak(u);
    });
  },

  // Mehrere Zeilen nacheinander (Dialog)
  async dialog(zeilen, beiZeile = () => {}) {
    this.stopp();
    for (let i = 0; i < zeilen.length; i++) {
      beiZeile(i);
      await this.sprechen(zeilen[i].pt, { stimme: zeilen[i].stimme || "f" });
      await new Promise((r) => setTimeout(r, 350));
    }
    beiZeile(-1);
  },
};

Sprache.init();
