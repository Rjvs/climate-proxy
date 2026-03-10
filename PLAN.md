# Implementation Plan: Climate Proxy — Gold Quality Level

## Summary of Current State

The codebase is a well-structured Home Assistant custom integration that proxies a physical climate entity. The current test suite covers happy paths for config flow (3 tests), enforcement (11 tests), offset calculator (12 tests), and state manager lifecycle (8 tests). The following gaps and bugs must be closed to reach Gold quality.

---

## Phase 0 — Critical Bug Fix (standalone commit)

**Goal:** Fix the Python 2-era `except` syntax that causes a `SyntaxError` on Python 3, preventing the entire integration from loading when any underlying device has a fan entity.

### Checklist

- [ ] Open `custom_components/climate_proxy/fan/proxy_entity.py`
- [ ] Navigate to line 311, change:
  ```python
  except ValueError, TypeError:
  ```
  to:
  ```python
  except (ValueError, TypeError):
  ```
- [ ] Verify no other Python 2-style `except` clauses exist in the codebase
- [ ] Run `pytest tests/fan/` to confirm fan tests still pass
- [ ] Commit: `"fix: correct Python 2 except syntax in fan/proxy_entity.py"`

---

## Phase 1 — Config Flow Server-Side Validation (ship with Phase 3a tests)

**Goal:** Prevent non-climate entities and proxy-chaining from being accepted, even when the UI is bypassed.

**Files:** `config_flow_handler/config_flow.py`, `strings.json`, `translations/en.json`

### 1a — Add validation in `async_step_user`

After the `self.hass.states.get(climate_entity_id) is None` check, add inside the `else` branch (before `async_set_unique_id`):

1. Domain check:
   ```python
   state = self.hass.states.get(climate_entity_id)
   if state.domain != "climate":
       errors[CONF_CLIMATE_ENTITY_ID] = "entity_not_climate"
   ```
2. Proxy chain prevention:
   ```python
   from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
   registry = async_get_entity_registry(self.hass)
   entity_entry = registry.async_get(climate_entity_id)
   if entity_entry is not None and entity_entry.platform == DOMAIN:
       errors[CONF_CLIMATE_ENTITY_ID] = "entity_is_proxy"
   ```
3. Only proceed to `async_set_unique_id` and beyond if `not errors`

### 1b — Mirror validation in `async_step_reconfigure`

Same two checks at the same logical position (after state existence confirmed, before `async_update_reload_and_abort`).

### 1c — Add error strings

In `strings.json` under `config.error`:
```json
"entity_not_climate": "The selected entity is not a climate entity. Please select a real thermostat.",
"entity_is_proxy": "The selected entity is itself a Climate Proxy. Chaining proxies is not supported."
```
Mirror in `translations/en.json`.

---

## Phase 2 — Enforcement Robustness (ship with Phase 3c tests)

**Goal:** Prevent crashes when the underlying device returns non-numeric values for temperature or humidity attributes.

**File:** `climate/enforcement.py`

### 2a — Guard `float()` calls

Three unguarded `float()` calls in `enforcement.py`:

- **Line 84** — `abs(float(actual_temp) - eff_temp)`:
  Wrap in `try/except (TypeError, ValueError)`. If conversion fails, treat `actual_temp` as `None` (force a correction since the value is unusable). Log at debug: `LOGGER.debug("Non-numeric temperature attribute '%s' on %s — forcing correction", actual_temp, underlying_state.entity_id)`

- **Lines 92–93** — `float(actual_low)` / `float(actual_high)`:
  Wrap each individually. On failure set to `None` so the existing `actual_low is None or actual_high is None` guard triggers naturally.

- **Line 104** — `abs(float(actual_humidity) - desired_target_humidity)`:
  Same pattern as line 84.

### 2b — Add LOGGER import

`LOGGER` is not currently imported in `enforcement.py`. Add it to the existing `from ..const import ...` line.

---

## Phase 3 — Test Coverage (largest body of work)

### Phase 3a — Config flow tests

**File:** `tests/test_config_flow.py`

- [ ] `test_config_flow_entity_not_climate` — submit `"switch.plug"`, assert form redisplayed with `entity_not_climate` in `result["errors"].values()`
- [ ] `test_config_flow_entity_is_proxy` — register entity in entity registry with `platform == DOMAIN`, assert `entity_is_proxy` error
- [ ] `test_config_flow_full_5_step_with_both_sensors` — full flow with both temperature and humidity sensors, assert correct `options` structure
- [ ] `test_reconfigure_flow_success` — change underlying entity, assert `ABORT` with `reconfigure_successful`, entry data updated
- [ ] `test_reconfigure_flow_entity_not_found` — non-existent entity, assert `entity_not_found` error
- [ ] `test_reconfigure_flow_entity_not_climate` — non-climate entity, assert `entity_not_climate` error
- [ ] `test_reconfigure_flow_entity_is_proxy` — proxy entity, assert `entity_is_proxy` error
- [ ] `test_options_flow_change_sensors` — update temp sensors via options flow, confirm stored in `entry.options`

### Phase 3b — Climate entity tests

**File:** `tests/climate/test_proxy_entity.py`

**`TestAsyncAddedToHass` class:**
- [ ] `test_with_underlying_present` — mock full climate state; assert capabilities extracted (fan_modes, preset_modes)
- [ ] `test_with_underlying_absent` — mock `states.get` returns `None`; assert entity stays available
- [ ] `test_with_underlying_unavailable` — mock `STATE_UNAVAILABLE` state; assert `underlying_was_unavailable is True`
- [ ] `test_restores_previous_desired_state` — mock `async_get_last_extra_data`; assert all desired keys restored

