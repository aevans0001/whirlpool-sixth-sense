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
                "Cavity_ChangeStatusSteamChangeable": {
                    "value": "1",
                    "updateTime": 1000,
                },
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


# ---------------------------------------------------------------------------
# Per-cycle wash option controls (WFW9620HBK3)
# ---------------------------------------------------------------------------
# Every expected value below comes from the WFW9620HBK3 DDM response at
# personality.capability[0].Capability.WashCavity.CapabilityData. The DDM is the
# authority for what each cycle allows, because the Whirlpool cloud API accepts
# and stores values that are illegal for the selected cycle and only the
# appliance rejects them, at Start - so the library has to refuse first.

WFW_MODEL = "WFW9620HBK3"
WFW_SAID = "SAIDWFW9620"

# Cycle wire values used by these tests, with their DDM names.
CYCLE_REGULAR_NORMAL = 1  # WashCycleNormal
CYCLE_REGULAR_SANITIZE = 3  # WashCycleSanitize
CYCLE_DELICATES = 5  # WashCycleDelicates
CYCLE_DRAIN_SPIN = 8  # WashCycleDrainSpin (utility)
CYCLE_REGULAR_COLD_WASH = 18  # WashCycleColdWash
CYCLE_CLEAN_WASHER = 20  # WashCycleCleanWasher (utility)
CYCLE_COLORS_QUICK = 47  # WashCycleWhatToColorsBrightsHowToQuick
CYCLE_WHITES_SANITIZE = 92  # WashCycleWhatToWhitesHowToSanitize


def _wfw_attributes(**overrides: object) -> dict:
    """Build a WFW9620HBK3 attribute payload with everything changeable."""
    base = {
        "WashCavity_CycleSetCycleSelect": CYCLE_REGULAR_NORMAL,
        "WashCavity_CycleSetTemperature": 2,
        "WashCavity_CycleSetSpinSpeed": 5,
        "WashCavity_CycleSetSoilLevel": 1,
        "WashCavity_CycleSetExtraRinseSelect": 0,
        "WashCavity_CycleSetPresoakTimed": 0,
        "WashCavity_CycleSetFresheningSelect": 0,
        "Cavity_CycleSetSteamEnable": 0,
        "WashCavity_ChangeStatusCycleSelect": 1,
        "WashCavity_ChangeStatusTemperature": 1,
        "WashCavity_ChangeStatusSpinSpeed": 1,
        "WashCavity_ChangeStatusSoilLevel": 1,
        "WashCavity_ChangeStatusExtraRinse": 1,
        "WashCavity_ChangeStatusPresoakTimed": 1,
        "WashCavity_ChangeStatusFreshening": 1,
        "Cavity_ChangeStatusSteamChangeable": 1,
        "XCat_RemoteSetRemoteControlEnable": 1,
    }
    base.update(overrides)
    return {
        key: {"value": str(value), "updateTime": 1000} for key, value in base.items()
    }


async def _make_wfw_washer(
    auth: Auth,
    backend_selector: BackendSelector,
    session,
    mock: aiointercept,
    *,
    model_number: str = WFW_MODEL,
    **overrides: object,
) -> Washer:
    """Create a fetched Washer whose attribute set is fully controllable."""
    from whirlpool.types import ApplianceInfo

    info = ApplianceInfo(
        said=WFW_SAID,
        name="Test washer",
        data_model="API144",
        category="Laundry",
        model_number=model_number,
        serial_number="TEST",
    )
    washer = Washer(backend_selector, auth, session, info)
    mock.get(
        backend_selector.get_appliance_data_url(WFW_SAID),
        payload={"attributes": _wfw_attributes(**overrides)},
    )
    await washer.fetch_data()
    return washer


def _expected_call(
    washer: Washer, auth: Auth, backend_selector: BackendSelector, body: dict
) -> dict:
    return {
        "url": backend_selector.appliance_command_url,
        "method": "POST",
        "data": None,
        "json": {
            "body": body,
            "header": {"said": washer.said, "command": "setAttributes"},
        },
        "headers": auth.create_headers(),
    }


