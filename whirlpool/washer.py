from enum import Enum

from ._laundry_commands import LaundryCommandsMixin
from .appliance import Appliance

ATTR_CYCLE_STATUS_SENSING = "WashCavity_CycleStatusSensing"
ATTR_CYCLE_STATUS_FILLING = "WashCavity_CycleStatusFilling"
ATTR_CYCLE_STATUS_SOAKING = "WashCavity_CycleStatusSoaking"
ATTR_CYCLE_STATUS_WASHING = "WashCavity_CycleStatusWashing"
ATTR_CYCLE_STATUS_RINSING = "WashCavity_CycleStatusRinsing"
ATTR_CYCLE_STATUS_SPINNING = "WashCavity_CycleStatusSpinning"
ATTR_CYCLE_STATUS_MACHINE_STATE = "Cavity_CycleStatusMachineState"
ATTR_CYCLE_STATUS_TIME_REMAINING = "Cavity_TimeStatusEstTimeRemaining"

ATTR_DISPENSE_1_LEVEL = "WashCavity_OpStatusBulkDispense1Level"
ATTR_DISPENSE_2_LEVEL = "WashCavity_OpStatusBulkDispense2Level"
ATTR_DISPENSE_1_ENABLE = "WashCavity_CycleSetBulkDispense1Enable"
ATTR_DISPENSE_2_ENABLE = "WashCavity_CycleSetBulkDispense2Enable"
ATTR_DISPENSE_1_CONCENTRATION = "WashCavity_OpSetBulkDispense1Concentration"
ATTR_DISPENSE_2_CONCENTRATION = "WashCavity_OpSetBulkDispense2Concentration"
ATTR_DISPENSE_2_SELECTION = "WashCavity_OpSetBulkDispense2Selection"
ATTR_CYCLE_SELECT = "WashCavity_CycleSetCycleSelect"
ATTR_FRESHENING_SELECT = "WashCavity_CycleSetFresheningSelect"
ATTR_CHANGE_STATUS_FRESHENING = "WashCavity_ChangeStatusFreshening"
ATTR_DOOR_OPEN = "Cavity_OpStatusDoorOpen"

# Fan Fresh is proven only for this exact model. Keep the gate here, next to
# the model-specific cycle matrix, so generic Washer instances cannot expose
# a setting merely because a similarly named attribute happens to be present.
FAN_FRESH_SUPPORTED_MODEL = "WFW9620HBK3"
FRESHENING_VALUES = {"off": 0, "on": 1}
FRESHENING_REVERSE = {value: key for key, value in FRESHENING_VALUES.items()}

# DDM-proven combined What-to-Wash / How-to-Wash values for WFW9620HBK3.
WASH_CYCLE_MATRIX = {
    ("regular", "normal"): 1,
    ("regular", "quick"): 4,
    ("regular", "wrinkle_control"): 16,
    ("regular", "heavy_duty"): 2,
    ("regular", "cold_wash"): 18,
    ("regular", "sanitize"): 3,
    ("colors", "normal"): 24,
    ("colors", "quick"): 47,
    ("colors", "wrinkle_control"): 49,
    ("colors", "heavy_duty"): 46,
    ("colors", "cold_wash"): 44,
    ("colors", "sanitize"): 48,
    ("whites", "normal"): 10,
    ("whites", "quick"): 91,
    ("whites", "wrinkle_control"): 93,
    ("whites", "heavy_duty"): 90,
    ("whites", "cold_wash"): 88,
    ("whites", "sanitize"): 92,
    ("towels", "normal"): 11,
    ("towels", "quick"): 85,
    ("towels", "wrinkle_control"): 87,
    ("towels", "heavy_duty"): 84,
    ("towels", "cold_wash"): 82,
    ("towels", "sanitize"): 86,
    ("delicates", "normal"): 5,
    ("delicates", "quick"): 68,
    ("delicates", "wrinkle_control"): 70,
    ("delicates", "heavy_duty"): 67,
    ("delicates", "cold_wash"): 65,
    ("delicates", "sanitize"): 69,
    ("bulky", "normal"): 22,
    ("bulky", "quick"): 53,
    ("bulky", "wrinkle_control"): 54,
    ("bulky", "heavy_duty"): 52,
    ("bulky", "cold_wash"): 50,
}
WASH_CYCLE_REVERSE = {value: key for key, value in WASH_CYCLE_MATRIX.items()}

