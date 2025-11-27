"""Oscilloscope protocol and implementations for ShutterScope."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class WaveformData:
    """Captured waveform data from an oscilloscope."""

    times: list[float]
    voltages: list[float]
    sample_rate: float


class OscilloscopeProtocol(Protocol):
    """Protocol defining the interface for oscilloscope implementations."""

    def connect(self) -> None:
        """Connect to the oscilloscope."""
        ...

    def disconnect(self) -> None:
        """Disconnect from the oscilloscope."""
        ...

    def setup_edge_trigger(
        self, channel: int, level: float, slope: str = "POS"
    ) -> None:
        """Configure edge trigger on the specified channel.

        Args:
            channel: Channel number (1-4)
            level: Trigger level in volts
            slope: Trigger slope - "POS" for rising edge, "NEG" for falling edge
        """
        ...

    def wait_for_trigger(self, timeout: float = 10.0) -> bool:
        """Wait for the oscilloscope to trigger.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if triggered, False if timeout occurred
        """
        ...

    def get_waveform(self, channel: int) -> WaveformData:
        """Retrieve waveform data from the specified channel.

        Args:
            channel: Channel number (1-4)

        Returns:
            WaveformData containing times, voltages, and sample rate
        """
        ...