def _assert_nothing_sent(
    mock: aiointercept, backend_selector: BackendSelector
) -> None:
    """Assert the rejected write never reached the network."""
    key = ("POST", URL(backend_selector.appliance_command_url))
    assert key not in mock.requests or not mock.requests[key]


# --- Temperature -----------------------------------------------------------


@pytest.mark.parametrize(
    ["option", "expected_value"],
    [
        ("cold", "0"),
        ("cool", "1"),
        ("warm", "2"),
        ("hot", "3"),
        ("extra_hot", "4"),
    ],
)
async def test_temperature_setter_sends_exact_wire_value(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    option: str,
    expected_value: str,
):
    """All five DDM temperature values reach the wire on Regular/Normal.

    Cycle 1 lists the full enumeration {Cold, Cool, Warm, Hot, ExtraHot}, so
    every option must be accepted here.
    """
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})

    assert await washer.set_temperature(option) is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer,
            auth,
            backend_selector,
            {"WashCavity_CycleSetTemperature": expected_value},
        )
    )


async def test_temperature_unknown_option_rejected(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """An option key that is not in the DDM enum never reaches the network."""
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    with pytest.raises(ValueError):
        await washer.set_temperature("tepid")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


@pytest.mark.parametrize(
    "cycle", [CYCLE_REGULAR_SANITIZE, CYCLE_WHITES_SANITIZE]
)
async def test_temperature_sanitize_is_extra_hot_only(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    """Sanitize cycles list only WashTempExtraHot in their DDM enumeration."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
        WashCavity_CycleSetTemperature=4,
    )
    assert washer.get_supported_temperatures() == ["extra_hot"]

    with pytest.raises(ValueError):
        await washer.set_temperature("warm")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_temperature_sanitize_accepts_extra_hot(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """The one legal Sanitize temperature still goes through."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_REGULAR_SANITIZE,
        WashCavity_CycleSetTemperature=4,
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_temperature("extra_hot") is True


@pytest.mark.parametrize("cycle", [CYCLE_DRAIN_SPIN, CYCLE_CLEAN_WASHER])
async def test_temperature_unavailable_on_utility_cycles(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    """Neither utility cycle declares a temperature attribute in the DDM."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
    )
    assert washer.cycle_supports_temperature() is False
    assert washer.get_supported_temperatures() == []

    with pytest.raises(ValueError):
        await washer.set_temperature("warm")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_temperature_not_changeable_returns_false(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """An appliance-reported 'not changeable' is a refusal, not an exception."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_ChangeStatusTemperature=0,
    )
    assert await washer.set_temperature("hot") is False
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_temperature_blocked_on_other_model(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Other washer models keep their existing behaviour and expose nothing.

    The bundled WTW8127LW1 fixture reports Temperature=5, which is not even a
    legal value on WFW9620HBK3 - proof that this capability table must not be
    applied to other models.
    """
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        model_number="WTW8127LW1",
    )
    assert washer.is_cycle_options_model_supported() is False
    assert washer.supports_temperature() is False
    assert washer.get_cycle_capability() is None
    assert await washer.set_temperature("hot") is False
    _assert_nothing_sent(aiointercept_mock, backend_selector)


# --- Spin speed ------------------------------------------------------------


async def test_spin_speed_wire_value_one_is_unreachable():
    """The DDM enum has no SpinSpeed value 1, so no option key can produce it."""
    from whirlpool.washer import CYCLE_CAPABILITIES, WASH_SPIN_SPEED_VALUES

    assert 1 not in WASH_SPIN_SPEED_VALUES.values()
    for capability in CYCLE_CAPABILITIES.values():
        assert 1 not in capability.spin_speeds


async def test_spin_speed_numeric_option_rejected(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Passing a raw wire number instead of an option key is rejected."""
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    with pytest.raises(ValueError):
        await washer.set_spin_speed("1")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


@pytest.mark.parametrize(
    "cycle",
    [
        CYCLE_REGULAR_NORMAL,
        CYCLE_REGULAR_SANITIZE,
        CYCLE_REGULAR_COLD_WASH,
    ],
)
async def test_spin_speed_regular_family_omits_low(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    """Cycles 1/2/3/4/18 list {Off, Medium, High, ExtraHigh} - no Low."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
        WashCavity_CycleSetTemperature=4 if cycle == CYCLE_REGULAR_SANITIZE else 2,
    )
    assert washer.get_supported_spin_speeds() == [
        "off",
        "medium",
        "high",
        "extra_high",
    ]
    with pytest.raises(ValueError):
        await washer.set_spin_speed("low")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_spin_speed_low_allowed_outside_regular_family(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Delicates (5) lists the full {Off, Low, Medium, High, ExtraHigh} set."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_DELICATES,
    )
    assert washer.get_supported_spin_speeds() == [
        "off",
        "low",
        "medium",
        "high",
        "extra_high",
    ]
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_spin_speed("low") is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer, auth, backend_selector, {"WashCavity_CycleSetSpinSpeed": "2"}
        )
    )


async def test_spin_speed_supported_on_drain_spin(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Drain & Spin requires a spin speed - it is the point of the cycle."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_DRAIN_SPIN,
    )
    assert washer.cycle_supports_spin_speed() is True
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_spin_speed("extra_high") is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer, auth, backend_selector, {"WashCavity_CycleSetSpinSpeed": "5"}
        )
    )


async def test_spin_speed_unsupported_on_clean_washer(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Clean Washer with affresh declares no spin speed attribute at all."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_CLEAN_WASHER,
    )
    assert washer.cycle_supports_spin_speed() is False
    with pytest.raises(ValueError):
        await washer.set_spin_speed("high")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


# --- Soil level ------------------------------------------------------------


@pytest.mark.parametrize(
    ["option", "expected_value"], [("light", "0"), ("normal", "1"), ("heavy", "2")]
)
async def test_soil_level_setter_sends_exact_wire_value(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    option: str,
    expected_value: str,
):
    """Every normal cycle lists all three soil levels."""
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_soil_level(option) is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer,
            auth,
            backend_selector,
            {"WashCavity_CycleSetSoilLevel": expected_value},
        )
    )


async def test_soil_level_available_on_sanitize(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Sanitize keeps all three soil levels; only temperature is locked."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_REGULAR_SANITIZE,
        WashCavity_CycleSetTemperature=4,
    )
    assert washer.get_supported_soil_levels() == ["light", "normal", "heavy"]


@pytest.mark.parametrize("cycle", [CYCLE_DRAIN_SPIN, CYCLE_CLEAN_WASHER])
async def test_soil_level_unsupported_on_utility_cycles(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
    )
    assert washer.cycle_supports_soil_level() is False
    with pytest.raises(ValueError):
        await washer.set_soil_level("heavy")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


# --- Extra rinse -----------------------------------------------------------


@pytest.mark.parametrize(["option", "expected_value"], [("off", "0"), ("on", "1")])
async def test_extra_rinse_setter_sends_exact_wire_value(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    option: str,
    expected_value: str,
):
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_extra_rinse(option) is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer,
            auth,
            backend_selector,
            {"WashCavity_CycleSetExtraRinseSelect": expected_value},
        )
    )


async def test_extra_rinse_supported_on_drain_spin(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Drain & Spin lists extra rinse as a Required option."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_DRAIN_SPIN,
    )
    assert washer.cycle_supports_extra_rinse() is True
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_extra_rinse("on") is True


async def test_extra_rinse_unsupported_on_clean_washer(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_CLEAN_WASHER,
    )
    assert washer.cycle_supports_extra_rinse() is False
    assert washer.get_supported_extra_rinse_options() == []
    with pytest.raises(ValueError):
        await washer.set_extra_rinse("on")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


# --- Presoak ---------------------------------------------------------------


@pytest.mark.parametrize(
    ["option", "expected_value"],
    [
        ("off", "0"),
        ("30_min", "1800"),
        ("1_hour", "3600"),
        ("8_hour", "28800"),
    ],
)
async def test_presoak_setter_sends_exact_wire_value(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    option: str,
    expected_value: str,
):
    """The DDM List is exactly {0, 1800, 3600, 28800} seconds."""
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_presoak(option) is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer,
            auth,
            backend_selector,
            {"WashCavity_CycleSetPresoakTimed": expected_value},
        )
    )


async def test_presoak_accepts_raw_seconds_from_the_list(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_presoak(3600) is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer,
            auth,
            backend_selector,
            {"WashCavity_CycleSetPresoakTimed": "3600"},
        )
    )


@pytest.mark.parametrize("bad", [900, 1, 28801, "45_min"])
async def test_presoak_rejects_values_outside_the_ddm_list(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    bad,
):
    """Presoak is a List, not a Range - 900 seconds is not rounded, it is refused."""
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    with pytest.raises(ValueError):
        await washer.set_presoak(bad)
    _assert_nothing_sent(aiointercept_mock, backend_selector)


@pytest.mark.parametrize("bad", [True, False])
async def test_presoak_rejects_bool(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    bad: bool,
):
    """bool is an int subclass, so False would otherwise resolve to 'off'.

    set_presoak accepts an option key or a raw wire value in seconds. Without
    an explicit guard, False == 0 would silently look up the 0-second entry
    and send Presoak off, and True == 1 would produce a confusing message.
    Both are rejected before anything is sent.
    """
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    with pytest.raises(ValueError):
        await washer.set_presoak(bad)
    _assert_nothing_sent(aiointercept_mock, backend_selector)


@pytest.mark.parametrize(
    "cycle",
    [
        CYCLE_REGULAR_SANITIZE,
        CYCLE_WHITES_SANITIZE,
        CYCLE_DRAIN_SPIN,
        CYCLE_CLEAN_WASHER,
    ],
)
async def test_presoak_unsupported_on_sanitize_and_utility_cycles(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    """Presoak is absent from every Sanitize cycle and both utility cycles."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
        WashCavity_CycleSetTemperature=4,
    )
    assert washer.cycle_supports_presoak() is False
    assert washer.get_supported_presoak_options() == []
    with pytest.raises(ValueError):
        await washer.set_presoak("30_min")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


# --- What / How matrix -----------------------------------------------------


async def test_wash_cycle_matrix_matches_ddm_shape():
    """35 pairs: six categories, but Bulky has no Sanitize and only Regular
    has a distinct '+Normal' value - the other categories' base value IS their
    Normal selection (Colors=24 is DDM-named 'ColorNormal')."""
    from whirlpool.washer import WASH_CYCLE_MATRIX, WASH_CYCLE_REVERSE

    assert len(WASH_CYCLE_MATRIX) == 35
    assert ("bulky", "sanitize") not in WASH_CYCLE_MATRIX
    assert WASH_CYCLE_MATRIX[("regular", "normal")] == 1
    assert WASH_CYCLE_MATRIX[("colors", "normal")] == 24
    assert WASH_CYCLE_MATRIX[("whites", "normal")] == 10
    assert WASH_CYCLE_MATRIX[("towels", "normal")] == 11
    assert WASH_CYCLE_MATRIX[("delicates", "normal")] == 5
    assert WASH_CYCLE_MATRIX[("bulky", "normal")] == 22
    # Round-trip: no duplicate wire values, reverse map stays consistent.
    assert len(WASH_CYCLE_REVERSE) == len(WASH_CYCLE_MATRIX)
    for pair, value in WASH_CYCLE_MATRIX.items():
        assert WASH_CYCLE_REVERSE[value] == pair


async def test_every_matrix_value_exists_in_the_capability_table():
    """No matrix entry may point at a cycle the DDM does not define."""
    from whirlpool.washer import CYCLE_CAPABILITIES, WASH_CYCLE_MATRIX

    for pair, value in WASH_CYCLE_MATRIX.items():
        assert value in CYCLE_CAPABILITIES, f"{pair} -> {value} missing from DDM table"


async def test_utility_values_are_not_in_the_what_how_matrix():
    """Drain & Spin and Clean Washer must never resolve to a What+How pair."""
    from whirlpool.washer import UTILITY_CYCLE_VALUES, WASH_CYCLE_REVERSE

    for value in UTILITY_CYCLE_VALUES.values():
        assert value not in WASH_CYCLE_REVERSE


async def test_set_wash_cycle_pair_sends_exact_wire_value(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_wash_cycle_pair("colors", "quick") is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer, auth, backend_selector, {"WashCavity_CycleSetCycleSelect": "47"}
        )
    )


async def test_bulky_sanitize_is_rejected(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Bulky+Sanitize has no DDM value and must not be coerced to anything."""
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    with pytest.raises(ValueError):
        await washer.set_wash_cycle_pair("bulky", "sanitize")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_unknown_wash_cycle_pair_is_rejected(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    with pytest.raises(ValueError):
        await washer.set_wash_cycle_pair("curtains", "eco")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_wash_cycle_pair_reports_none_during_utility_cycle(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """What/How must not claim a matrix value while a utility cycle runs."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_DRAIN_SPIN,
    )
    assert washer.get_wash_cycle_pair() is None
    assert washer.get_utility_cycle() == "drain_spin"


# --- Utility cycles --------------------------------------------------------


@pytest.mark.parametrize(
    ["option", "expected_value"],
    [("drain_spin", "8"), ("clean_washer", "20")],
)
async def test_set_utility_cycle_sends_exact_wire_value(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    option: str,
    expected_value: str,
):
    """Utility cycles are written to the same CycleSelect attribute."""
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_utility_cycle(option) is True
    aiointercept_mock.assert_called_with(
        **_expected_call(
            washer,
            auth,
            backend_selector,
            {"WashCavity_CycleSetCycleSelect": expected_value},
        )
    )


@pytest.mark.parametrize(
    ["cycle", "expected"],
    [
        (CYCLE_DRAIN_SPIN, "drain_spin"),
        (CYCLE_CLEAN_WASHER, "clean_washer"),
        (CYCLE_REGULAR_NORMAL, None),
        (CYCLE_COLORS_QUICK, None),
    ],
)
async def test_get_utility_cycle(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
    expected,
):
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
    )
    assert washer.get_utility_cycle() == expected
    assert washer.is_utility_cycle_active() is (expected is not None)


async def test_unknown_utility_cycle_is_rejected(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth, backend_selector, client_session_fixture, aiointercept_mock
    )
    with pytest.raises(ValueError):
        await washer.set_utility_cycle("self_clean")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_utility_cycle_blocked_on_other_model(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        model_number="WTW8127LW1",
    )
    assert washer.supports_utility_cycles() is False
    assert await washer.set_utility_cycle("drain_spin") is False
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_clean_washer_offers_no_options_at_all(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Clean Washer with affresh declares only an optional delay time."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_CLEAN_WASHER,
    )
    assert washer.cycle_supports_temperature() is False
    assert washer.cycle_supports_spin_speed() is False
    assert washer.cycle_supports_soil_level() is False
    assert washer.cycle_supports_presoak() is False
    assert washer.cycle_supports_extra_rinse() is False
    assert washer.cycle_supports_fan_fresh() is False
    assert washer.cycle_supports_steam() is False
    assert washer.cycle_supports_delay_time() is True


async def test_drain_spin_offers_only_spin_rinse_and_fan_fresh(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_DRAIN_SPIN,
    )
    assert washer.cycle_supports_spin_speed() is True
    assert washer.cycle_supports_extra_rinse() is True
    assert washer.cycle_supports_fan_fresh() is True
    assert washer.cycle_supports_temperature() is False
    assert washer.cycle_supports_soil_level() is False
    assert washer.cycle_supports_presoak() is False
    assert washer.cycle_supports_steam() is False


# --- Steam / Fan Fresh per-cycle behaviour ---------------------------------


@pytest.mark.parametrize("cycle", [18, 44, 50, 65, 82, 88])
async def test_steam_unavailable_on_cold_wash_cycles(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    """Cavity_CycleSetSteamEnable is absent from Cold Wash and every
    What+ColdWash variant in the DDM."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
    )
    assert washer.cycle_supports_steam() is False
    with pytest.raises(ValueError):
        await washer.set_steam("on")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


@pytest.mark.parametrize("cycle", [3, 48, 69, 86, 92])
async def test_steam_available_on_sanitize_cycles(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    """Previously an open question: the DDM does list Steam for Sanitize."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
        WashCavity_CycleSetTemperature=4,
    )
    assert washer.cycle_supports_steam() is True
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await washer.set_steam("on") is True


@pytest.mark.parametrize("cycle", [CYCLE_DRAIN_SPIN, CYCLE_CLEAN_WASHER])
async def test_steam_unavailable_on_utility_cycles(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
    cycle: int,
):
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=cycle,
    )
    assert washer.cycle_supports_steam() is False


