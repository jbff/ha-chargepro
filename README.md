# ChargePro Solar

A **Home Assistant** integration for HQST/Helios solar charge controllers
over Bluetooth, e.g. the HQST HP-2430N (24V 30A MPPT) used with the
"ChargePro 2.0" app. Exposes live measurements from the controller: battery
voltage/current, solar panel voltage/power, DC load draw, temperatures, and
energy totals.

The BLE protocol was reverse-engineered from
[ddrown/ble-solar](https://github.com/ddrown/ble-solar) (gatttool PoC for
InfluxDB) and re-implemented here natively for Home Assistant's managed
Bluetooth — see [PROTOCOL.md](PROTOCOL.md) for the wire format.

## Features

- **Sensors**: battery voltage & current (charge/discharge), solar panel
  voltage & power, DC load voltage/current/power, controller & battery
  temperature, energy charged today, plus diagnostic entities (lifetime
  energy totals, boost voltage, over-discharge voltage, error register)
- **Polls every 60 s** while **holding the BLE connection open** — important
  because the Helios BLE module only advertises in intermittent ~5-minute
  bursts, so per-poll reconnects would require chasing advertisements
- **Patient reconnection**: after a connection drop the coordinator falls
  back to HA's scanned-device cache and then an active scan, so it rides
  out the module's advertising duty-cycle without user intervention
- **Unauthenticated protocol** — no pairing, PIN, or cloud account needed

## Requirements

- A charge controller with the Helios/"ChargePro 2.0" Bluetooth module
  (tested: HQST HP-2430N; the app is also used with Helios/HQST/HQST-rebrand
  MPPT units — M2xxN/M4xxN family). BLE range of your Home Assistant
  Bluetooth adapter is required.

## Installation

### HACS

1. Add this repository as a custom repository:
   HACS → ⋮ → Custom repositories → `https://github.com/jbff/ha-chargepro`
   (type: Integration)
2. Download "ChargePro Solar" from HACS and restart Home Assistant.

### Manual

Copy `custom_components/chargepro_solar/` into the `custom_components/`
folder of your Home Assistant configuration, then restart Home Assistant.

## Setup

1. **Settings → Devices & services** — once the controller advertises (it
   does so in bursts; give it up to ~5 minutes, or briefly open/close the
   ChargePro 2.0 app to wake the module), you'll see **PVChargePro**
   discovered. Click **Add**.
2. Alternatively: **Add integration → ChargePro Solar** and enter the
   controller's MAC address (visible in the ChargePro 2.0 app or from a BLE
   scan).

No configuration beyond that: the integration connects and starts polling.

## Notes

- The controller serves **one BLE connection at a time**. While Home
  Assistant holds it, the ChargePro 2.0 app cannot connect (and vice versa
  — after using the app, HA reattaches automatically when the controller
  becomes reachable again).
- Temperature entities respect your Home Assistant unit system (°F in US
  units, °C in metric).
- The protocol writes are read-only queries; the integration never changes
  charger settings.

## License

MIT — see [LICENSE](LICENSE).