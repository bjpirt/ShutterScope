"""Tests for RigolDS1000Z oscilloscope implementation."""

from typing import Any

import pytest

from shutterscope.rigol_ds1000z import RigolDS1000Z


class MockVisaInstrument:
    """Mock VISA instrument that records commands and returns configured responses."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, str]] = []
        self.query_responses: dict[str, str] = {}
        self.binary_data: list[int] = []
        self.closed = False

    def write(self, command: str) -> None:
        self.commands.append(("write", command))

    def query(self, command: str) -> str:
        self.commands.append(("query", command))
        return self.query_responses.get(command, "")

    def query_binary_values(
        self, command: str, datatype: str = "B", container: Any = list
    ) -> list[int]:
        self.commands.append(("query_binary_values", command))
        return self.binary_data

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def mock_instrument() -> MockVisaInstrument:
    """Provide a mock VISA instrument for testing."""
    return MockVisaInstrument()


@pytest.fixture
def scope_with_mock(mock_instrument: MockVisaInstrument) -> RigolDS1000Z:
    """Provide a RigolDS1000Z with injected mock instrument."""
    return RigolDS1000Z("TEST::RESOURCE", instrument=mock_instrument)


# Error handling tests


def test_configure_timebase_raises_when_not_connected() -> None:
    """Verify configure_timebase raises RuntimeError when not connected."""
    scope = RigolDS1000Z("TEST::RESOURCE")

    with pytest.raises(RuntimeError, match="Not connected"):
        scope.configure_timebase(max_duration=1.0)


def test_setup_edge_trigger_raises_when_not_connected() -> None:
    """Verify setup_edge_trigger raises RuntimeError when not connected."""
    scope = RigolDS1000Z("TEST::RESOURCE")

    with pytest.raises(RuntimeError, match="Not connected"):
        scope.setup_edge_trigger(channel=1, level=0.5)


def test_wait_for_trigger_raises_when_not_connected() -> None:
    """Verify wait_for_trigger raises RuntimeError when not connected."""
    scope = RigolDS1000Z("TEST::RESOURCE")

    with pytest.raises(RuntimeError, match="Not connected"):
        scope.wait_for_trigger()


def test_get_waveform_raises_when_not_connected() -> None:
    """Verify get_waveform raises RuntimeError when not connected."""
    scope = RigolDS1000Z("TEST::RESOURCE")

    with pytest.raises(RuntimeError, match="Not connected"):
        scope.get_waveform(channel=1)


# Disconnect test


def test_disconnect_closes_instrument(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify disconnect() calls close() on the instrument."""
    scope_with_mock.disconnect()

    assert mock_instrument.closed is True
    assert scope_with_mock._instrument is None


def test_disconnect_when_not_connected() -> None:
    """Verify disconnect() does nothing when not connected."""
    scope = RigolDS1000Z("TEST::RESOURCE")
    scope.disconnect()  # Should not raise


# configure_timebase tests


