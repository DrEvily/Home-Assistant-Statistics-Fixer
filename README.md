# 🧰 Home Assistant Statistics Fixer (SQLite)

> 🇩🇪 Deutsch · 🇬🇧 English below

---

## 🇩🇪 Übersicht

**HA Statistics Fixer** ist ein Python-Tool mit GUI zur komfortablen Bearbeitung von Statistikdaten in **Home Assistant** (z. B. Energie- oder Zählerdaten).  
Fehlerhafte Modbus- oder Messwertausreißer können zu falschen Integralen oder Monatswerten führen – dieses Tool behebt das direkt in der SQLite-Datenbank (`home-assistant_v2.db`).

### ✨ Funktionen
- 🪟 **GUI (Tkinter)** – keine Kommandozeile nötig  
- 🕒 **Zeitfensterkorrektur:** Anfangs- und Endzeit (lokal oder UTC-basiert)  
- 📊 **Spaltenauswahl:** `sum`, `state` oder `both`  
- 🔎 **Diagnose & Vorschau:** zeigt Werte *vor, im und nach* dem gewählten Zeitraum  
- 💾 **Automatisches Backup** vor jeder Änderung  
- ⚙️ **Optional:** auch `statistics_short_term` anpassen  

---

## 🖥️ Installation

```bash
# 1. Python >= 3.10 erforderlich
python --version

# 2. Datei herunterladen
wget https://github.com/DrEvily/Home-Assistant-Statistics-Fixer/blob/main/ha_stats_fixer.py

# 3. (Optional) Abhängigkeiten sicherstellen
pip install tk zoneinfo

# 4. Tool starten
python ha_stats_fixer.py
```

---

## 🧩 Verwendung

1. **Home Assistant stoppen**, bevor du die Datenbank öffnest.  
2. In der GUI:
   - **DB-Pfad:** z. B. `/config/home-assistant_v2.db`
   - **Entity ID:** `sensor.pv_sg_meter_monthly`
   - **Startzeit:** `2025-09-01 00:00`
   - **Endzeit (optional, exklusiv):** `2025-10-01 00:00`
   - **Columns to adjust:** `state`, `sum` oder `both`
   - **Offset:** z. B. `-3000` (entfernt 3000 kWh)
3. **Preview** → Zeigt betroffene Zeilen  
4. **Diagnose** → Prüft Daten im Zeitraum  
5. **Apply Correction** → Änderungen ausführen  
6. **Home Assistant neu starten** und **Browsercache leeren**

---

## ⚠️ Sicherheit

- Das Tool erstellt **automatisch ein Backup**:  
  `home-assistant_v2.db.YYYYMMDD-HHMMSS.bak`  
- Während der Nutzung darf Home Assistant **nicht laufen!**  
- Rückgängig machen:
  ```bash
  cp home-assistant_v2.db.20251026-153000.bak home-assistant_v2.db
  ```

---

## 🧾 Beispiel

```yaml
chart_type: bar
period: month
type: statistics-graph
entities:
  - sensor.pv_sg_meter_monthly
stat_types:
  - state
```

Korrektur:
- Start: `2025-09-01 00:00`
- Ende: `2025-10-01 00:00`
- Columns: `state`
- Offset: `-3000`

→ Nach Neustart zeigt das Diagramm den korrekten September-Wert.

---

## 📸 Screenshots
*(Optional – hier eigene Bilder hinzufügen)*  
- **Hauptfenster:** ![GUI Preview](./screenshots/gui_main.png)  
- **Diagnose-Ansicht:** ![Diagnose Output](./screenshots/diagnose.png)

---

## 🧑‍💻 Autor & Lizenz
**Autor:** DrEvily  
**Lizenz:** MIT – Nutzung auf eigene Gefahr.

---

---

# 🇬🇧 Overview

**HA Statistics Fixer** is a Python GUI tool for editing **Home Assistant** statistical data (e.g. energy or meter readings) directly in the SQLite database.

Useful when occasional Modbus or sensor glitches produce unrealistic jumps that distort total or monthly values.

---

## ✨ Features
- 🪟 **Tkinter GUI** – no command line required  
- 🕒 **Time-window corrections:** start and optional end (local or UTC)  
- 📊 **Column selection:** `sum`, `state`, or `both`  
- 🔍 **Diagnosis & preview:** view values *before, inside, and after* your time range  
- 💾 **Automatic backup** before applying any changes  
- ⚙️ **Optional:** updates `statistics_short_term` as well  

---

## 🖥️ Installation

```bash
# 1. Requires Python >= 3.10
python --version

# 2. Download
wget https://github.com/DrEvily/Home-Assistant-Statistics-Fixer/blob/main/ha_stats_fixer.py

# 3. Ensure tkinter and zoneinfo are available
pip install tk zoneinfo

# 4. Run the app
python ha_stats_fixer.py
```

---

## 🧩 Usage

1. **Stop Home Assistant** before opening the database.  
2. Fill in:
   - **DB path:** `/config/home-assistant_v2.db`
   - **Entity ID:** e.g. `sensor.pv_sg_meter_monthly`
   - **Start time:** `2025-09-01 00:00`
   - **End time (optional, exclusive):** `2025-10-01 00:00`
   - **Columns to adjust:** `sum`, `state`, or `both`
   - **Offset:** e.g. `-3000`
3. Click **Preview** → review affected rows  
4. **Diagnose** → inspect surrounding data  
5. **Apply Correction** → changes with backup  
6. **Restart Home Assistant** + hard refresh UI  

---

## ⚠️ Safety Notes
- Automatically creates backups before every write:
  ```
  home-assistant_v2.db.YYYYMMDD-HHMMSS.bak
  ```
- Do **not** run Home Assistant during modification.  
- Restore from backup anytime:
  ```bash
  cp home-assistant_v2.db.20251026-153000.bak home-assistant_v2.db
  ```

---

## 🧾 Example

```yaml
chart_type: bar
period: month
type: statistics-graph
entities:
  - sensor.pv_sg_meter_monthly
stat_types:
  - state
```

To fix the September jump:
- Start: `2025-09-01 00:00`
- End: `2025-10-01 00:00`
- Columns: `state`
- Offset: `-3000`

After restarting HA, the September bar will display correctly.


---

## 🧑‍💻 Author & License
**Author:** DrEvily
**License:** MIT  
Use at your own risk. Back up before modifying databases.
