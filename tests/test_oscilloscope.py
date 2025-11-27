"""Tests for oscilloscope protocol and implementations."""

from typing import Protocol, runtime_checkable

from shutterscope.oscilloscope import OscilloscopeProtocol, WaveformData

from .conftest import MockOscilloscope


def test_waveform_data_dataclass() -> None:
    """Verify WaveformData stores times, voltages, sample_rate correctly."""
    times = [0.0, 1e-6, 2e-6]
    voltages = [1.0, 2.0, 3.0]
    sample_rate = 1e6

    waveform = WaveformData(times=times, voltages=voltages, sample_rate=sample_rate)

    assert waveform.times == times
    assert waveform.voltages == voltages
    assert waveform.sample_rate == sample_rate


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
        def wait_for_trigger(self, timeout: float = 10.0) -> bool: ...
        def get_waveform(self, channel: int) -> WaveformData: ...

    mock = MockOscilloscope()
    assert isinstance(mock, RuntimeOscilloscopeProtocol)


def test_mock_oscilloscope_get_waveform() -> None:
    """Verify mock returns valid WaveformData."""
    mock = MockOscilloscope()

    waveform = mock.get_waveform(channel=1)

    assert isinstance(waveform, WaveformData)
    assert len(waveform.times) == len(waveform.voltages)
    assert len(waveform.times) > 0
    assert waveform.sample_rate > 0


def test_mock_oscilloscope_custom_waveform() -> None:
    """Verify mock can return custom waveform data."""
    mock = MockOscilloscope()
    custom_waveform = WaveformData(
        times=[0.0, 0.001],
        voltages=[5.0, 0.0],
        sample_rate=1000.0,
    )
    mock.set_waveform(custom_waveform)

    result = mock.get_waveform(channel=1)

    assert result.times == [0.0, 0.001]
    assert result.voltages == [5.0, 0.0]
    assert result.sample_rate == 1000.0


def test_mock_oscilloscope_wait_for_trigger_default() -> None:
    """Verify trigger returns True by default."""
    mock = MockOscilloscope()

    assert mock.wait_for_trigger(timeout=1.0) is True


def test_mock_oscilloscope_wait_for_trigger_configurable() -> None:
    """Verify trigger result can be configured."""
    mock = MockOscilloscope()
    mock.set_trigger_result(False)

    assert mock.wait_for_trigger(timeout=1.0) is False


def test_oscilloscope_protocol_is_protocol() -> None:
    """Verify OscilloscopeProtocol is a proper Protocol class."""
    # This test ensures we're using Protocol correctly
    # The class should have the Protocol base
    assert hasattr(OscilloscopeProtocol, "__protocol_attrs__") or issubclass(
        OscilloscopeProtocol, Protocol
    )
