from collections.abc import Callable

import pytest
from aiointercept import aiointercept
from yarl import URL

from whirlpool.appliancesmanager import AppliancesManager
from whirlpool.auth import Auth
from whirlpool.backendselector import BackendSelector
from whirlpool.washer import MachineState, Washer


async def test_attributes(appliances_manager: AppliancesManager):
    washer = appliances_manager.washers[0]

    assert washer.get_machine_state() == MachineState.Standby
    assert washer.get_cycle_status_sensing() is False
    assert washer.get_cycle_status_filling() is False
    assert washer.get_cycle_status_soaking() is False
    assert washer.get_cycle_status_washing() is False
    assert washer.get_cycle_status_rinsing() is False
    assert washer.get_cycle_status_spinning() is False
    assert washer.get_dispense_1_level() == 4
    assert washer.get_door_open() is True
    assert washer.get_time_remaining() == 4080
    # Added for API144 laundry command support (Phase 5F.1 compatibility
    # port) - fixture data has Remote Control disabled for this appliance.
    assert washer.get_remote_control_enabled() is False


@pytest.mark.parametrize(
    ["method", "expected_json"],
    [
        (Washer.start, {"Cavity_OpSetOperations": "2"}),
        (Washer.pause, {"Cavity_OpSetOperations": "5"}),
        (Washer.resume, {"Cavity_OpSetOperations": "6"}),
        (Washer.cancel, {"Cavity_OpSetOperations": "1"}),
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
    existing tests/test_aircon.py::test_setters pattern for this fork's
    new commands."""
    washer = appliances_manager.washers[0]
    expected_payload = {
        "json": {
            "body": expected_json,
            "header": {"said": washer.said, "command": "setAttributes"},
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
    assert await method(washer) is True

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
        name="Unfetched washer",
        data_model="API144",
        category="Laundry",
        model_number="TEST",
        serial_number="TEST",
    )
    washer = Washer(backend_selector, auth, client_session_fixture, info)
    assert await washer.start() is False


async def test_steam_setter_model_blocked(
    auth: Auth, backend_selector: BackendSelector, client_session_fixture
):
    """Steam Enable setter returns False for non-WFW9620HBK3 model numbers.
    Proves the model gate in is_steam_model_supported() and supports_steam()."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="TESTSTEAM",
        name="Generic washer",
        data_model="API144",
        category="Laundry",
        model_number="OTHER_MODEL",
        serial_number="TEST",
    )
    washer = Washer(backend_selector, auth, client_session_fixture, info)
    assert not washer.is_steam_model_supported()
    assert not washer.supports_steam()
    assert await washer.set_steam("on") is False


@pytest.mark.parametrize(
    ["option", "expected_value"],
    [
        ("on", "1"),
        ("off", "0"),
    ],
)
async def test_steam_setter(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    option: str,
    expected_value: str,
):
    """Exact-payload test for set_steam() on WFW9620HBK3.

    Proves both values from the DDM-evidence enum (off=0, on=1) reach the
    wire as Cavity_CycleSetSteamEnable. Fixture data provides both required
    attributes so supports_steam() returns True.
    """
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said="SAIDSTEAM1",
        name="Steam Washer",
        data_model="API144",
        category="Laundry",
        model_number="WFW9620HBK3",
        serial_number="TEST",
    )
    washer = Washer(backend_selector, auth, client_session_fixture, info)

    aiointercept_mock.get(
        backend_selector.get_appliance_data_url("SAIDSTEAM1"),
        payload={
            "attributes": {
                "Cavity_CycleSetSteamEnable": {"value": "0", "updateTime": 1000},
                "Cavity_ChangeStatusSteamChangeable": {"value": "1", "updateTime": 1000},
                "XCat_RemoteSetRemoteControlEnable": {"value": "0", "updateTime": 1000},
            }
        },
    )
    await washer.fetch_data()

    assert washer.is_steam_model_supported()
    assert washer.supports_steam()

    expected_payload = {
        "json": {
            "body": {"Cavity_CycleSetSteamEnable": expected_value},
            "header": {"said": washer.said, "command": "setAttributes"},
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
    assert await washer.set_steam(option) is True

    aiointercept_mock.assert_called_with(**post_request_call_kwargs)
    assert len(aiointercept_mock.requests[("POST", URL(url))]) == 1


def test_no_remote_control_enable_setter():
    """Reflection guard: fails the build if a setter for Remote Enable
    is ever accidentally added, per this fork's safety boundary."""
    forbidden = {
        "set_remote_control_enabled",
        "set_remote_enable",
        "enable_remote_control",
        "disable_remote_control",
    }
    assert not (forbidden & set(dir(Washer)))
