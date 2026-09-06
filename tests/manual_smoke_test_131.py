"""Dependency-free smoke test for the 1.3.1 compatibility branch.

Unlike Phase 5F's tests/manual_smoke_test.py (which exercised a
hand-written FakeLaundryAppliance standing in for LaundryCommandsMixin),
this test imports and instantiates the REAL whirlpool.washer.Washer and
whirlpool.dryer.Dryer classes from this checkout and drives them through
a fake aiohttp session, so it is exercising actual production code paths
(Appliance.send_attributes -> session.post -> real JSON body construction)
rather than a stand-in.

This is not a substitute for the real pytest suite (tests/test_washer.py,
tests/test_dryer.py) - it exists because this sandbox cannot reach PyPI
to install aiointercept/pytest-asyncio (see the implementation report).
Run with:
    PYTHONPATH=/tmp/stubs:. python3 tests/manual_smoke_test_131.py
"""

import asyncio
import sys

sys.path.insert(0, "/tmp/stubs")

from whirlpool.backendselector import BackendSelector  # noqa: E402
from whirlpool.dryer import Dryer  # noqa: E402
from whirlpool.types import ApplianceInfo, Brand, Region  # noqa: E402
from whirlpool.washer import Washer  # noqa: E402

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def check(label: str, condition: bool) -> None:
    global CHECKS_PASSED, CHECKS_FAILED
    if condition:
        CHECKS_PASSED += 1
        print(f"PASS: {label}")
    else:
        CHECKS_FAILED += 1
        print(f"FAIL: {label}")


class FakeAuth:
    def create_headers(self):
        return {}

    async def do_auth(self):
        return None


class FakeResponse:
    def __init__(self, status=200):
        self.status = status

    async def text(self):
        return "{}"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Records every POST body instead of sending it anywhere."""

    def __init__(self):
        self.sent: list[dict] = []

    def post(self, url, json, headers):
        self.sent.append(json)
        return FakeResponse(200)


def make_appliance(cls, said="TESTSAID", fetched=True):
    info = ApplianceInfo(
        said=said,
        name="Test Appliance",
        data_model="API144",
        category="Laundry",
        model_number="TESTMODEL",
        serial_number="TESTSERIAL",
    )
    backend_selector = BackendSelector(Brand.Whirlpool, Region.US)
    session = FakeSession()
    appliance = cls(backend_selector, FakeAuth(), session, info)
    if fetched:
        # Populate the minimal internal data dict fetch_data() would have
        # populated, so has_attribute()/_get_attribute() behave as if a
        # real fetch already succeeded.
        appliance._data_dict = {
            "attributes": {
                "XCat_RemoteSetRemoteControlEnable": {"value": "1"},
            }
        }
    return appliance, session


async def main():
    # --- Washer -------------------------------------------------------
    washer, washer_session = make_appliance(Washer)

    check(
        "Washer.get_remote_control_enabled() reads True from wire attr",
        washer.get_remote_control_enabled() is True,
    )

    ok = await washer.start()
    check("Washer.start() returns True", ok is True)
    check(
        "Washer.start() sent Cavity_OpSetOperations=2",
        washer_session.sent[-1]["body"] == {"Cavity_OpSetOperations": "2"},
    )
    check(
        "Washer.start() sent correct header (said/command)",
        washer_session.sent[-1]["header"]
        == {"said": "TESTSAID", "command": "setAttributes"},
    )

    await washer.pause()
    check(
        "Washer.pause() sent Cavity_OpSetOperations=5",
        washer_session.sent[-1]["body"] == {"Cavity_OpSetOperations": "5"},
    )

    await washer.resume()
    check(
        "Washer.resume() sent Cavity_OpSetOperations=6",
        washer_session.sent[-1]["body"] == {"Cavity_OpSetOperations": "6"},
    )

    await washer.cancel()
    check(
        "Washer.cancel() sent Cavity_OpSetOperations=1",
        washer_session.sent[-1]["body"] == {"Cavity_OpSetOperations": "1"},
    )

    check(
        "Washer sent exactly 4 requests total (no extra/unrelated sends)",
        len(washer_session.sent) == 4,
    )

    # --- Dryer ----------------------------------------------------------
    dryer, dryer_session = make_appliance(Dryer)
    await dryer.start()
    check(
        "Dryer.start() sent Cavity_OpSetOperations=2",
        dryer_session.sent[-1]["body"] == {"Cavity_OpSetOperations": "2"},
    )

    # --- Not-yet-fetched guard -------------------------------------------
    unfetched_washer, unfetched_session = make_appliance(Washer, fetched=False)
    result = await unfetched_washer.start()
    check(
        "Command on never-fetched appliance returns False (protocol guard)",
        result is False,
    )
    check(
        "Command on never-fetched appliance sends nothing",
        len(unfetched_session.sent) == 0,
    )

    # --- No public Remote Enable setter -----------------------------------
    forbidden_names = {
        "set_remote_control_enabled",
        "set_remote_enable",
        "enable_remote_control",
        "disable_remote_control",
    }
    found = forbidden_names & set(dir(Washer)) | forbidden_names & set(dir(Dryer))
    check("No Remote Enable setter exists on Washer or Dryer", not found)

    # --- Only proven operation values are reachable -----------------------
    from whirlpool._laundry_commands import (
        OPERATION_CANCEL,
        OPERATION_PAUSE,
        OPERATION_RESUME,
        OPERATION_START,
    )

    check(
        "Only the 4 proven operation values are defined",
        {OPERATION_CANCEL, OPERATION_PAUSE, OPERATION_RESUME, OPERATION_START}
        == {"1", "2", "5", "6"},
    )

    print(f"\n{CHECKS_PASSED} passed, {CHECKS_FAILED} failed")
    return CHECKS_FAILED == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