**`TestAsyncOnUnderlyingStateChanged` class:**
- [ ] `test_availability_change_clears_unavailable_flag`
- [ ] `test_unavailable_sets_flag`
- [ ] `test_current_readings_updated`

**`TestAsyncOnSensorChanged` class:**
- [ ] `test_offset_recalculated_when_sensors_configured`
- [ ] `test_no_offset_when_no_sensors`

**`TestAsyncSetTemperatureAdditional` class:**
- [ ] `test_set_temperature_single_pushes_to_device`
- [ ] `test_set_temperature_range_pushes_low_and_high`

### Phase 3c — Enforcement tests

**File:** `tests/climate/test_enforcement.py`

- [ ] `test_temperature_exactly_at_tolerance_no_correction` — `abs(diff) == TEMPERATURE_TOLERANCE`, assert no correction (check is `>`)
- [ ] `test_temperature_just_above_tolerance_correction` — `abs(diff) == TEMPERATURE_TOLERANCE + 0.001`, assert correction
- [ ] Same tolerance boundary pair for humidity
- [ ] `test_non_numeric_actual_temp_forces_correction` — `attrs = {"temperature": "n/a"}`, assert no crash + correction triggered
- [ ] `test_non_numeric_actual_low_forces_range_correction`
- [ ] `test_non_numeric_actual_humidity_forces_correction`
- [ ] `test_eff_temp_matches_underlying_no_correction` — `eff_temp` provided and matches underlying, assert no correction
- [ ] `test_eff_low_and_high_provided_uses_effective_range`
- [ ] `test_preset_correction_when_actual_preset_is_none`
- [ ] `test_fan_correction_when_actual_fan_is_none`
- [ ] `test_swing_correction_when_actual_swing_is_none`
- [ ] `test_all_corrections_simultaneously` — all 7 service call keys present

### Phase 3d — State manager tests

**File:** `tests/state_manager/test_manager.py`

**`TestClimateChangedHandler` class:**
- [ ] `test_pending_state_drained_on_reconnect`
- [ ] `test_enforcement_triggered_on_state_change`
- [ ] `test_enforcement_skipped_during_debounce`
- [ ] `test_pass_through_sensors_notified`

**`TestDebounce` class:**
- [ ] `test_second_correction_within_debounce_suppressed`
- [ ] `test_debounce_clears_after_sleep`
- [ ] `test_new_debounce_cancels_previous_task`

**`TestSensorChangedHandler` class:**
- [ ] `test_sensor_changed_notifies_climate_proxy`
- [ ] `test_sensor_changed_notifies_weighted_avg_entities`

### Phase 3e — Offset calculator edge cases

**File:** `tests/climate/test_offset_calculator.py`

- [ ] `test_all_sensors_entity_not_found_returns_none` — all `states.get()` return `None`
- [ ] `test_zero_weight_sensor_excluded`
- [ ] `test_exact_boundary_min_not_clamped`
- [ ] `test_exact_boundary_max_not_clamped`
- [ ] `test_range_no_offset_identity`

### Phase 3f — Integration tests

**File:** `tests/test_init.py`

- [ ] `test_setup_activates_fan_platform_when_underlying_has_fan`
- [ ] `test_setup_activates_only_climate_and_sensor_when_no_companions`
- [ ] `test_setup_when_underlying_unavailable` — assert setup succeeds, entry `LOADED`
- [ ] `test_reload_after_options_change` — trigger reload, assert re-enters `LOADED`

---

## Phase 4 — HA Gold Best Practices

### Phase 4a — `async_migrate_entry`

**File:** `custom_components/climate_proxy/__init__.py`

Add after `async_unload_entry`:
```python
async def async_migrate_entry(hass: HomeAssistant, config_entry: ClimateProxyConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    LOGGER.debug(
        "Migrating config entry %s from version %s.%s",
        config_entry.entry_id,
        config_entry.version,
        config_entry.minor_version,
    )
    # v1.1 is current — nothing to migrate yet
    return True
```

### Phase 4b — Diagnostics improvements

**File:** `custom_components/climate_proxy/diagnostics.py`

- [ ] Fetch actual underlying state and build `actual_state` snapshot
- [ ] Build per-sensor snapshot with current value and availability
- [ ] Compute `in_compliance: bool` (empty corrections dict = compliant)
- [ ] Add `_last_correction_time: datetime | None` to `ClimateProxyStateManager`, set in `_async_enforce_climate_state` when corrections found
- [ ] Expose `last_correction_time` in diagnostics output

---

## Phase 5 — README and Documentation

**File:** `README.md`

- [ ] Add CI test badge at top
- [ ] Add `## Troubleshooting` section covering:
  - Proxy device not appearing after setup
  - Thermostat not following proxy settings
  - Temperature reading seems incorrect
  - "The selected entity is itself a Climate Proxy" error
  - Proxy state not restored after restart
  - Entity availability model (proxy always available; underlying unavailable triggers pending-state queue)

---

## Execution Order

| Step | Phases | Rationale |
|------|--------|-----------|
| 1 | Phase 0 | Critical bug; standalone commit |
| 2 | Phase 1 + Phase 3a | Validation + its tests together |
| 3 | Phase 2 + Phase 3c | Enforcement fix + tests together |
| 4 | Phase 3b | Climate entity tests, independent |
| 5 | Phase 3d | State manager tests, independent |
| 6 | Phase 3e + 3f | Offset + integration tests |
| 7 | Phase 4 | Gold best practices after green suite |
| 8 | Phase 5 | Documentation last |