DISPENSER_ENABLE_VALUES = {
    "disabled": 0,
    "enabled": 1,
    "disabled_next_cycle": 2,
}
DISPENSER_ENABLE_REVERSE = {value: key for key, value in DISPENSER_ENABLE_VALUES.items()}

DISPENSER_CONCENTRATION_VALUES = {
    "2x": 50,
    "3x": 33,
    "4x": 25,
    "5x": 20,
    "6x": 17,
    "8x": 13,
}
DISPENSER_CONCENTRATION_REVERSE = {
    value: key for key, value in DISPENSER_CONCENTRATION_VALUES.items()
}

DISPENSER_2_SELECTION_VALUES = {
    "detergent": 1,
    "softener": 2,
}
DISPENSER_2_SELECTION_REVERSE = {
    value: key for key, value in DISPENSER_2_SELECTION_VALUES.items()
}

ATTRVAL_MACHINE_STATE_STANDBY = "0"
ATTRVAL_MACHINE_STATE_SETTING = "1"
ATTRVAL_MACHINE_STATE_DELAY_COUNT_DOWN_MODE = "2"
ATTRVAL_MACHINE_STATE_DELAY_PAUSE = "3"
ATTRVAL_MACHINE_STATE_SMART_DELAY = "4"
ATTRVAL_MACHINE_STATE_SMART_GRID_PAUSE = "5"
ATTRVAL_MACHINE_STATE_PAUSE = "6"
ATTRVAL_MACHINE_STATE_RUNNING_MAIN_CYCLE = "7"
ATTRVAL_MACHINE_STATE_RUNNING_POST_CYCLE = "8"
ATTRVAL_MACHINE_STATE_EXCEPTIONS = "9"
ATTRVAL_MACHINE_STATE_COMPLETE = "10"
ATTRVAL_MACHINE_STATE_POWER_FAILURE = "11"
ATTRVAL_MACHINE_STATE_SERVICE_DIAGNOSTIC = "12"
ATTRVAL_MACHINE_STATE_FACTORY_DIAGNOSTIC = "13"
ATTRVAL_MACHINE_STATE_LIFE_TEST = "14"
ATTRVAL_MACHINE_STATE_CUSTOMER_FOCUS_MODE = "15"
ATTRVAL_MACHINE_STATE_DEMO_MODE = "16"
ATTRVAL_MACHINE_STATE_HARD_STOP_OR_ERROR = "17"
ATTRVAL_MACHINE_STATE_SYSTEM_INIT = "18"


class MachineState(Enum):
    Standby = 0
    Setting = 1
    DelayCountdownMode = 2
    DelayPause = 3
    SmartDelay = 4
    SmartGridPause = 5
    Pause = 6
    RunningMainCycle = 7
    RunningPostCycle = 8
    Exceptions = 9
    Complete = 10
    PowerFailure = 11
    ServiceDiagnostic = 12
    FactoryDiagnostic = 13
    LifeTest = 14
    CustomerFocusMode = 15
    DemoMode = 16
    HardStopOrError = 17
    SystemInit = 18


