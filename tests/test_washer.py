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
