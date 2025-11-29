"""Shared test fixtures for ShutterScope tests."""

import pytest

from shutterscope.oscilloscope import WaveformData


class MockOscilloscope:
    """Mock oscilloscope for testing without hardware."""

    def __init__(self) -> None:
        self._connected = False
        self._waveform_data: WaveformData | None = None
        self._waveforms_data: dict[int, WaveformData] | None = None

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def configure_timebase(
        self,
        max_duration: float,
        sample_interval: float = 1e-6,
        channels: list[int] | None = None,
    ) -> None:
        pass

    def setup_edge_trigger(
        self, channel: int, level: float, slope: str = "NEG"
    ) -> None:
        pass

    def wait_for_trigger(self) -> None:
        pass

    def get_waveform(self, channel: int) -> WaveformData:
        if self._waveform_data is not None:
            return self._waveform_data
        # Return a simple test waveform: 100 samples at 1MHz
        voltages = [0.0 if i < 20 or i >= 80 else 3.3 for i in range(100)]
        return WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    def get_waveforms(self, channels: list[int]) -> dict[int, WaveformData]:
        """Retrieve waveform data from multiple channels."""
        if self._waveforms_data is not None:
            return self._waveforms_data
        # Return test waveforms with slight timing offsets for three-point testing
        result = {}
        for i, channel in enumerate(channels):
            # Offset pulses by 5 samples each to simulate shutter travel
            offset = i * 5
            voltages = [
                0.0 if j < (20 + offset) or j >= (80 + offset) else 3.3
                for j in range(100)
            ]
            result[channel] = WaveformData(
                voltages=voltages, sample_rate=1e6, start_time=0.0
            )
        return result

    def set_waveform(self, waveform: WaveformData) -> None:
        """Set custom waveform data for testing."""
        self._waveform_data = waveform

    def set_waveforms(self, waveforms: dict[int, WaveformData]) -> None:
        """Set custom waveform data for multi-channel testing."""
        self._waveforms_data = waveforms


@pytest.fixture
def mock_oscilloscope() -> MockOscilloscope:
    """Provide a mock oscilloscope for testing."""
    return MockOscilloscope()
