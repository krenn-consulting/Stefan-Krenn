# Português-App – so startest du sie

1. Den Ordner `portugues-app` an einen festen Ort legen, z. B. in „Dokumente".
2. **Start.command** doppelklicken. Beim ersten Mal richtet sich alles selbst ein (ca. 2–5 Min., Internet nötig), danach öffnet sich Chrome mit der App.
3. **Beenden:** das Terminalfenster schließen (Frage „Beenden?" bestätigen) oder **Stop.command** doppelklicken.
4. **Blockiert macOS den Start** („nicht verifizierter Entwickler“ o. Ä.): Terminal öffnen (⌘+Leertaste, „Terminal“), `bash ` tippen (mit Leerzeichen), Start.command ins Fenster ziehen, Enter. Das klappt immer; danach geht auch der Doppelklick. Alternative: Systemeinstellungen → Datenschutz & Sicherheit → ganz unten „Dennoch öffnen“.
5. **Ins Dock legen:** In Chrome bei geöffneter App oben rechts auf ⋮ → „Streamen, speichern und teilen" → „Seite als App installieren…". Dann Rechtsklick auf das neue Symbol im Dock → „Optionen" → „Im Dock behalten". (Vorher muss Start.command laufen.)
6. **Mikrofon:** Chrome fragt beim ersten Sprechen nach Erlaubnis → „Zulassen“. Die Stimmen brauchen Internet; offline spricht die Mac-Stimme.
7. Dein Lernstand liegt in `data/` und wird täglich automatisch gesichert. Zusätzlich: Einstellungen → „Lernstand exportieren".
8. Optional (Claude für Gespräche und Textkorrektur): `einstellungen.beispiel.env` kopieren, die Kopie `einstellungen.env` nennen und den API-Key eintragen.
