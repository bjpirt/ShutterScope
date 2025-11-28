"""Shared test fixtures for ShutterScope tests."""

import pytest

from shutterscope.oscilloscope import WaveformData


class MockOscilloscope:
    """Mock oscilloscope for testing without hardware."""

    def __init__(self) -> None:
        self._connected = False
        self._triggered = True
        self._waveform_data: WaveformData | None = None

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def configure_timebase(
        self, max_duration: float, sample_interval: float = 1e-6
    ) -> None:
        pass

    def setup_edge_trigger(
        self, channel: int, level: float, slope: str = "NEG"
    ) -> None:
        pass

    def wait_for_trigger(self, timeout: float = 10.0) -> bool:
        return self._triggered

    def get_waveform(self, channel: int) -> WaveformData:
        if self._waveform_data is not None:
            return self._waveform_data
        # Return a simple test waveform: 100 samples at 1MHz
        voltages = [0.0 if i < 20 or i >= 80 else 3.3 for i in range(100)]
        return WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    def set_waveform(self, waveform: WaveformData) -> None:
        """Set custom waveform data for testing."""
        self._waveform_data = waveform

    def set_trigger_result(self, triggered: bool) -> None:
        """Set whether wait_for_trigger returns True or False."""
        self._triggered = triggered


@pytest.fixture
def mock_oscilloscope() -> MockOscilloscope:
    """Provide a mock oscilloscope for testing."""
    return MockOscilloscope()
