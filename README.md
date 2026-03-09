# Climate Proxy

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

**Climate Proxy** is a Home Assistant custom integration that creates a virtual climate device sitting in front of a real physical thermostat. It acts as a "man in the middle": the proxy presents itself to Home Assistant like a full-featured climate device, enforces the user's settings on the underlying hardware, and optionally uses any room sensor — or a weighted average of several sensors — as the temperature or humidity reference instead of the thermostat's built-in sensor.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Rjvs/climate-proxy?quickstart=1)

---

## How It Works

```
User ──► Proxy entity ──► Real thermostat
              │
              └── Monitors real thermostat ──► corrects deviations immediately
              └── Reads external sensors ──► applies dynamic setpoint offset
```

1. **Proxy acts as the thermostat.** Every control (HVAC mode, temperature, fan mode, preset, swing, humidity) is handled by the proxy, which immediately pushes the command to the underlying device.
2. **Proxy enforces your settings.** Whenever the underlying thermostat changes state (e.g. reset by the device itself, a power cut, a direct interaction), the proxy detects the deviation and corrects it within seconds.
3. **Proxy absorbs unavailability.** If the underlying device goes offline, commands are queued and applied as soon as it comes back online. The proxy entity remains available throughout.
4. **External sensor offset.** When you select external temperature or humidity sensors, the proxy calculates the difference between the thermostat's own sensor and your reference sensors, then biases the physical setpoint to make the external location reach your desired temperature — effectively using the thermostat as a dumb actuator while the proxy provides the smart control.
5. **All other device entities are proxied too.** Switches, selects, numbers, binary sensors, buttons, and fans that belong to the same HA device as the underlying climate entity are automatically discovered and proxied with the same enforcement pattern.

---

## Features

- **UI-only setup** — no YAML configuration required
- **Dynamic capability mirroring** — the proxy exposes exactly the features the underlying thermostat supports: single/range temperature, fan modes, preset modes, vertical and horizontal swing, aux heat, and humidity control
- **Weighted average reference sensors** — pick any number of temperature or humidity sensors and assign weights to each; the proxy computes the weighted average as the reference reading
- **Setpoint offset calculation** — when external sensors are used, a dynamic offset keeps the physical device tracking the correct location
- **State restoration** — desired state is persisted across Home Assistant restarts
- **Diagnostics** — download a full state snapshot from the Devices & Services page

### Proxied Platforms

Platform | Behaviour
-- | --
`climate` | Full MitM proxy; enforces HVAC mode, temperatures, humidity, fan/preset/swing/aux heat
`sensor` | Pass-through; mirrors value, unit, device class, and state class without alteration
`binary_sensor` | Pass-through read-only mirror
`switch` | MitM; enforces desired on/off state
`select` | MitM; enforces desired option
`number` | MitM; enforces desired value (with tolerance)
`fan` | MitM; enforces on/off, percentage, and preset mode
`button` | Best-effort pass-through; presses forwarded immediately

---

## Installation

### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click **Custom repositories** and add `https://github.com/Rjvs/climate-proxy` as an **Integration**
3. Search for **Climate Proxy** and click **Download**
4. Restart Home Assistant

### Manual

1. Copy `custom_components/climate_proxy/` to your `config/custom_components/` directory
2. Restart Home Assistant

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Climate Proxy**
3. Follow the setup wizard:

   **Step 1 — Name & Thermostat**
   Give the proxy a friendly name and select the climate entity to wrap.

   **Step 2 — Temperature Sensors** *(optional)*
   Select one or more sensors to use as the reference temperature. Leave empty to use the thermostat's built-in sensor.

   **Step 3 — Temperature Weights** *(shown only if sensors were selected)*
   Assign a relative weight (0.1–10) to each temperature sensor. A sensor with weight 2 influences the average twice as much as one with weight 1.

   **Step 4 — Humidity Sensors** *(optional)*
   Same as Step 2 but for humidity.

   **Step 5 — Humidity Weights** *(shown only if sensors were selected)*
   Same as Step 3 but for humidity.

### Reconfiguring

To change the underlying thermostat or rename the proxy, go to **Settings → Devices & Services**, find the entry and click the **three-dot menu → Reconfigure**.

To update sensor selections after initial setup, click **Configure** on the integration entry.

---

## Sensor Weighting Example

Suppose you have two temperature sensors:

| Sensor | Room | Weight | Current reading |
|--------|------|--------|-----------------|
| `sensor.bedroom_temp` | Bedroom | 2 | 18 °C |
| `sensor.hallway_temp` | Hallway | 1 | 24 °C |

Weighted average = (18 × 2 + 24 × 1) / (2 + 1) = **20 °C**

The proxy displays 20 °C as the current temperature and uses it to calculate the setpoint offset sent to the physical thermostat.

---

## Setpoint Offset Calculation

When external sensors are used, the proxy calculates:

```
offset          = device_internal_temp - external_weighted_avg
device_setpoint = proxy_target + offset
```

**Example:** Device reads 23 °C internally, external reference reads 20 °C (offset = +3). User wants 22 °C at the reference location. The proxy tells the device to target 25 °C, so the device stops heating exactly when the external sensor reaches 22 °C.

---

## Diagnostics

Download a diagnostics snapshot from:
**Settings → Devices & Services → Climate Proxy → three-dot menu → Download diagnostics**

The snapshot includes the desired state, current offset, discovered entities, pending command queue, and debounce status.

---

## Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.climate_proxy: debug
```

---

## Contributing

Pull requests and issues are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) if it exists, or just open an issue.

### Local Development

```bash
git clone https://github.com/Rjvs/climate-proxy
cd climate-proxy
pip install -r requirements_test.txt
pytest tests/ -v
```

---

## License

MIT — see [LICENSE](LICENSE).

---

**Made with ❤️ by [@Rjvs][user_profile]**

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/Rjvs/climate-proxy.svg?style=for-the-badge
[commits]: https://github.com/Rjvs/climate-proxy/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/Rjvs/climate-proxy.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40Rjvs-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/Rjvs/climate-proxy.svg?style=for-the-badge
[releases]: https://github.com/Rjvs/climate-proxy/releases
[user_profile]: https://github.com/Rjvs
