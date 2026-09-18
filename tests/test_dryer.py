from collections.abc import Callable

import pytest
from aiointercept import aiointercept
from yarl import URL

from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector
from whirlpool.dryer import (
    DRY_CYCLE_PAIR_MAP,
    DRY_CYCLE_PAIR_REVERSE,
    Cycle,
    Dryer,
    Dryness,
    MachineState,
    Temperature,
    WrinkleShield,
)


async def test_attributes(appliances_manager: AppliancesManager):
    dryer = appliances_manager.dryers[0]
    assert dryer.get_machine_state() == MachineState.Standby
    assert not dryer.get_door_open()
    assert dryer.get_time_remaining() == 1800
    assert not dryer.get_drum_light_on()
    assert dryer.get_steam_changeable()
    assert not dryer.get_cycle_changeable()
    assert dryer.get_dryness_changeable()
    assert dryer.get_manual_dry_time_changeable()
    assert dryer.get_steam_changeable()
    assert dryer.get_wrinkle_shield_changeable()
    assert dryer.get_dryness() == Dryness.High
    assert dryer.get_manual_dry_time() == 1800
    assert dryer.get_cycle() == Cycle.TimedDry
    assert not dryer.get_cycle_status_airflow_status()
    assert not dryer.get_cycle_status_cool_down()
    assert not dryer.get_cycle_status_damp()
    assert not dryer.get_cycle_status_drying()
    assert not dryer.get_cycle_status_limited_cycle()
    assert not dryer.get_cycle_status_sensing()
    assert not dryer.get_cycle_status_static_reduce()
    assert not dryer.get_cycle_status_steaming()
    assert not dryer.get_cycle_status_wet()
    assert dryer.get_cycle_count() == 195
    assert dryer.get_damp_notification_tone_volume() == 0
    assert dryer.get_alert_tone_volume() == 0
    assert dryer.get_temperature() == Temperature.Cool
    assert dryer.get_wrinkle_shield() == WrinkleShield.Off
    assert dryer.get_wrinkle_shield_str() == "off"
    # Added for API144 laundry command support (Phase 5F.1 compatibility
    # port) - fixture data has Remote Control disabled for this appliance.
    assert dryer.get_remote_control_enabled() is False


