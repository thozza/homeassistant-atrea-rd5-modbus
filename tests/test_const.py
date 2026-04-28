"""Unit tests for const.py pure functions."""
from __future__ import annotations

import pytest

from custom_components.atrea_rd5_modbus.const import (
    REGISTER_MAP,
    RegisterEntry,
    RegisterType,
    build_batch_groups,
    signed10,
    TIDA_SOURCES,
    TIDA_SOURCES_INV,
    TODA_SOURCES,
    TODA_SOURCES_INV,
    encode_signed10,
)

# --- signed10 ---

@pytest.mark.parametrize("raw, expected", [
    (200,   20.0),    # typical positive
    (0,      0.0),    # zero
    (1,      0.1),    # smallest positive
    (1300, 130.0),    # spec max positive
    (65535,  pytest.approx(-0.1)),   # (65535-65536)/10
    (65036,  pytest.approx(-50.0)),  # spec min negative
    (32767,  pytest.approx(3276.7)), # boundary: last positive
    (32768,  pytest.approx(-3276.8)),# boundary: first negative
])
def test_signed10(raw: int, expected: float) -> None:
    assert signed10(raw) == expected


# --- build_batch_groups: REGISTER_MAP produces exactly 2 groups ---

def test_build_batch_groups_returns_two_groups():
    groups = build_batch_groups(REGISTER_MAP)
    assert len(groups) == 2


def test_build_batch_groups_has_input_and_holding():
    groups = build_batch_groups(REGISTER_MAP)
    types = {g.register_type for g in groups}
    assert types == {RegisterType.INPUT, RegisterType.HOLDING}


@pytest.mark.parametrize("register_type, expected_start, expected_count, expected_keys", [
    (
        RegisterType.INPUT,
        10211,
        5,
        ["temp_oda", "temp_sup", "temp_eta", "temp_eha", "temp_ida"],
    ),
    (
        RegisterType.HOLDING,
        10704,
        2,
        ["power", "mode"],
    ),
])
def test_build_batch_groups_properties(
    register_type: RegisterType,
    expected_start: int,
    expected_count: int,
    expected_keys: list[str],
) -> None:
    groups = build_batch_groups(REGISTER_MAP)
    group = next(g for g in groups if g.register_type == register_type)
    assert group.start_address == expected_start
    assert group.count == expected_count
    assert group.keys == expected_keys


def test_build_batch_groups_non_consecutive_splits():
    """Registers that are not adjacent must produce separate batches."""
    sparse_map = {
        "a": RegisterEntry(address=100, register_type=RegisterType.INPUT, convert=float),
        "b": RegisterEntry(address=102, register_type=RegisterType.INPUT, convert=float),
    }
    groups = build_batch_groups(sparse_map)
    assert len(groups) == 2


@pytest.mark.parametrize("temp_c, expected", [
    (20.0,    200),
    (0.0,     0),
    (0.1,     1),
    (130.0,   1300),
    (-0.1,    65535),
    (-10.0,   65436),
    (-50.0,   65036),
])
def test_encode_signed10(temp_c: float, expected: int) -> None:
    assert encode_signed10(temp_c) == expected


@pytest.mark.parametrize("temp_c", [-50.0, -10.0, -0.1, 0.0, 0.1, 20.5, 130.0])
def test_encode_signed10_round_trip(temp_c: float) -> None:
    assert signed10(encode_signed10(temp_c)) == pytest.approx(temp_c)


def test_toda_sources_inv_round_trip() -> None:
    for code, name in TODA_SOURCES.items():
        assert TODA_SOURCES_INV[name] == code


def test_tida_sources_inv_round_trip() -> None:
    for code, name in TIDA_SOURCES.items():
        assert TIDA_SOURCES_INV[name] == code
