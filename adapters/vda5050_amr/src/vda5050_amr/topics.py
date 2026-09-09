"""VDA 5050 MQTT topic naming: `uagv/v2/<manufacturer>/<serialNumber>/<topic>`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vda5050Topics:
    manufacturer: str
    serial_number: str
    interface: str = "uagv"
    version: str = "v2"

    @property
    def _prefix(self) -> str:
        return f"{self.interface}/{self.version}/{self.manufacturer}/{self.serial_number}"

    @property
    def order(self) -> str:
        return f"{self._prefix}/order"

    @property
    def instant_actions(self) -> str:
        return f"{self._prefix}/instantActions"

    @property
    def state(self) -> str:
        return f"{self._prefix}/state"

    @property
    def visualization(self) -> str:
        return f"{self._prefix}/visualization"

    @property
    def connection(self) -> str:
        return f"{self._prefix}/connection"
