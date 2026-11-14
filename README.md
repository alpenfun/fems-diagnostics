
<p align="center">
  <img src="https://raw.githubusercontent.com/alpenfun/fems-diagnostics/main/docs/images/logo.png" width="260" alt="FEMS Diagnostics logo">
</p>

<h1 align="center">FEMS Diagnostics</h1>

<p align="center">
  Advanced diagnostics, battery health monitoring, and system visibility for FEMS in Home Assistant
</p>

<p align="center">
  <a href="https://github.com/alpenfun/fems-diagnostics/releases">
    <img src="https://img.shields.io/github/v/release/alpenfun/fems-diagnostics" alt="Latest release">
  </a>
<a href="https://github.com/alpenfun/fems-diagnostics/blob/main/LICENSE">
  <img src="https://img.shields.io/github/license/alpenfun/fems-diagnostics?cacheSeconds=300" alt="License">
</a>
  <a href="https://github.com/alpenfun/fems-diagnostics/issues">
    <img src="https://img.shields.io/github/issues/alpenfun/fems-diagnostics" alt="Issues">
  </a>
  <a href="https://github.com/alpenfun/fems-diagnostics/stargazers">
    <img src="https://img.shields.io/github/stars/alpenfun/fems-diagnostics" alt="Stars">
  </a>
  <img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS">
</p>

<p align="center">
  REST + Modbus integration • Battery health • Diagnostics dashboard
</p>

---

## 🇩🇪 Deutsche Zusammenfassung

**FEMS Diagnostics** ist eine inoffizielle Home Assistant Integration für die Diagnose und Überwachung von FEMS-basierten Energiesystemen.

### 🔧 Funktionen
- REST + Modbus Integration
- Batterie-Zustandsüberwachung
- Diagnose von Fehlern und Warnungen
- Spezielles Diagnose-Dashboard
- Automatische Erkennung vorhandener PV-Laderegler (auch Charger 2+)
- Gerätehierarchie kompatibel mit aktueller Home-Assistant-API

### 📥 Installation (Kurzfassung)
1. HACS installieren
2. Repository hinzufügen:
   https://github.com/alpenfun/fems-diagnostics
3. Integration installieren und Home Assistant neu starten

👉 Die vollständige Dokumentation befindet sich im englischen Hauptteil dieses README.

---

## 🇬🇧 English

# 🔋 FEMS Diagnostics for Home Assistant

**FEMS Diagnostics** is an unofficial Home Assistant integration focused on **diagnostics, health monitoring, and technical visibility** for FEMS-based energy systems.

It combines:
- 🌐 REST API data for status and diagnostics
- 🔌 Modbus data for technical real-time values
- 📊 a dedicated diagnostic dashboard for fast anomaly detection

> ⚠️ **Unofficial project**  
> This project is not affiliated with, endorsed by, or supported by FENECON GmbH.  
> All product names, trademarks, and brand names belong to their respective owners.

---

## ✨ Features

- 📡 Parallel REST + Modbus integration
- 🔋 Battery health and operating data
- ⚡ Charger / inverter values
- 🚨 Error, warning, and alarm diagnostics
- 📈 Energy counters and phase values
- 🧠 Derived system state: **OK / Warning / Error**
- 🔧 Configurable battery module count
- 🧩 Dashboard optimized for **diagnosis**, not just monitoring

---

## 🧪 Project focus

This integration is intentionally positioned as a **diagnostic and health tool**.

Focus areas:
- Zellgesundheit / cell health
- Spannungsabweichungen / voltage spread (ΔU / ΔV)
- Fehler- und Warnbilder / error and warning patterns
- Kommunikationsstatus / communication state

The goal is to help detect battery issues early instead of only showing general energy flows.

---

## 🖼️ Example dashboard