async def test_fan_fresh_available_on_drain_spin_not_clean_washer(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Fan Fresh is Required on Drain & Spin and absent from Clean Washer."""
    drain = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_DRAIN_SPIN,
    )
    assert drain.cycle_supports_fan_fresh() is True
    url = backend_selector.appliance_command_url
    aiointercept_mock.post(url, payload={})
    assert await drain.set_fan_fresh("on") is True


async def test_fan_fresh_rejected_on_clean_washer(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_CLEAN_WASHER,
    )
    assert washer.cycle_supports_fan_fresh() is False
    with pytest.raises(ValueError):
        await washer.set_fan_fresh("on")
    _assert_nothing_sent(aiointercept_mock, backend_selector)


async def test_unknown_cycle_never_invents_a_restriction(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """A cycle value outside the captured DDM enum must stay permissive.

    This is what keeps the pre-existing Steam and Fan Fresh behaviour intact
    for any payload that does not carry a CycleSelect attribute at all.
    """
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=999,
    )
    assert washer.get_cycle_capability() is None
    assert washer.cycle_supports_steam() is True
    assert washer.cycle_supports_temperature() is True
    assert washer.get_supported_temperatures() == [
        "cold",
        "cool",
        "warm",
        "hot",
        "extra_hot",
    ]


# --- Read-back of live-captured values -------------------------------------


async def test_getters_decode_the_live_capture_values(
    auth: Auth,
    backend_selector: BackendSelector,
    aiointercept_mock: aiointercept,
    client_session_fixture,
):
    """Decode the exact values captured from the real WFW9620HBK3 in Setting
    state on 2026-09-12: cycle 47, Warm, High, Light, everything else off."""
    washer = await _make_wfw_washer(
        auth,
        backend_selector,
        client_session_fixture,
        aiointercept_mock,
        WashCavity_CycleSetCycleSelect=CYCLE_COLORS_QUICK,
        WashCavity_CycleSetTemperature=2,
        WashCavity_CycleSetSpinSpeed=4,
        WashCavity_CycleSetSoilLevel=0,
        WashCavity_CycleSetExtraRinseSelect=0,
        WashCavity_CycleSetPresoakTimed=0,
    )
    assert washer.get_wash_cycle_pair() == ("colors", "quick")
    assert washer.get_cycle_select() == 47
    assert washer.get_temperature() == "warm"
    assert washer.get_spin_speed() == "high"
    assert washer.get_soil_level() == "light"
    assert washer.get_extra_rinse() == "off"
    assert washer.get_presoak() == "off"
    assert washer.get_presoak_seconds() == 0
    assert washer.get_utility_cycle() is None


async def test_no_easy_iron_surface_exists():
    """Easy Iron is live-observed but has no DDM definition and no app write
    path, so this fork must never grow a setter or option map for it - nor for
    the other undocumented live attributes."""
    from whirlpool import washer as washer_module

    forbidden_members = {
        "set_easy_iron",
        "get_easy_iron",
        "set_bleach_enable",
        "set_color15",
        "set_spin_speed_rpm",
        "set_temperature_degrees",
    }
    assert not (forbidden_members & set(dir(Washer)))
    source_constants = {
        name for name in dir(washer_module) if name.startswith("ATTR_")
    }
    for name in source_constants:
        value = getattr(washer_module, name)
        assert "EasyIron" not in value
        assert "BleachEnable" not in value
        assert "Color15" not in value
        assert "SpinSpeedRpm" not in value
        assert "TemperatureDegrees" not in value
