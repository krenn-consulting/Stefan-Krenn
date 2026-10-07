// Ablauf einer Lektion: Blöcke nacheinander, in jedem Block die Schritte
// nacheinander. Ein Schritt = ein Bildschirm.

const AKZENTE = ["á", "à", "â", "ã", "ç", "é", "ê", "í", "ó", "ô", "õ", "ú"];

function lektion() {
  return {
    plan: null,
    ladeFehler: "",
    bi: 0,              // aktueller Block (Index)
    queue: [],          // Schritte des aktuellen Blocks (falsche Karten kommen ans Ende)
    si: 0,              // aktueller Schritt (Index)
    phase: "frage",     // frage | feedback
    eingabe: "",
    gewaehlt: null,     // Auswahl-Index
    satz: [],           // Satzbau: gewählte Wörter
    rest: [],           // Satzbau: noch verfügbare Wörter
    feedback: null,     // {ergebnis, loesung, hinweis}
    textZeigen: false,
    uebersetzungZeigen: false,
    sprichtZeile: -1,
    blockStart: 0,
    schrittStart: 0,
    restSekunden: 0,
    timer: null,
    zusammenfassung: null,
    bewertung: 0,
    ergebnis: null,     // nach dem Abschließen
    akzente: AKZENTE,
    hoertZu: false,     // Mikrofon aktiv
    erkannt: "",        // was die Spracherkennung verstanden hat
    sprachFehler: "",
    perSprache: false,  // Antwort wurde gesprochen statt getippt
    erkennungDa: Erkennung.verfuegbar,

    // ---------- Laden und Blöcke ----------

    async laden() {
      this.ergebnis = null;
      this.plan = null;
      this.ladeFehler = "";
      const modus = location.hash.includes("wiederholung") ? "wiederholung" : "lektion";
      try {
        this.plan = await api(`/api/lektion?modus=${modus}`);
      } catch (e) {
        this.ladeFehler = e.message;
        return;
      }
      this.audioVorladen();
      // Mit dem ersten noch offenen Block weitermachen (die App merkt sich den Stand)
      const offen = this.plan.bloecke.findIndex((b) => !b.status && b.id !== "abschluss");
      this.blockStarten(offen >= 0 ? offen : this.plan.bloecke.length - 1);
      this.timer = this.timer || setInterval(() => this.tick(), 1000);
    },

    // Alle Sätze der Lektion schon einmal beim Server bestellen
    audioVorladen() {
      const liste = [];
      const dazu = (text, stimme = "standard") => text && liste.push({ text, stimme });
      for (const b of this.plan.bloecke) {
        for (const s of b.schritte) {
          dazu(s.pt); dazu(s.beispiel_pt); dazu(s.audio);
          if (s.loesungen) dazu(s.loesungen[0]);
          for (const z of s.zeilen || []) dazu(z.pt, z.stimme || "f");
          for (const z of s.kontext || []) dazu(z.pt, z.stimme || "f");
          for (const x of s.beispiele || []) dazu(x.pt);
        }
      }
      Sprache.vorladen(liste);
    },

    verlassen() {
      Sprache.stopp();
      clearInterval(this.timer);
      this.timer = null;
      this.plan = null;
      location.hash = "#/";
    },

    get block() {
      return this.plan?.bloecke[this.bi];
    },

    get schritt() {
      return this.queue[this.si];
    },

    blockStarten(index) {
      Sprache.stopp();
      this.bi = index;
      this.queue = [...this.block.schritte];
      this.si = 0;
      this.blockStart = Date.now();
      this.restSekunden = Math.round(this.block.minuten * 60);
      this.zusammenfassung = null;
      if (this.block.id === "abschluss") {
        this.abschlussLaden();
        return;
      }
      if (this.queue.length === 0) {
        const texte = {
          wiederholung: "Heute sind keine Wiederholungen fällig. Stark! 💪",
          wortschatz: "In dieser Lektion gibt es keine neuen Wörter.",
        };
        this.queue = [{ typ: "leer", text: texte[this.block.id] || "Für diesen Block gibt es heute nichts zu tun." }];
      }
      this.schrittBeginnen();
    },

    async blockBeenden(status) {
      Sprache.stopp();
      const sekunden = Math.round((Date.now() - this.blockStart) / 1000);
      try {
        await api(`/api/lektion/${this.plan.id}/block`, {
          method: "POST",
          body: JSON.stringify({ block: this.block.id, status, sekunden }),
        });
      } catch (e) { /* Weiterlernen ist wichtiger als die Statistik */ }
      this.block.status = status;
      // Nächster offener Block nach diesem, sonst Abschluss
      let naechster = this.plan.bloecke.findIndex((b, i) => i > this.bi && !b.status && b.id !== "abschluss");
      if (naechster < 0) naechster = this.plan.bloecke.length - 1;
      this.blockStarten(naechster);
    },

    ueberspringen() {
      this.blockBeenden("uebersprungen");
    },

    tick() {
      if (!this.plan || this.block?.id === "abschluss") return;
      this.restSekunden -= 1;
    },

    get zeitText() {
      const s = Math.abs(this.restSekunden);
      const t = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
      return this.restSekunden < 0 ? `+${t}` : t;
    },

    get fortschritt() {
      if (!this.queue.length) return 0;
      return Math.min(100, Math.round((this.si / this.queue.length) * 100));
    },

    // ---------- Schritte ----------

    schrittBeginnen() {
      this.phase = "frage";
      this.eingabe = "";
      this.gewaehlt = null;
      this.feedback = null;
      this.textZeigen = false;
      this.uebersetzungZeigen = false;
      this.hoertZu = false;
      this.erkannt = "";
      this.sprachFehler = "";
      this.perSprache = false;
      this.schrittStart = Date.now();
      const s = this.schritt;
      if (!s) return;
      if (s.typ === "satzbau") {
        this.satz = [];
        this.rest = s.woerter.map((w, i) => ({ w, i }));
      }
      // Ton automatisch abspielen, wo er zur Aufgabe gehört
      if (s.typ === "vokabel" || s.typ === "nachsprechen" || (s.typ === "eingabe" && s.art === "diktat")) {
        setTimeout(() => this.abspielen(), 300);
      }
      // Rollenspiel: die Zeilen des Gegenübers vorlesen, dann bist du dran
      if (s.typ === "eingabe" && s.art === "rolle" && s.kontext.length) {
        setTimeout(() => Sprache.dialog(s.kontext), 300);
      }
      this.$nextTick(() => this.$root.querySelector("[data-fokus]")?.focus());
    },

    weiter() {
      Sprache.stopp();
      // Wiederholungsblock: Wenn die Zeit um ist, nach diesem Schritt aufhören.
      // Nicht geschaffte Karten bleiben fällig und kommen morgen.
      if (this.block.id === "wiederholung" && this.plan.modus === "lektion" && this.restSekunden <= 0) {
        this.blockBeenden("fertig");
        return;
      }
      this.si += 1;
      if (this.si >= this.queue.length) {
        this.blockBeenden("fertig");
      } else {
        this.schrittBeginnen();
      }
    },

    // Text, der mit der Leertaste abgespielt wird
    get audioText() {
      const s = this.schritt;
      if (!s) return "";
      if (s.typ === "vokabel" || s.typ === "nachsprechen") return s.pt;
      if (s.typ === "eingabe" && s.art === "diktat") return s.audio;
      if (this.phase === "feedback") return this.feedback?.loesung || s.audio || "";
      if (s.typ === "auswahl") return s.audio || "";
      return "";
    },

    abspielen() {
      const s = this.schritt;
      if (s?.typ === "dialog") return this.dialogAbspielen();
      Sprache.stopp();
      Sprache.sprechen(this.audioText);
    },

    dialogAbspielen() {
      Sprache.dialog(this.schritt.zeilen, (i) => (this.sprichtZeile = i));
    },

    sprecheZeile(z) {
      Sprache.stopp();
      Sprache.sprechen(z.pt, { stimme: z.stimme || "f" });
    },

    akzentEinfuegen(zeichen) {
      const feld = this.$root.querySelector("[data-fokus]");
      if (!feld) return;
      const a = feld.selectionStart ?? this.eingabe.length;
      const b = feld.selectionEnd ?? this.eingabe.length;
      this.eingabe = this.eingabe.slice(0, a) + zeichen + this.eingabe.slice(b);
      this.$nextTick(() => {
        feld.focus();
        feld.setSelectionRange(a + 1, a + 1);
      });
    },

    // ---------- Antworten ----------

    get istFrage() {
      return ["eingabe", "auswahl", "satzbau"].includes(this.schritt?.typ);
    },

    async pruefenEingabe(text, varianten = null) {
      const daten = varianten
        ? { modus: "sprechen", varianten, loesungen: this.schritt.loesungen }
        : { antwort: text, loesungen: this.schritt.loesungen };
      try {
        this.feedback = await api("/api/pruefen", { method: "POST", body: JSON.stringify(daten) });
      } catch (e) {
        alert("Prüfen hat nicht geklappt: " + e.message);
        return;
      }
      this.phase = "feedback";
      Sprache.sprechen(this.feedback.loesung);
    },

    pruefen() {
      const s = this.schritt;
      if (this.phase !== "frage") return;
      if (s.typ === "eingabe") {
        if (!this.eingabe.trim()) return;
        // Gesprochen und nicht mehr verändert → großzügige Sprach-Prüfung
        if (this.perSprache && this.eingabe === this.erkannt) this.pruefenEingabe(this.eingabe, [this.eingabe]);
        else this.pruefenEingabe(this.eingabe);
      } else if (s.typ === "satzbau") {
        if (!this.satz.length) return;
        this.pruefenEingabe(this.satz.map((x) => x.w).join(" "));
      }
    },

    waehlen(index) {
      if (this.phase !== "frage") return;
      const s = this.schritt;
      this.gewaehlt = index;
      const ok = index === s.richtig;
      this.feedback = { ergebnis: ok ? "richtig" : "falsch", loesung: s.optionen[s.richtig], hinweis: "" };
      this.phase = "feedback";
      if (s.audio) Sprache.sprechen(s.audio);
    },

    satzWort(x) {
      if (this.phase !== "frage") return;
      this.rest = this.rest.filter((r) => r !== x);
      this.satz.push(x);
    },

    satzZurueck(x) {
      if (this.phase !== "frage") return;
      this.satz = this.satz.filter((r) => r !== x);
      this.rest.push(x);
    },

    trotzdemRichtig() {
      // Für den Fall, dass deine Antwort auch stimmt (z. B. ein Synonym)
      this.feedback = { ...this.feedback, ergebnis: "richtig", korrigiert: true };
    },

    // ---------- Mikrofon ----------

    async zuhoeren() {
      if (this.hoertZu || this.phase !== "frage") return;
      this.sprachFehler = "";
      this.hoertZu = true;
      let varianten;
      try {
        varianten = await Erkennung.hoeren();
      } catch (e) {
        this.sprachFehler = e.message;
        return;
      } finally {
        this.hoertZu = false;
      }
      this.erkannt = varianten[0];
      const s = this.schritt;
      if (s.typ === "nachsprechen") {
        // Nachsprechen: direkt mit dem Zielsatz vergleichen
        try {
          this.feedback = await api("/api/pruefen", {
            method: "POST",
            body: JSON.stringify({ modus: "sprechen", varianten, loesungen: [s.pt] }),
          });
          this.erkannt = this.feedback.erkannt || this.erkannt;
          this.phase = "feedback";
        } catch (e) {
          this.sprachFehler = e.message;
        }
      } else {
        // Eingabefeld mit dem Gesprochenen füllen – du kannst es noch korrigieren
        this.eingabe = this.erkannt;
        this.perSprache = true;
      }
    },

    // Nach der Mikrofon-Prüfung beim Nachsprechen
    async weiterNachSprechen() {
      await this.antwortSpeichern(this.erkannt);
      this.weiter();
    },

    // Selbstbewertung beim Nachsprechen
    selbst(gut) {
      this.feedback = { ergebnis: gut ? "richtig" : "falsch" };
      this.antwortSpeichern("").then(() => this.weiter());
    },

    async antwortSpeichern(antwort) {
      const s = this.schritt;
      if (!s?.ref) return;
      try {
        await api("/api/antwort", {
          method: "POST",
          body: JSON.stringify({
            lesson_id: this.plan.id, block: this.block.id, ergebnis: this.feedback.ergebnis,
            antwort, dauer_ms: Date.now() - this.schrittStart, schritt: s,
          }),
        });
      } catch (e) { /* nicht blockieren */ }
      // Falsch beantwortete Karten kommen im selben Block noch einmal (einmalig)
      if (this.feedback.ergebnis === "falsch" && ["wiederholung", "wortschatz"].includes(this.block.id) && !s.nochmal) {
        this.queue.push({ ...s, nochmal: true });
      }
    },

    async weiterNachFeedback() {
      const s = this.schritt;
      const antwort = s.typ === "satzbau" ? this.satz.map((x) => x.w).join(" ")
        : s.typ === "auswahl" ? s.optionen[this.gewaehlt] : this.eingabe;
      await this.antwortSpeichern(antwort);
      this.weiter();
    },

    // Enter: prüfen bzw. weiter
    enter() {
      const s = this.schritt;
      if (!s || this.block?.id === "abschluss") return;
      if (this.istFrage) {
        if (this.phase === "frage") this.pruefen();
        else this.weiterNachFeedback();
      } else if (s.typ === "nachsprechen") {
        if (this.phase === "feedback") this.weiterNachSprechen();
      } else {
        this.weiter();
      }
    },

    taste(e) {
      if (!this.plan || location.hash.indexOf("#/lektion") !== 0) return;
      const imFeld = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
      if (e.key === "Enter") {
        e.preventDefault();
        this.enter();
      } else if (e.key === " " && !imFeld) {
        e.preventDefault();
        this.abspielen();
      } else if (!imFeld && (e.key === "m" || e.key === "M") && this.erkennungDa &&
                 (this.schritt?.typ === "nachsprechen" || this.schritt?.typ === "eingabe")) {
        e.preventDefault();
        this.zuhoeren();
      } else if (!imFeld && this.schritt?.typ === "auswahl" && /^[1-9]$/.test(e.key)) {
        const i = Number(e.key) - 1;
        if (this.phase === "frage" && i < this.schritt.optionen.length) this.waehlen(i);
      }
    },

    // ---------- Abschluss ----------

    async abschlussLaden() {
      try {
        this.zusammenfassung = await api(`/api/lektion/${this.plan.id}/zusammenfassung`);
      } catch (e) {
        this.zusammenfassung = { gesamt: 0, gut: 0, woerter: [], fehler: [] };
      }
    },

    get uebersprungen() {
      return (this.plan?.bloecke || []).filter((b) => b.status === "uebersprungen");
    },

    nachholen(blockId) {
      const i = this.plan.bloecke.findIndex((b) => b.id === blockId);
      if (i >= 0) this.blockStarten(i);
    },

    async abschliessen() {
      const sekunden = Math.round((Date.now() - this.blockStart) / 1000);
      try {
        this.ergebnis = await api(`/api/lektion/${this.plan.id}/abschluss`, {
          method: "POST",
          body: JSON.stringify({ selbsteinschaetzung: this.bewertung || null, sekunden }),
        });
      } catch (e) {
        alert("Speichern hat nicht geklappt: " + e.message);
        return;
      }
      this.block.status = "fertig";
      clearInterval(this.timer);
      this.timer = null;
    },

    prozent(wert) {
      return wert == null ? "–" : `${Math.round(wert * 100)} %`;
    },

    statusSymbol(b, i) {
      if (i === this.bi && !this.ergebnis) return "▶";
      if (b.status === "fertig") return "✓";
      if (b.status === "uebersprungen") return "↷";
      return "";
    },
  };
}
