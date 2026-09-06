"""Shared API144 laundry command implementation for Washer and Dryer.

This module targets the whirlpool-sixth-sense 1.3.1 baseline, in which
Washer and Dryer are single concrete classes (whirlpool.washer.Washer,
whirlpool.dryer.Dryer) with no separate transport-implementation split —
there is no whirlpool.httpapi / whirlpool.awsiot namespace at this
baseline. Because of that, this mixin is placed directly on the one
existing Washer/Dryer implementation rather than on an abstract common
interface. See CHANGES.md ("Common ABC vs implementation-specific API")
for the full architectural rationale: expanding a shared abstract
interface makes sense once a second (e.g. AWS-IoT) transport
implementation exists that would otherwise be forced to fake support for
commands it cannot actually perform. At 1.3.1 there is no second
implementation to force anything onto, so that concern does not apply
here, and adding these methods straight to the concrete classes is the
smaller, more accurate change.

Evidence basis: all wire attribute names, values, and the read-only
classification of Remote Enable come from a live, server-delivered
Device Data Model (DDM) response and its accompanying rule engine,
captured from a real WFW9620HBK3 washer and WED9620HBK2 dryer. See the
project's Phase 5B-5D analysis artifacts for the full derivation. This is
unchanged from the 2.x fork of this same feature; only the surrounding
class structure differs between library versions.

Safety boundary (do not weaken without new, explicit authorization):
- XCat_RemoteSetRemoteControlEnable is READ-ONLY here. There is no
  setter, no toggle, no generic attribute writer exposed for it anywhere
  in this module or in the classes that use it. Enabling/disabling
  Remote Control must be done at the physical appliance.
- Only four Cavity_OpSetOperations values are exposed, because only
  these four were proven against a live DDM response: Cancel (1),
  Start (2), Pause (5), Resume (6). SetOnDisplay (3), Save (9),
  SaveAndStart (10), and Modify (1001) are deliberately NOT exposed
  here - there is no DDM evidence backing their behavior.
"""

from typing import Protocol

ATTR_REMOTE_CONTROL_ENABLE = "XCat_RemoteSetRemoteControlEnable"
ATTR_OPERATIONS = "Cavity_OpSetOperations"

# Proven against a live DDM response for both a WFW9620HBK3 washer and a
# WED9620HBK2 dryer. Do not add SET_ON_DISPLAY (3), SAVE (9),
# SAVE_AND_START (10), or MODIFY (1001) without new DDM evidence.
OPERATION_CANCEL = "1"
OPERATION_START = "2"
OPERATION_PAUSE = "5"
OPERATION_RESUME = "6"


class _AttributeSource(Protocol):
    """Structural type for the host class's existing Appliance helpers.

    whirlpool.appliance.Appliance (1.3.1) already defines has_attribute,
    _get_attribute, attr_value_to_bool, and send_attributes; this Protocol
    exists only so type checkers can verify LaundryCommandsMixin's use of
    them without this module importing Appliance directly (avoids a
    circular import, since Appliance itself does not need to know about
    laundry commands).
    """

    def has_attribute(self, attribute: str) -> bool: ...
    def _get_attribute(self, attribute: str) -> str | None: ...
    def attr_value_to_bool(self, val: str | None) -> bool | None: ...
    async def send_attributes(self, attributes: dict[str, str]) -> bool: ...


class LaundryCommandsMixin:
    """Start/Pause/Resume/Cancel + read-only Remote Enable status.

    Mixed into whirlpool.washer.Washer and whirlpool.dryer.Dryer. Shared
    here (rather than duplicated in both files) because the underlying
    wire protocol is identical for washers and dryers at the API144
    level - only the Home Assistant-layer MachineState gating differs
    between the two, and that gating deliberately does not live here
    (see the paired Home Assistant integration fork's button.py and its
    own CHANGES.md).
    """

    def get_remote_control_enabled(self: _AttributeSource) -> bool | None:
        """Return whether Remote Control is enabled on the appliance.

        Read-only. Returns None if the attribute has not been fetched
        yet (fetch_data() has not completed), matching every other
        get_* accessor's None-when-unknown convention on this class.
        There is no corresponding setter anywhere in this fork.
        """
        return self.attr_value_to_bool(self._get_attribute(ATTR_REMOTE_CONTROL_ENABLE))

    async def _send_operation(self: _AttributeSource, operation: str) -> bool:
        """Send one Cavity_OpSetOperations value via the existing transport.

        Uses the same send_attributes() -> POST /api/v1/appliance/command
        path every other command on this class already uses. No new
        transport, no new endpoint.

        Protocol-level guard only: if appliance data has never been
        fetched (has_attribute is False for every attribute, including
        this one, before the first successful fetch_data()), refuses to
        send rather than emitting a request for an appliance we have no
        confirmed data for at all. This is deliberately the only guard
        at this layer - live-state-based gating (Remote Enable value,
        current MachineState) is Home Assistant integration policy, not
        library policy; see this module's docstring.
        """
        if not self.has_attribute(ATTR_REMOTE_CONTROL_ENABLE):
            return False
        return await self.send_attributes({ATTR_OPERATIONS: operation})

    async def start(self: _AttributeSource) -> bool:
        """Start the currently-set cycle (Cavity_OpSetOperations = 2)."""
        return await self._send_operation(OPERATION_START)

    async def pause(self: _AttributeSource) -> bool:
        """Pause the running cycle (Cavity_OpSetOperations = 5)."""
        return await self._send_operation(OPERATION_PAUSE)

    async def resume(self: _AttributeSource) -> bool:
        """Resume a paused cycle (Cavity_OpSetOperations = 6)."""
        return await self._send_operation(OPERATION_RESUME)

    async def cancel(self: _AttributeSource) -> bool:
        """Cancel the current cycle (Cavity_OpSetOperations = 1)."""
        return await self._send_operation(OPERATION_CANCEL)