MACHINE_STATE_MAP = {
    ATTRVAL_MACHINE_STATE_STANDBY: MachineState.Standby,
    ATTRVAL_MACHINE_STATE_SETTING: MachineState.Setting,
    ATTRVAL_MACHINE_STATE_DELAY_COUNT_DOWN_MODE: MachineState.DelayCountdownMode,
    ATTRVAL_MACHINE_STATE_DELAY_PAUSE: MachineState.DelayPause,
    ATTRVAL_MACHINE_STATE_SMART_DELAY: MachineState.SmartDelay,
    ATTRVAL_MACHINE_STATE_SMART_GRID_PAUSE: MachineState.SmartGridPause,
    ATTRVAL_MACHINE_STATE_PAUSE: MachineState.Pause,
    ATTRVAL_MACHINE_STATE_RUNNING_MAIN_CYCLE: MachineState.RunningMainCycle,
    ATTRVAL_MACHINE_STATE_RUNNING_POST_CYCLE: MachineState.RunningPostCycle,
    ATTRVAL_MACHINE_STATE_EXCEPTIONS: MachineState.Exceptions,
    ATTRVAL_MACHINE_STATE_COMPLETE: MachineState.Complete,
    ATTRVAL_MACHINE_STATE_POWER_FAILURE: MachineState.PowerFailure,
    ATTRVAL_MACHINE_STATE_SERVICE_DIAGNOSTIC: MachineState.ServiceDiagnostic,
    ATTRVAL_MACHINE_STATE_FACTORY_DIAGNOSTIC: MachineState.FactoryDiagnostic,
    ATTRVAL_MACHINE_STATE_LIFE_TEST: MachineState.LifeTest,
    ATTRVAL_MACHINE_STATE_CUSTOMER_FOCUS_MODE: MachineState.CustomerFocusMode,
    ATTRVAL_MACHINE_STATE_DEMO_MODE: MachineState.DemoMode,
    ATTRVAL_MACHINE_STATE_HARD_STOP_OR_ERROR: MachineState.HardStopOrError,
    ATTRVAL_MACHINE_STATE_SYSTEM_INIT: MachineState.SystemInit,
}


