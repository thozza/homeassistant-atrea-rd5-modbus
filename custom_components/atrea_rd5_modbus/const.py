"""Constants, register map, and pure conversion functions for Atrea RD5 Modbus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

DOMAIN = "atrea_rd5_modbus"

CONF_UNIT_ID = "unit_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 30


class RegisterType(Enum):
    INPUT = "input"
    HOLDING = "holding"
    COIL = "coil"


@dataclass(frozen=True)
class RegisterEntry:
    address: int
    register_type: RegisterType
    convert: Callable[[int], float | str | None]


@dataclass
class BatchGroup:
    register_type: RegisterType
    start_address: int
    count: int
    keys: list[str]


def signed10(val: int) -> float:
    """Convert 16-bit unsigned Modbus register value to temperature in °C.

    The Atrea RD5 encodes temperatures as tenths of degrees Celsius using a
    16-bit unsigned value where values > 32767 represent negative temperatures
    (two's complement style over 16 bits).

    Spec ranges: 1..1300 → 0.1..130.0 °C, 65036..65535 → -50.0..-0.1 °C
    """
    if val > 32767:
        val -= 65536
    return val / 10.0


def encode_signed10(temp_c: float) -> int:
    """Encode -50.0..130.0 °C as a 16-bit register value (×10, two's complement)."""
    val = round(temp_c * 10)
    if val < 0:
        val += 65536
    return val


OPERATION_MODES: dict[int, str] = {
    0: "Off",
    1: "Automatic",
    2: "Ventilation",
    3: "Circulation+Ventilation",
    4: "Circulation",
    5: "Night cooling",
    6: "Redistribution",
    7: "Overpressure",
}

OPERATION_MODE_OPTIONS: list[str] = list(OPERATION_MODES.values())


def _convert_mode(val: int) -> str | None:
    return OPERATION_MODES.get(val)


TODA_SOURCES: dict[int, str] = {
    0: "Internal",
    1: "BMS",
}
TODA_SOURCE_OPTIONS: list[str] = list(TODA_SOURCES.values())
TODA_SOURCES_INV: dict[str, int] = {v: k for k, v in TODA_SOURCES.items()}


def _convert_toda_source(val: int) -> str | None:
    return TODA_SOURCES.get(val)


TIDA_SOURCES: dict[int, str] = {
    0: "CP",
    1: "T-ETA",
    2: "TRKn",
    3: "BMS",
}
TIDA_SOURCE_OPTIONS: list[str] = list(TIDA_SOURCES.values())
TIDA_SOURCES_INV: dict[str, int] = {v: k for k, v in TIDA_SOURCES.items()}


def _convert_tida_source(val: int) -> str | None:
    return TIDA_SOURCES.get(val)


REGISTER_MAP: dict[str, RegisterEntry] = {
    "temp_oda": RegisterEntry(address=10211, register_type=RegisterType.INPUT, convert=signed10),
    "temp_sup": RegisterEntry(address=10212, register_type=RegisterType.INPUT, convert=signed10),
    "temp_eta": RegisterEntry(address=10213, register_type=RegisterType.INPUT, convert=signed10),
    "temp_eha": RegisterEntry(address=10214, register_type=RegisterType.INPUT, convert=signed10),
    "temp_ida": RegisterEntry(address=10215, register_type=RegisterType.INPUT, convert=signed10),
    "tida_source": RegisterEntry(address=10514, register_type=RegisterType.HOLDING, convert=_convert_tida_source),
    "power": RegisterEntry(address=10704, register_type=RegisterType.HOLDING, convert=float),
    "mode": RegisterEntry(address=10705, register_type=RegisterType.HOLDING, convert=_convert_mode),
    "toda_source": RegisterEntry(address=10510, register_type=RegisterType.COIL, convert=_convert_toda_source),
}


@dataclass(frozen=True)
class WriteRegisterEntry:
    address: int
    register_type: RegisterType  # HOLDING or COIL
    encode: Callable[[Any], int]


WRITE_REGISTER_MAP: dict[str, WriteRegisterEntry] = {
    "bms_toda": WriteRegisterEntry(10213, RegisterType.HOLDING, encode_signed10),
    "bms_tida": WriteRegisterEntry(10214, RegisterType.HOLDING, encode_signed10),
    "toda_source": WriteRegisterEntry(10510, RegisterType.COIL, lambda v: TODA_SOURCES_INV[v]),
    "tida_source": WriteRegisterEntry(10514, RegisterType.HOLDING, lambda v: TIDA_SOURCES_INV[v]),
}


def build_batch_groups(register_map: dict[str, RegisterEntry]) -> list[BatchGroup]:
    """Compile a register map into contiguous batch groups for efficient reading.

    Registers of the same type at consecutive addresses are merged into a single
    Modbus read request. Non-consecutive addresses become separate batches.
    """
    by_type: dict[RegisterType, list[tuple[int, str]]] = {}
    for key, entry in register_map.items():
        by_type.setdefault(entry.register_type, []).append((entry.address, key))

    groups: list[BatchGroup] = []
    for reg_type, addr_keys in by_type.items():
        sorted_pairs = sorted(addr_keys, key=lambda x: x[0])

        group_start = sorted_pairs[0][0]
        group_keys = [sorted_pairs[0][1]]

        for addr, key in sorted_pairs[1:]:
            if addr == group_start + len(group_keys):
                group_keys.append(key)
            else:
                groups.append(BatchGroup(reg_type, group_start, len(group_keys), list(group_keys)))
                group_start = addr
                group_keys = [key]

        groups.append(BatchGroup(reg_type, group_start, len(group_keys), list(group_keys)))

    return groups