![FEMS Diagnostics Dashboard](https://raw.githubusercontent.com/alpenfun/fems-diagnostics/main/docs/images/dashboard.png)

A ready-to-use example dashboard YAML is included in this repository:

```text
docs/dashboard.yaml
```

It is based on the current diagnostic layout and uses the entity names provided by the integration.

The included example dashboard reflects the current recommended standard layout for diagnostics-focused daily use.

---

## 🎯 Dashboard design decision

**Per-cell voltages are intentionally not shown in the example dashboard.**

Why:
- too many entities for a compact diagnosis view
- slower visual interpretation
- module voltage spread plus min/max values are usually the better first indicator

The cell entities are still created by the integration and remain available for advanced users.

---

## 🟢 Status logic

⚠️ Cell voltage spread (ΔU / ΔV) interpretation

The cell voltage spread (ΔU / ΔV) is one of the key indicators used by this integration to assess battery health.

However, it is important to understand the following:

❗ Not an official manufacturer metric

The thresholds used in this integration:

Spread	Interpretation
< 0.02 V	uncritical
0.02 – 0.05 V	observe
> 0.05 V	critical

are engineering heuristics based on general lithium-ion battery behavior.

👉 They are NOT official thresholds from FENECON or any other manufacturer.

⚡ Strongly dependent on operating conditions

The spread between cell voltages is not constant and varies depending on system conditions.

Higher spread values can be completely normal during:

low state of charge (SOC)
charging phases
high load / discharge currents
transient system behavior

In particular:

A higher ΔU at low SOC does not necessarily indicate a battery defect.

🧠 Context-aware evaluation in this integration

To avoid false interpretations, this integration evaluates ΔU with context:

low SOC → separate status (low_soc)
high current → separate status (under_load)
missing context → not_evaluable

This helps prevent false "critical" indications under normal operating conditions.

📊 Recommendation for users
Do not evaluate ΔU based on a single measurement
Observe trends over time
Compare behavior at similar SOC levels
Use manufacturer tools for final diagnosis if needed
🚫 Important disclaimer

This integration is intended as a diagnostic aid.

It does not replace manufacturer diagnostics or official support.

If you suspect a real issue with your system, always consult the official FENECON service.

---

## 📦 Prerequisites

### 🧩 HACS (Home Assistant Community Store)

This integration and the example dashboard rely on HACS.

👉 HACS is required to install:
- this integration
- custom dashboard cards

Install HACS here:
👉 https://hacs.xyz/

👉 Without HACS, the integration and dashboard cannot be installed.

---

### 🎨 Dashboard dependencies

For the provided example dashboard you also need:

- 🍄 [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)
- 🔘 [button-card](https://github.com/custom-cards/button-card) by @RomRider

These can be installed directly via HACS.

The integration itself can run without the dashboard, but the provided example dashboard depends on those custom dashboard cards.

---

## 📥 Installation

### 1. Install HACS (if not already installed)

See the official HACS documentation.

### 2. Add this repository as a custom repository in HACS

![Installation über HACS](https://raw.githubusercontent.com/alpenfun/fems-diagnostics/main/docs/images/hacs_installation.png)

Use this repository URL:

```text
https://github.com/alpenfun/fems-diagnostics
```

Type:

```text
Integration
```

### 3. Search for the integration in HACS and install it

![FEMS Integration in HACS suchen](https://raw.githubusercontent.com/alpenfun/fems-diagnostics/main/docs/images/hacs_search.png)

### 4. Restart Home Assistant

### 5. Add the integration in Home Assistant

![FEMS einrichten](https://raw.githubusercontent.com/alpenfun/fems-diagnostics/main/docs/images/config_flow.png)

Required setup values:
- REST host
- REST port
- Modbus host
- Modbus port
- Modbus slave
- Battery module count
- Username
- Password

The configuration flow currently exposes these setup parameters directly in Home Assistant, including separate REST and Modbus endpoints and the configurable battery module count.

---

## 🧩 Created devices

The integration creates a hierarchy of logical devices:
- 🖥️ FEMS System
- 🔋 Battery
- ⚡ Charger devices discovered dynamically (Charger 0, Charger 1, Charger 2, etc., if available)
- 🧠 Diagnostics
- 📊 Energy management
- 🔬 Cells

---

## ⚙️ Configuration notes

During setup, the battery module count can be configured from **1 to 10**.  
This setting controls how many module spread and cell sensors are created.

> ⚠️ The current default value is a technical placeholder and must be adjusted to match the real system.

If the configured module count does not match the real system, diagnostic values may become misleading.

---

## 🛠️ Configuration options

The integration provides a small set of runtime options to balance update speed, diagnostic depth, and entity count.

### `scan_interval`
Controls how often the main sensor data is updated.

- Lower value = faster updates
- Higher value = lower system load

**Recommended default:** `30` seconds

Use a lower value only if you need faster updates in daily operation.

### `diagnostics_interval`
Controls how often health and diagnostic values are refreshed.

- Lower value = faster diagnostic updates
- Higher value = lower system load

**Recommended default:** `60` seconds

In most setups, diagnostics do not need to update as often as general power and status values.

### `battery_module_count`
Defines how many battery modules are installed in your system.

**Important:** This value must match your real physical battery configuration.

> ⚠️ This setting has a direct impact on sensor creation and diagnostic accuracy.

If the value is incorrect:
- expected sensors may be missing
- additional sensors may appear that do not exist
- diagnostic values may become misleading

**Default value:** `7` (placeholder only)

The default does not represent a recommended system size.

Typical real-world examples:
- 3 modules → small system (~6–7 kWh)
- 5 modules → common residential setup (~10 kWh)
- 7+ modules → larger systems

Always configure this value according to your actual installation.

### `enable_cell_voltages`
Enables creation of individual cell voltage entities.

- Enabled = maximum detail
- Disabled = fewer entities and lower overhead

**Recommended default:** `True`

Disable this option if you want to reduce the number of entities or keep the setup simpler.

---

## 📊 Dashboard setup

To use the included example dashboard:

1. Open the dashboard editor in Home Assistant
2. Switch to YAML mode if needed
3. Copy the content of:

```text
docs/dashboard.yaml
```

4. Paste it into your dashboard / view configuration

The provided dashboard view is currently named **FEMS Diagnostics** and includes status badges, KPI cards, module spread cards, compact health information, critical diagnostics, warnings, phase values, and energy counters.

For a step-by-step setup and customization guide, see:

👉 [Dashboard Setup and Customization Guide](./docs/dashboard_guide.md)

---

## 📡 Sensors and diagnostics

📘 **Detailed sensor explanations:**

👉 [Sensors and Diagnostics Guide](./sensors_and_diagnostics.md)

The integration provides, among other things:

### Battery
- SoC
- SoH
- current
- DC voltage
- pack voltage
- capacity
- cycle count

### Charger / inverter
- power
- voltage
- current

### Diagnostics
- fault status
- warning status
- alarm status
- communication state
- module spread per battery module
- per-cell voltage entities

### Derived binary states
- system OK
- system warning
- system error
- REST communication
- Modbus communication

Your current binary sensor implementation derives these overall health states from REST and Modbus availability plus fault, warning, and alarm signals.

---

## ⚡ Performance notes

The total entity count grows with the configured number of battery modules.

Important:
- more modules = more entities
- per-cell voltages are the largest contributor
- the first refresh can take noticeably longer than later updates
- REST is usually slower than Modbus

---

## 🛠️ Repository structure

Recommended structure:

```text
custom_components/fems/
docs/images/
docs/dashboard/
README.md
hacs.json
manifest.json
```

This README assumes the following documentation files exist:
- `docs/images/dashboard.png`
- `docs/images/hacs_installation.png`
- `docs/images/hacs_search.png`
- `docs/images/config_flow.png`
- `docs/dashboard.yaml`

---

## 🚧 Troubleshooting

If something is not working as expected, check the following first:

### 🔌 No data or sensors unavailable
- verify REST host and port
- verify Modbus host, port, and slave ID
- check credentials

### ⏳ Slow initialization
- initial startup can take longer due to REST requests
- large systems (many modules) create many entities

### ⚠️ Missing or incorrect values
- verify battery module count
- check if your system matches the configured setup

### 🔄 Integration not updating
- check Home Assistant logs
- verify network connectivity to the FEMS system

Most issues are caused by configuration mismatches or connectivity problems.

---

## 🛠️ Support and diagnostics

If you encounter issues with the integration, please follow these steps before opening an issue:

### 🔍 1. Check Home Assistant logs

Look for entries related to:

```text
custom_components.fems
```

Common indicators:

- connection issues (REST / Modbus)
- authentication problems
- timeout warnings

### 📊 2. Use integration diagnostics

This integration provides a built-in diagnostics function.

You can download diagnostics data via:

Home Assistant → Settings → Devices & Services → FEMS → Download diagnostics

The diagnostics include:

- sanitized configuration (no passwords)
- update status and timing
- REST and Modbus data snapshots

👉 This information is extremely helpful for debugging.

### 🧪 3. Verify system basics

Before reporting a bug, please ensure:

- REST endpoint is reachable
- Modbus connection is working
- credentials are correct
- battery module count matches your system

### 🐞 4. Open an issue

If the problem persists, please open an issue on GitHub.

Include:

- a clear description of the problem
- steps to reproduce
- relevant log excerpts
- diagnostics file (if possible)

👉 Please use the provided issue templates.

### 💡 Tip

Most issues are related to:

- incorrect endpoints or ports
- Modbus connectivity
- mismatched module configuration

Checking these first usually resolves the problem quickly.

---

## 🤝 Contributing

Feedback, issues, and pull requests are welcome.

---

## 📜 License

This project is licensed under the MIT License.

(Deutsch: Dieses Projekt steht unter der MIT-Lizenz – eine sehr freie Open-Source-Lizenz.)