@pytest.mark.parametrize(
    ["method", "expected_json"],
    [
        (Dryer.start, {"Cavity_OpSetOperations": "2"}),
        (Dryer.pause, {"Cavity_OpSetOperations": "5"}),
        (Dryer.resume, {"Cavity_OpSetOperations": "6"}),
        (Dryer.cancel, {"Cavity_OpSetOperations": "1"}),
    ],
)
async def test_command_setters(
    appliances_manager: AppliancesManager,
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    method: Callable,
    expected_json: dict,
):
    """Exact-payload test for Start/Pause/Resume/Cancel, mirroring the
    existing tests/test_aircon.py::test_setters pattern."""
    dryer = appliances_manager.dryers[0]
    expected_payload = {
        "json": {
            "body": expected_json,
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    post_request_call_kwargs = {
        "url": backend_selector.appliance_command_url,
        "method": "POST",
        "data": None,
        "json": expected_payload["json"],
        "headers": auth.create_headers(),
    }
    url = backend_selector.appliance_command_url

    aiointercept_mock.post(url, payload=expected_payload)
    assert await method(dryer) is True

    aiointercept_mock.assert_called_with(**post_request_call_kwargs)
    assert len(aiointercept_mock.requests[("POST", URL(url))]) == 1


async def test_command_blocked_before_first_fetch(
    auth: Auth, backend_selector: BackendSelector, client_session_fixture
):
    """Protocol-level guard: a command sent before any fetch_data() call
    must not be sent, since has_attribute() is False for everything."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="UNFETCHED",
        name="Unfetched dryer",
        data_model="API144",
        category="Laundry",
        model_number="TEST",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    assert await dryer.start() is False


@pytest.mark.parametrize(
    ["option", "expected_value"],
    [
        ("off", "0"),
        ("on", "1"),
        ("on_with_steam", "2"),
    ],
)
async def test_wrinkle_shield_setter(
    appliances_manager: AppliancesManager,
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    option: str,
    expected_value: str,
):
    """Exact-payload test for set_wrinkle_shield() for all three DDM-proven values.

    WED9620HBK2 DDM-evidence:
      DryCavity_CycleSetWrinkleShield confirmed present (value "0" at capture);
      DryCavity_ChangeStatusWrinkleShield = "1" (changeable — fixture asserts this);
      Cavity_ChangeStatusSteamChangeable = "1" (steam via value "2" proven).
    """
    dryer = appliances_manager.dryers[0]
    expected_payload = {
        "json": {
            "body": {"DryCavity_CycleSetWrinkleShield": expected_value},
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    post_request_call_kwargs = {
        "url": backend_selector.appliance_command_url,
        "method": "POST",
        "data": None,
        "json": expected_payload["json"],
        "headers": auth.create_headers(),
    }
    url = backend_selector.appliance_command_url

    aiointercept_mock.post(url, payload=expected_payload)
    assert await dryer.set_wrinkle_shield(option) is True

    aiointercept_mock.assert_called_with(**post_request_call_kwargs)
    assert len(aiointercept_mock.requests[("POST", URL(url))]) == 1


async def test_wrinkle_shield_setter_blocked_when_not_changeable(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """Non-changeable guard: set_wrinkle_shield() returns False when
    DryCavity_ChangeStatusWrinkleShield="0", matching the changeability
    gate in dryer.set_wrinkle_shield().

    No HTTP POST must occur in this path.
    """
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_NC",
        name="Non-changeable dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)

    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_NC"),
        payload={
            "attributes": {
                "DryCavity_CycleSetWrinkleShield": {"value": "0", "updateTime": 1000},
                "DryCavity_ChangeStatusWrinkleShield": {
                    "value": "0",
                    "updateTime": 1000,
                },
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    assert dryer.get_wrinkle_shield_changeable() is False
    assert await dryer.set_wrinkle_shield("on") is False
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests


def test_no_remote_control_enable_setter():
    """Reflection guard: fails the build if a setter for Remote Enable
    is ever accidentally added, per this fork's safety boundary."""
    forbidden = {
        "set_remote_control_enabled",
        "set_remote_enable",
        "enable_remote_control",
        "disable_remote_control",
    }
    assert not (forbidden & set(dir(Dryer)))


# ---------------------------------------------------------------------------
# DRY CYCLE PAIR MAP — unit tests (no fixtures needed)
# ---------------------------------------------------------------------------

def test_dry_cycle_pair_map_known_entries():
    """Spot-check key DDM-proven entries in DRY_CYCLE_PAIR_MAP."""
    # Legacy flat cycles re-used as What+How "normal" anchors
    assert DRY_CYCLE_PAIR_MAP[("regular", "normal")] == "1"
    assert DRY_CYCLE_PAIR_MAP[("bulky", "normal")] == "6"
    assert DRY_CYCLE_PAIR_MAP[("delicates", "normal")] == "4"
    assert DRY_CYCLE_PAIR_MAP[("towels", "normal")] == "15"
    assert DRY_CYCLE_PAIR_MAP[("whites", "normal")] == "16"
    assert DRY_CYCLE_PAIR_MAP[("colors", "normal")] == "13"
    # Matrix values
    assert DRY_CYCLE_PAIR_MAP[("colors", "heavy_duty")] == "17"
    assert DRY_CYCLE_PAIR_MAP[("bulky", "heavy_duty")] == "22"
    assert DRY_CYCLE_PAIR_MAP[("delicates", "heavy_duty")] == "27"
    assert DRY_CYCLE_PAIR_MAP[("towels", "heavy_duty")] == "31"
    assert DRY_CYCLE_PAIR_MAP[("whites", "heavy_duty")] == "36"
    assert DRY_CYCLE_PAIR_MAP[("whites", "wrinkle_control")] == "40"


def test_dry_cycle_pair_map_delicates_sanitize_absent():
    """Delicates+Sanitize must NOT appear in DRY_CYCLE_PAIR_MAP — it is
    DDM-forbidden and absent from the official Whirlpool app."""
    assert ("delicates", "sanitize") not in DRY_CYCLE_PAIR_MAP


def test_dry_cycle_pair_map_count():
    """Exactly 35 DDM-proven What+How pairs (36 matrix slots minus the
    one DDM-forbidden Delicates+Sanitize slot)."""
    assert len(DRY_CYCLE_PAIR_MAP) == 35


def test_dry_cycle_pair_reverse_round_trip():
    """Every entry in DRY_CYCLE_PAIR_MAP must round-trip through
    DRY_CYCLE_PAIR_REVERSE without loss."""
    for pair, wire in DRY_CYCLE_PAIR_MAP.items():
        assert DRY_CYCLE_PAIR_REVERSE[wire] == pair


# ---------------------------------------------------------------------------
# Delicates+Sanitize blocked by set_dry_cycle_pair()
# ---------------------------------------------------------------------------

async def test_delicates_sanitize_raises(
    appliances_manager: AppliancesManager,
    aiointercept_mock: aiointercept,
    backend_selector: BackendSelector,
):
    """set_dry_cycle_pair('delicates', 'sanitize') must raise ValueError.

    No HTTP POST must be sent when the combination is DDM-forbidden.
    """
    dryer = appliances_manager.dryers[0]
    with pytest.raises(ValueError, match="Delicates"):
        await dryer.set_dry_cycle_pair("delicates", "sanitize")
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests


# ---------------------------------------------------------------------------
# Steam Refresh: sends CycleSelect=10, NOT WrinkleShield=2
# ---------------------------------------------------------------------------

async def test_utility_cycle_steam_refresh_sends_cycle_select(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """set_utility_cycle('steam_refresh') sends DryCavity_CycleSetCycleSelect='10',
    NOT DryCavity_CycleSetWrinkleShield='2'. These are definitively separate
    features (CycleSelect=10 vs WrinkleShield on-with-steam=2)."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_UC",
        name="Utility cycle dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)

    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_UC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusCycleSelect": {"value": "1", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "1", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    expected_body = {"DryCavity_CycleSetCycleSelect": "10"}
    expected_payload = {
        "json": {
            "body": expected_body,
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload=expected_payload)

    assert await dryer.set_utility_cycle("steam_refresh") is True
    aiointercept_mock.assert_called_with(
        url=url,
        method="POST",
        data=None,
        json=expected_payload["json"],
        headers=auth.create_headers(),
    )
    # WrinkleShield must NOT appear in any POST body
    posted = aiointercept_mock.requests[("POST", URL(url))]
    assert len(posted) == 1
    for req in posted:
        assert "DryCavity_CycleSetWrinkleShield" not in req.kwargs.get("json", {}).get(
            "body", {}
        )


# ---------------------------------------------------------------------------
# set_dryness — exact-payload tests (dryness IS changeable in main fixture)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ["option", "expected_wire"],
    [
        ("less", "1"),
        ("normal", "4"),
        ("more", "7"),
        ("none", "10"),
    ],
)
async def test_set_dryness(
    appliances_manager: AppliancesManager,
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    option: str,
    expected_wire: str,
):
    """Exact-payload test for set_dryness(). All four WED9620HBK2 DDM-proven
    dryness option keys must map to the correct wire values."""
    dryer = appliances_manager.dryers[0]
    assert dryer.get_dryness_changeable() is True  # fixture precondition

    expected_payload = {
        "json": {
            "body": {"DryCavity_CycleSetDryness": expected_wire},
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload=expected_payload)

    assert await dryer.set_dryness(option) is True
    aiointercept_mock.assert_called_with(
        url=url,
        method="POST",
        data=None,
        json=expected_payload["json"],
        headers=auth.create_headers(),
    )


async def test_set_dryness_blocked_when_not_changeable(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """set_dryness() returns False when DryCavity_ChangeStatusDryness='0'."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_DNC",
        name="Dryness NC dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_DNC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusDryness": {"value": "0", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    assert dryer.get_dryness_changeable() is False
    assert await dryer.set_dryness("normal") is False
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests


# ---------------------------------------------------------------------------
# set_temperature — exact-payload tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ["option", "expected_wire"],
    [
        ("air", "0"),
        ("cool_low", "1"),
        ("cool_mid", "2"),
        ("warm_mid", "5"),
        ("hot_mid", "8"),
    ],
)
async def test_set_temperature(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
    option: str,
    expected_wire: str,
):
    """Exact-payload test for set_temperature(). All five WED9620HBK2 DDM-proven
    temperature option keys must map to the correct wire values."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_TC",
        name="Temperature changeable dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_TC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusTemperature": {"value": "1", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "1", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    expected_payload = {
        "json": {
            "body": {"DryCavity_CycleSetTemperature": expected_wire},
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload=expected_payload)

    assert await dryer.set_temperature(option) is True
    aiointercept_mock.assert_called_with(
        url=url,
        method="POST",
        data=None,
        json=expected_payload["json"],
        headers=auth.create_headers(),
    )


async def test_set_temperature_blocked_when_not_changeable(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """set_temperature() returns False when DryCavity_ChangeStatusTemperature='0'."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_TNC",
        name="Temperature NC dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_TNC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusTemperature": {"value": "0", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    assert dryer.get_temperature_changeable() is False
    assert await dryer.set_temperature("warm_mid") is False
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests


# ---------------------------------------------------------------------------
# set_dry_cycle_pair — exact-payload and blocked tests
# ---------------------------------------------------------------------------

async def test_set_dry_cycle_pair(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """set_dry_cycle_pair('towels', 'heavy_duty') sends CycleSelect='31'."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_CC",
        name="Cycle changeable dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_CC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusCycleSelect": {"value": "1", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "1", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()
    assert dryer.get_cycle_changeable() is True

    # TowelsHeavyDuty = 31 (DDM-proven)
    expected_payload = {
        "json": {
            "body": {"DryCavity_CycleSetCycleSelect": "31"},
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload=expected_payload)

    assert await dryer.set_dry_cycle_pair("towels", "heavy_duty") is True
    aiointercept_mock.assert_called_with(
        url=url,
        method="POST",
        data=None,
        json=expected_payload["json"],
        headers=auth.create_headers(),
    )


async def test_set_dry_cycle_pair_blocked_when_not_changeable(
    appliances_manager: AppliancesManager,
    aiointercept_mock: aiointercept,
    backend_selector: BackendSelector,
):
    """set_dry_cycle_pair() returns False when cycle is not changeable
    (fixture has DryCavity_ChangeStatusCycleSelect='0')."""
    dryer = appliances_manager.dryers[0]
    assert dryer.get_cycle_changeable() is False  # fixture precondition

    assert await dryer.set_dry_cycle_pair("towels", "normal") is False
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests


# ---------------------------------------------------------------------------
# set_static_guard — exact-payload and blocked tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ["option", "expected_wire"],
    [
        ("off", "0"),
        ("on", "1"),
    ],
)
async def test_set_static_guard(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
    option: str,
    expected_wire: str,
):
    """Exact-payload test for set_static_guard() for both DDM-proven values."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_SGC",
        name="Static guard changeable dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_SGC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusStaticGuard": {"value": "1", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "1", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    expected_payload = {
        "json": {
            "body": {"DryCavity_CycleSetStaticGuard": expected_wire},
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload=expected_payload)

    assert await dryer.set_static_guard(option) is True
    aiointercept_mock.assert_called_with(
        url=url,
        method="POST",
        data=None,
        json=expected_payload["json"],
        headers=auth.create_headers(),
    )


async def test_set_static_guard_blocked_when_not_changeable(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """set_static_guard() returns False when DryCavity_ChangeStatusStaticGuard='0'."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_SGNC",
        name="Static guard NC dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_SGNC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusStaticGuard": {"value": "0", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    assert dryer.get_static_guard_changeable() is False
    assert await dryer.set_static_guard("on") is False
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests


# ---------------------------------------------------------------------------
# set_eco_boost — exact-payload and blocked tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ["option", "expected_wire"],
    [
        ("off", "0"),
        ("on", "1"),
    ],
)
async def test_set_eco_boost(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
    option: str,
    expected_wire: str,
):
    """Exact-payload test for set_eco_boost() for both DDM-proven values."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_EBC",
        name="Eco boost changeable dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_EBC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusEcoBoost": {"value": "1", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "1", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    expected_payload = {
        "json": {
            "body": {"DryCavity_CycleSetEcoBoost": expected_wire},
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload=expected_payload)

    assert await dryer.set_eco_boost(option) is True
    aiointercept_mock.assert_called_with(
        url=url,
        method="POST",
        data=None,
        json=expected_payload["json"],
        headers=auth.create_headers(),
    )


async def test_set_eco_boost_blocked_when_not_changeable(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """set_eco_boost() returns False when DryCavity_ChangeStatusEcoBoost='0'."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_EBNC",
        name="Eco boost NC dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_EBNC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusEcoBoost": {"value": "0", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    assert dryer.get_eco_boost_changeable() is False
    assert await dryer.set_eco_boost("on") is False
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests


# ---------------------------------------------------------------------------
# set_manual_dry_time — exact-payload and blocked tests
# ---------------------------------------------------------------------------

async def test_set_manual_dry_time(
    appliances_manager: AppliancesManager,
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
):
    """set_manual_dry_time(seconds) sends the correct wire value.

    Wire unit is seconds (DDM-proven: fixture value 1800 = 30 minutes).
    """
    dryer = appliances_manager.dryers[0]
    assert dryer.get_manual_dry_time_changeable() is True  # fixture precondition

    expected_payload = {
        "json": {
            "body": {"DryCavity_CycleSetManualDryTime": "1800"},
            "header": {"said": dryer.said, "command": "setAttributes"},
        }
    }
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload=expected_payload)

    assert await dryer.set_manual_dry_time(1800) is True
    aiointercept_mock.assert_called_with(
        url=url,
        method="POST",
        data=None,
        json=expected_payload["json"],
        headers=auth.create_headers(),
    )


async def test_set_manual_dry_time_blocked_when_not_changeable(
    auth: Auth,
    backend_selector: BackendSelector,
    client_session_fixture,
    aiointercept_mock: aiointercept,
):
    """set_manual_dry_time() returns False when
    DryCavity_ChangeStatusManualDryTime='0'."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDDRYER_MDTNC",
        name="Manual time NC dryer",
        data_model="API144",
        category="Laundry",
        model_number="WED9620HBK2",
        serial_number="TEST",
    )
    dryer = Dryer(backend_selector, auth, client_session_fixture, info)
    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDDRYER_MDTNC"),
        payload={
            "attributes": {
                "DryCavity_ChangeStatusManualDryTime": {
                    "value": "0",
                    "updateTime": 1000,
                },
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    assert dryer.get_manual_dry_time_changeable() is False
    assert await dryer.set_manual_dry_time(1800) is False
    assert (
        "POST",
        URL(backend_selector.appliance_command_url),
    ) not in aiointercept_mock.requests
