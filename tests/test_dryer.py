from collections.abc import Callable

import pytest
from aiointercept import aiointercept
from yarl import URL

from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector
from whirlpool.dryer import (
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
                "DryCavity_ChangeStatusWrinkleShield": {"value": "0", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await dryer.fetch_data()

    assert dryer.get_wrinkle_shield_changeable() is False
    assert await dryer.set_wrinkle_shield("on") is False
    assert ("POST", URL(backend_selector.appliance_command_url)) not in aiointercept_mock.requests


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