class Washer(LaundryCommandsMixin, Appliance):
    def get_machine_state(self) -> MachineState | None:
        state_raw = self._get_attribute(ATTR_CYCLE_STATUS_MACHINE_STATE)
        if state_raw is None:
            return None
        return MACHINE_STATE_MAP.get(state_raw, None)

    def get_cycle_status_sensing(self) -> bool | None:
        return self.attr_value_to_bool(self._get_attribute(ATTR_CYCLE_STATUS_SENSING))

    def get_cycle_status_filling(self) -> bool | None:
        return self.attr_value_to_bool(self._get_attribute(ATTR_CYCLE_STATUS_FILLING))

    def get_cycle_status_soaking(self) -> bool | None:
        return self.attr_value_to_bool(self._get_attribute(ATTR_CYCLE_STATUS_SOAKING))

    def get_cycle_status_washing(self) -> bool | None:
        return self.attr_value_to_bool(self._get_attribute(ATTR_CYCLE_STATUS_WASHING))

    def get_cycle_status_rinsing(self) -> bool | None:
        return self.attr_value_to_bool(self._get_attribute(ATTR_CYCLE_STATUS_RINSING))

    def get_cycle_status_spinning(self) -> bool | None:
        return self.attr_value_to_bool(self._get_attribute(ATTR_CYCLE_STATUS_SPINNING))

    def get_dispense_1_level(self) -> int | None:
        return self._get_int_attribute(ATTR_DISPENSE_1_LEVEL)

    def get_dispense_2_level(self) -> int | None:
        return self._get_int_attribute(ATTR_DISPENSE_2_LEVEL)

    def get_door_open(self) -> bool | None:
        return self.attr_value_to_bool(self._get_attribute(ATTR_DOOR_OPEN))

    def get_time_remaining(self) -> int | None:
        return self._get_int_attribute(ATTR_CYCLE_STATUS_TIME_REMAINING)

    def get_wash_cycle_pair(self) -> tuple[str, str] | None:
        raw = self._get_int_attribute(ATTR_CYCLE_SELECT)
        return None if raw is None else WASH_CYCLE_REVERSE.get(raw)

    def is_fan_fresh_model_supported(self) -> bool:
        """Return whether this is the exact model proven to support Fan Fresh."""
        return self.appliance_info.model_number == FAN_FRESH_SUPPORTED_MODEL

    def supports_fan_fresh(self) -> bool:
        """Return whether this model currently exposes the required DDM fields."""
        return (
            self.is_fan_fresh_model_supported()
            and self.has_attribute(ATTR_FRESHENING_SELECT)
            and self.has_attribute(ATTR_CHANGE_STATUS_FRESHENING)
        )

    def get_fan_fresh(self) -> str | None:
        """Return the current Fan Fresh option."""
        raw = self._get_int_attribute(ATTR_FRESHENING_SELECT)
        return None if raw is None else FRESHENING_REVERSE.get(raw)

    def fan_fresh_changeable(self) -> bool | None:
        """Return the appliance-reported Fan Fresh changeability flag."""
        return self.attr_value_to_bool(
            self._get_attribute(ATTR_CHANGE_STATUS_FRESHENING)
        )

    async def set_fan_fresh(self, option: str) -> bool:
        """Set Fan Fresh using the exact WFW9620HBK3 DDM enum mapping."""
        if not self.supports_fan_fresh():
            return False
        return await self._set_enum_attribute(
            ATTR_FRESHENING_SELECT, FRESHENING_VALUES, option
        )

    async def set_wash_cycle_pair(self, what: str, how: str) -> bool:
        value = WASH_CYCLE_MATRIX.get((what, how))
        if value is None or not self.has_attribute(ATTR_CYCLE_SELECT):
            return False
        return await self.send_attributes({ATTR_CYCLE_SELECT: str(value)})

    def get_dispense_1_enable(self) -> str | None:
        raw = self._get_int_attribute(ATTR_DISPENSE_1_ENABLE)
        return None if raw is None else DISPENSER_ENABLE_REVERSE.get(raw)

    async def set_dispense_1_enable(self, option: str) -> bool:
        return await self._set_enum_attribute(
            ATTR_DISPENSE_1_ENABLE, DISPENSER_ENABLE_VALUES, option
        )

    def get_dispense_2_enable(self) -> str | None:
        raw = self._get_int_attribute(ATTR_DISPENSE_2_ENABLE)
        return None if raw is None else DISPENSER_ENABLE_REVERSE.get(raw)

    async def set_dispense_2_enable(self, option: str) -> bool:
        return await self._set_enum_attribute(
            ATTR_DISPENSE_2_ENABLE, DISPENSER_ENABLE_VALUES, option
        )

    def get_dispense_1_concentration(self) -> str | None:
        raw = self._get_int_attribute(ATTR_DISPENSE_1_CONCENTRATION)
        return None if raw is None else DISPENSER_CONCENTRATION_REVERSE.get(raw)

    async def set_dispense_1_concentration(self, option: str) -> bool:
        return await self._set_enum_attribute(
            ATTR_DISPENSE_1_CONCENTRATION, DISPENSER_CONCENTRATION_VALUES, option
        )

    def get_dispense_2_concentration(self) -> str | None:
        raw = self._get_int_attribute(ATTR_DISPENSE_2_CONCENTRATION)
        return None if raw is None else DISPENSER_CONCENTRATION_REVERSE.get(raw)

    async def set_dispense_2_concentration(self, option: str) -> bool:
        return await self._set_enum_attribute(
            ATTR_DISPENSE_2_CONCENTRATION, DISPENSER_CONCENTRATION_VALUES, option
        )

    def get_dispense_2_selection(self) -> str | None:
        raw = self._get_int_attribute(ATTR_DISPENSE_2_SELECTION)
        return None if raw is None else DISPENSER_2_SELECTION_REVERSE.get(raw)

    async def set_dispense_2_selection(self, option: str) -> bool:
        return await self._set_enum_attribute(
            ATTR_DISPENSE_2_SELECTION, DISPENSER_2_SELECTION_VALUES, option
        )

    async def _set_enum_attribute(
        self, attribute: str, values: dict[str, int], option: str
    ) -> bool:
        value = values.get(option)
        if value is None or not self.has_attribute(attribute):
            return False
        return await self.send_attributes({attribute: str(value)})
