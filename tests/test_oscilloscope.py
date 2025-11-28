"""Tests for oscilloscope protocol and implementations."""

from typing import Protocol, runtime_checkable

from shutterscope.oscilloscope import OscilloscopeProtocol, WaveformData

from .conftest import MockOscilloscope


def test_waveform_data_dataclass() -> None:
    """Verify WaveformData stores voltages, sample_rate, start_time correctly."""
    voltages = [1.0, 2.0, 3.0]
    sample_rate = 1e6
    start_time = -0.001

    waveform = WaveformData(
        voltages=voltages, sample_rate=sample_rate, start_time=start_time
    )

    assert waveform.voltages == voltages
    assert waveform.sample_rate == sample_rate
    assert waveform.start_time == start_time


def test_mock_oscilloscope_implements_protocol() -> None:
    """Verify MockOscilloscope satisfies OscilloscopeProtocol."""

    # Make OscilloscopeProtocol runtime checkable for this test
    @runtime_checkable
    class RuntimeOscilloscopeProtocol(Protocol):
        def connect(self) -> None: ...
        def disconnect(self) -> None: ...
        def configure_timebase(
            self, max_duration: float, sample_interval: float = 1e-6
        ) -> None: ...
        def setup_edge_trigger(
            self, channel: int, level: float, slope: str = "NEG"
        ) -> None: ...
        def wait_for_trigger(self) -> None: ...
        def get_waveform(self, channel: int) -> WaveformData: ...

    mock = MockOscilloscope()
    assert isinstance(mock, RuntimeOscilloscopeProtocol)


def test_mock_oscilloscope_get_waveform() -> None:
    """Verify mock returns valid WaveformData."""
    mock = MockOscilloscope()

    waveform = mock.get_waveform(channel=1)

    assert isinstance(waveform, WaveformData)
    assert len(waveform.voltages) > 0
    assert waveform.sample_rate > 0


def test_mock_oscilloscope_custom_waveform() -> None:
    """Verify mock can return custom waveform data."""
    mock = MockOscilloscope()
    custom_waveform = WaveformData(
        voltages=[5.0, 0.0],
        sample_rate=1000.0,
        start_time=0.0,
    )
    mock.set_waveform(custom_waveform)

    result = mock.get_waveform(channel=1)

    assert result.voltages == [5.0, 0.0]
    assert result.sample_rate == 1000.0
    assert result.start_time == 0.0


def test_oscilloscope_protocol_is_protocol() -> None:
    """Verify OscilloscopeProtocol is a proper Protocol class."""
    # This test ensures we're using Protocol correctly
    # The class should have the Protocol base
    assert hasattr(OscilloscopeProtocol, "__protocol_attrs__") or issubclass(
        OscilloscopeProtocol, Protocol
    )


def test_waveform_trim_basic() -> None:
    """Test basic waveform trimming."""
    # 100 samples at 1MHz starting at t=0
    voltages = list(range(100))
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    # Trim to samples 20-80 (20µs to 80µs)
    trimmed = waveform.trim(20e-6, 80e-6)

    assert len(trimmed.voltages) == 60
    assert trimmed.voltages[0] == 20
    assert trimmed.voltages[-1] == 79
    assert trimmed.sample_rate == 1e6
    assert trimmed.start_time == 20e-6


def test_waveform_trim_with_negative_start_time() -> None:
    """Test trimming waveform with negative start time."""
    # 100 samples at 1MHz starting at t=-50µs
    voltages = list(range(100))
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=-50e-6)

    # Trim to -20µs to +20µs (samples 30-70)
    trimmed = waveform.trim(-20e-6, 20e-6)

    assert len(trimmed.voltages) == 40
    assert trimmed.voltages[0] == 30
    assert trimmed.start_time == -20e-6


def test_waveform_trim_clamps_to_bounds() -> None:
    """Test that trim clamps to waveform boundaries."""
    voltages = list(range(100))
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    # Try to trim beyond boundaries
    trimmed = waveform.trim(-50e-6, 200e-6)

    # Should return all samples since requested range exceeds data
    assert len(trimmed.voltages) == 100
    assert trimmed.start_time == 0.0


def test_waveform_trim_preserves_sample_rate() -> None:
    """Test that trim preserves sample rate."""
    waveform = WaveformData(voltages=list(range(100)), sample_rate=2e6, start_time=0.0)

    trimmed = waveform.trim(10e-6, 40e-6)

    assert trimmed.sample_rate == 2e6
