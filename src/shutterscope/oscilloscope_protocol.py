"""Oscilloscope protocol interface for ShutterScope."""

from __future__ import annotations

from typing import Protocol

from shutterscope.waveform_data import WaveformData


class OscilloscopeProtocol(Protocol):
    """Protocol defining the interface for oscilloscope implementations."""

    def connect(self) -> None:
        """Connect to the oscilloscope."""
        ...

    def disconnect(self) -> None:
        """Disconnect from the oscilloscope."""
        ...

    def configure_timebase(
        self, max_duration: float, sample_interval: float = 1e-6
    ) -> None:
        """Configure timebase for pulse capture.

        Args:
            max_duration: Maximum expected pulse duration in seconds
            sample_interval: Desired time between samples in seconds (default 1µs)
        """
        ...

    def setup_edge_trigger(
        self, channel: int, level: float, slope: str = "NEG"
    ) -> None:
        """Configure edge trigger on the specified channel.

        Args:
            channel: Channel number (1-4)
            level: Trigger level in volts
            slope: Trigger slope - "NEG" for falling edge, "POS" for rising edge
        """
        ...

    def wait_for_trigger(self) -> None:
        """Wait indefinitely for the oscilloscope to trigger."""
        ...

    def get_waveform(self, channel: int) -> WaveformData:
        """Retrieve waveform data from the specified channel.

        Args:
            channel: Channel number (1-4)

        Returns:
            WaveformData containing times, voltages, and sample rate
        """
        ...

    def get_waveforms(self, channels: list[int]) -> dict[int, WaveformData]:
        """Retrieve waveform data from multiple channels.

        All channels are captured with synchronized timing from the same trigger.

        Args:
            channels: List of channel numbers (1-4)

        Returns:
            Dictionary mapping channel number to WaveformData
        """
        ...
