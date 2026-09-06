# API144 laundry controls — 1.3.1 compatibility fork

Branch `compatibility/1.3.1-api144-laundry-controls`, baselined at the
real, tagged `1.3.1` release
(`https://github.com/abmantis/whirlpool-sixth-sense`, tag `1.3.1`) — this
is the exact version Home Assistant Core 2026.8.3's built-in `whirlpool`
integration pins in its manifest (`whirlpool-sixth-sense==1.3.1`), and
therefore the exact version Adam's installation actually uses. This
corrects Phase 5F, whose `feature/api144-laundry-controls` branch was
baselined against commit `33dce79` (post-`2.0.1`), which Adam does not
run. **The Phase 5F branch is preserved, not deleted** - it remains
relevant as a forward-port for whenever HA Core eventually adopts 2.x.

## Architecture difference from the 2.x fork (read this first)

At `1.3.1`, `whirlpool.washer.Washer` and `whirlpool.dryer.Dryer` are
**single concrete classes** inheriting directly from `Appliance` - there
is no `whirlpool.httpapi` / `whirlpool.awsiot` transport split at all (no
AWS-IoT implementation exists yet at this version). `send_attributes()`,
`has_attribute()`, `_get_attribute()`, and `attr_value_to_bool()` all live
directly on `whirlpool.appliance.Appliance`, same as in 2.x.

This directly answers Phase 5F.1's question of whether these new methods
belong on a common abstract interface or an implementation-specific one:
**at 1.3.1, there is no second implementation to accidentally force into
advertising unsupported functionality, so the question doesn't arise.**
`LaundryCommandsMixin` is mixed directly into the one existing concrete
`Washer`/`Dryer` classes - no abstract method declarations were added
anywhere, unlike the 2.x fork (which added `@abstractmethod` stubs to
`whirlpool.washer.Washer`/`whirlpool.dryer.Dryer` and `NotImplementedError`
overrides to the AWS-IoT stubs, because 2.x's ABC/concrete split makes
that necessary there). This is the smaller, more accurate change for this
baseline, per the instruction to prefer the smallest public API expansion
that accurately represents supported functionality.

## What changed

- **`whirlpool/_laundry_commands.py`** (new): `LaundryCommandsMixin`,
  providing `get_remote_control_enabled()`, `start()`, `pause()`,
  `resume()`, `cancel()`. Same wire attributes and values as the 2.x
  fork: `XCat_RemoteSetRemoteControlEnable` (read-only), and
  `Cavity_OpSetOperations` = 1 (Cancel) / 2 (Start) / 5 (Pause) /
  6 (Resume) - proven against a live DDM capture from a WFW9620HBK3
  washer and WED9620HBK2 dryer; `3` (SetOnDisplay), `9` (Save),
  `10` (SaveAndStart), `1001` (Modify) remain unexposed, same as before.
- **`whirlpool/washer.py`**, **`whirlpool/dryer.py`**: `Washer`/`Dryer`
  now inherit `LaundryCommandsMixin` in addition to `Appliance`. No other
  line in either file changed.
- **`tests/test_washer.py`**, **`tests/test_dryer.py`**: added
  `get_remote_control_enabled()` assertion to `test_attributes` (fixture
  data already has Remote Control disabled for both test appliances -
  `False` was asserted, not assumed); added a parametrized
  `test_command_setters` mirroring the existing, real
  `tests/test_aircon.py::test_setters` pattern exactly (same
  `aiointercept_mock`/`assert_called_with` idiom, already proven in this
  repository for `Aircon.set_mode` etc. - this is not a new testing
  pattern, it's reuse of an existing one); added
  `test_command_blocked_before_first_fetch`; added
  `test_no_remote_control_enable_setter` (reflection-based safety test).
- **`tests/manual_smoke_test_131.py`** (new): dependency-free, but unlike
  Phase 5F's `tests/manual_smoke_test.py` (which used a hand-written
  `FakeLaundryAppliance` standing in for the mixin), this one imports and
  instantiates the REAL `whirlpool.washer.Washer` / `whirlpool.dryer.Dryer`
  classes against a fake `aiohttp` session, so it exercises actual
  production code (`Appliance.send_attributes` and real JSON body
  construction), not a stand-in. 13/13 checks pass; full output is in the
  implementation report.
- **`pyproject.toml`**: version bumped from `"1.3.1"` to `"1.3.1.post1"` -
  **not** for a local `pip install -e` reason like the 2.x fork, but so
  Home Assistant's dependency installer can tell this patched copy apart
  from the real, unpatched, already-installed PyPI `1.3.1` (HA's
  installer satisfies a requirement by version-string comparison only;
  see the paired HA integration fork's CHANGES.md, "Dependency strategy",
  for the full explanation).

## What did NOT change

No transport, endpoint, auth, `fetch_data()`, or `send_attributes()`
change. No other appliance type touched. No AWS-IoT anything (it doesn't
exist at this baseline). No setter for Remote Enable anywhere - enforced
by `test_no_remote_control_enable_setter` in both test files and by the
reflection check in `manual_smoke_test_131.py`.

## Testing

- `tests/manual_smoke_test_131.py`: ACTUALLY EXECUTED in this fork's
  build environment (`PYTHONPATH=/tmp/stubs:. python3
  tests/manual_smoke_test_131.py`) against hand-rolled `aiohttp`/
  `async_timeout` stub packages, since this sandbox cannot reach PyPI
  (`pip install` → HTTP 403, `curl https://pypi.org/simple/...` → 403,
  confirmed again during this phase, unchanged from Phase 5F). Result:
  13 passed, 0 failed.
- The real suite (`tests/test_washer.py`, `tests/test_dryer.py`, and the
  rest of `tests/`) was NOT executed here for the same reason. Exact
  commands for Adam to run it himself are in the implementation report.

## Evidence basis

Unchanged from Phase 5F: a live, server-delivered Device Data Model (DDM)
response and its rule engine, captured from a real WFW9620HBK3 washer and
WED9620HBK2 dryer. See the project's Phase 5B-5D analysis artifacts.