def test_configure_timebase_sends_all_commands(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify configure_timebase sends all required commands."""
    # max_duration=1.0: time_per_div = 1.0/10 = 0.1, trigger_offset = -0.1*5 = -0.5
    scope_with_mock.configure_timebase(max_duration=1.0, sample_interval=1e-6)

    assert mock_instrument.commands[0] == ("write", ":STOP")

    write_commands = [cmd for op, cmd in mock_instrument.commands if op == "write"]
    assert ":TIMebase:MAIN:SCALe 0.1" in write_commands
    assert ":TIMebase:MAIN:OFFSet -0.5" in write_commands
    # Memory depth command present
    assert any(":ACQuire:MDEPth" in cmd for cmd in write_commands)
    # Default channel 1 configured
    assert ":CHAN1:SCALe 0.5" in write_commands
    assert ":CHAN1:OFFSet -1.5" in write_commands
    assert ":CHAN1:DISPlay ON" in write_commands


def test_configure_timebase_configures_multiple_channels(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify configure_timebase configures all specified channels."""
    scope_with_mock.configure_timebase(max_duration=1.0, channels=[1, 2, 3])

    write_commands = [cmd for op, cmd in mock_instrument.commands if op == "write"]
    for ch in [1, 2, 3]:
        assert f":CHAN{ch}:SCALe 0.5" in write_commands
        assert f":CHAN{ch}:OFFSet -1.5" in write_commands
        assert f":CHAN{ch}:DISPlay ON" in write_commands


def test_configure_timebase_memory_depth_selection() -> None:
    """Test memory depth selection algorithm picks closest valid depth."""
    assert RigolDS1000Z.MEMORY_DEPTHS == [1000, 10000, 100000, 1000000, 6000000, 12000000]


# setup_edge_trigger tests


def test_setup_edge_trigger_sends_all_commands(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify setup_edge_trigger sends correct commands for both slopes."""
    scope_with_mock.setup_edge_trigger(channel=1, level=0.5, slope="NEG")

    write_commands = [cmd for op, cmd in mock_instrument.commands if op == "write"]
    assert ":TRIGger:MODE EDGE" in write_commands
    assert ":TRIGger:EDGe:SOURce CHAN1" in write_commands
    assert ":TRIGger:EDGe:LEVel 0.5" in write_commands
    assert ":TRIGger:EDGe:SLOPe NEGative" in write_commands
    assert ":TRIGger:SWEep SINGle" in write_commands
    assert ":SINGle" in write_commands

    # Test with different channel, level, and positive slope
    mock_instrument.commands.clear()
    scope_with_mock.setup_edge_trigger(channel=2, level=1.0, slope="POS")

    write_commands = [cmd for op, cmd in mock_instrument.commands if op == "write"]
    assert ":TRIGger:EDGe:SOURce CHAN2" in write_commands
    assert ":TRIGger:EDGe:LEVel 1.0" in write_commands
    assert ":TRIGger:EDGe:SLOPe POSitive" in write_commands


# wait_for_trigger tests


def test_wait_for_trigger_returns_on_completion_status(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify wait_for_trigger returns when status is TD or STOP."""
    mock_instrument.query_responses[":TRIGger:STATus?"] = "TD"
    scope_with_mock.wait_for_trigger()
    assert ("query", ":TRIGger:STATus?") in mock_instrument.commands

    mock_instrument.commands.clear()
    mock_instrument.query_responses[":TRIGger:STATus?"] = "STOP"
    scope_with_mock.wait_for_trigger()  # Should also return immediately


# get_waveform tests


def test_get_waveform_configures_source_and_mode(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify get_waveform configures waveform source, mode, and returns sample rate."""
    mock_instrument.query_responses[":ACQuire:MDEPth?"] = "1000"
    mock_instrument.query_responses[":CHAN1:SCALe?"] = "0.5"
    mock_instrument.query_responses[":CHAN1:OFFSet?"] = "-1.5"
    mock_instrument.query_responses[":ACQuire:SRATe?"] = "500000"
    mock_instrument.query_responses[":TIMebase:MAIN:OFFSet?"] = "-0.5"
    mock_instrument.binary_data = [128] * 1000

    waveform = scope_with_mock.get_waveform(channel=1)

    write_commands = [cmd for op, cmd in mock_instrument.commands if op == "write"]
    assert ":WAVeform:SOURce CHAN1" in write_commands
    assert ":WAVeform:MODE RAW" in write_commands
    assert ":WAVeform:FORMat BYTE" in write_commands
    assert waveform.sample_rate == 500000


def test_get_waveform_voltage_conversion(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify get_waveform correctly converts bytes to voltages."""
    # Set up mock responses
    mock_instrument.query_responses[":ACQuire:MDEPth?"] = "3"
    mock_instrument.query_responses[":CHAN1:SCALe?"] = "0.5"  # y_increment = 0.5/32 = 0.015625
    mock_instrument.query_responses[":CHAN1:OFFSet?"] = "0.0"  # No offset
    mock_instrument.query_responses[":ACQuire:SRATe?"] = "1000000"
    mock_instrument.query_responses[":TIMebase:MAIN:OFFSet?"] = "0.0"

    # Test data: 128 = 0V, 0 = negative, 255 = positive
    # voltage = (byte - 128) * y_increment - chan_offset
    # byte 128: (128 - 128) * 0.015625 - 0 = 0V
    # byte 0: (0 - 128) * 0.015625 - 0 = -2V
    # byte 255: (255 - 128) * 0.015625 - 0 = 1.984375V
    mock_instrument.binary_data = [128, 0, 255]

    waveform = scope_with_mock.get_waveform(channel=1)

    assert len(waveform.voltages) == 3
    assert waveform.voltages[0] == pytest.approx(0.0, abs=0.001)
    assert waveform.voltages[1] == pytest.approx(-2.0, abs=0.001)
    assert waveform.voltages[2] == pytest.approx(1.984375, abs=0.001)


def test_get_waveform_voltage_conversion_with_offset(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify get_waveform correctly applies channel offset."""
    mock_instrument.query_responses[":ACQuire:MDEPth?"] = "1"
    mock_instrument.query_responses[":CHAN1:SCALe?"] = "0.5"
    mock_instrument.query_responses[":CHAN1:OFFSet?"] = "-1.5"  # Offset of -1.5V
    mock_instrument.query_responses[":ACQuire:SRATe?"] = "1000000"
    mock_instrument.query_responses[":TIMebase:MAIN:OFFSet?"] = "0.0"

    # byte 128 with offset -1.5: (128 - 128) * 0.015625 - (-1.5) = 1.5V
    mock_instrument.binary_data = [128]

    waveform = scope_with_mock.get_waveform(channel=1)

    assert waveform.voltages[0] == pytest.approx(1.5, abs=0.001)


def test_get_waveform_timing_calculation(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify get_waveform calculates correct start time."""
    mock_instrument.query_responses[":ACQuire:MDEPth?"] = "1000"
    mock_instrument.query_responses[":CHAN1:SCALe?"] = "0.5"
    mock_instrument.query_responses[":CHAN1:OFFSet?"] = "0.0"
    mock_instrument.query_responses[":ACQuire:SRATe?"] = "1000000"  # 1MHz
    mock_instrument.query_responses[":TIMebase:MAIN:OFFSet?"] = "-0.0005"  # -500µs
    mock_instrument.binary_data = [128] * 1000

    waveform = scope_with_mock.get_waveform(channel=1)

    # total_duration = 1000 / 1000000 = 0.001s = 1ms
    # x_origin = -(0.001 / 2) + (-0.0005) = -0.0005 - 0.0005 = -0.001s
    assert waveform.start_time == pytest.approx(-0.001, abs=1e-6)
    assert waveform.sample_rate == 1000000


# get_waveforms tests


def test_get_waveforms_returns_all_channels(
    scope_with_mock: RigolDS1000Z, mock_instrument: MockVisaInstrument
) -> None:
    """Verify get_waveforms returns data for all requested channels."""
    mock_instrument.query_responses[":ACQuire:MDEPth?"] = "100"
    mock_instrument.query_responses[":CHAN1:SCALe?"] = "0.5"
    mock_instrument.query_responses[":CHAN1:OFFSet?"] = "0.0"
    mock_instrument.query_responses[":CHAN2:SCALe?"] = "0.5"
    mock_instrument.query_responses[":CHAN2:OFFSet?"] = "0.0"
    mock_instrument.query_responses[":CHAN3:SCALe?"] = "0.5"
    mock_instrument.query_responses[":CHAN3:OFFSet?"] = "0.0"
    mock_instrument.query_responses[":ACQuire:SRATe?"] = "1000000"
    mock_instrument.query_responses[":TIMebase:MAIN:OFFSet?"] = "0.0"
    mock_instrument.binary_data = [128] * 100

    waveforms = scope_with_mock.get_waveforms([1, 2, 3])

    assert len(waveforms) == 3
    assert 1 in waveforms
    assert 2 in waveforms
    assert 3 in waveforms
