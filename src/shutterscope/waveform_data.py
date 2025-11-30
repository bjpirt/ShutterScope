"""Waveform data class for ShutterScope."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WaveformData:
    """Captured waveform data from an oscilloscope.

    Stores voltage samples with uniform time spacing. Time values can be
    reconstructed as: time[i] = start_time + i / sample_rate
    """

    voltages: list[float]
    sample_rate: float
    start_time: float

    def get_times(self) -> list[float]:
        """Generate time values for each sample."""
        return [
            self.start_time + i / self.sample_rate for i in range(len(self.voltages))
        ]

    def trim(self, start_time: float, end_time: float) -> WaveformData:
        """Return a new WaveformData trimmed to the specified time range.

        Args:
            start_time: Start of trim window in seconds
            end_time: End of trim window in seconds

        Returns:
            New WaveformData containing only samples within the time range
        """
        start_idx = max(0, int((start_time - self.start_time) * self.sample_rate))
        end_idx = min(
            len(self.voltages), int((end_time - self.start_time) * self.sample_rate)
        )

        return WaveformData(
            voltages=self.voltages[start_idx:end_idx],
            sample_rate=self.sample_rate,
            start_time=self.start_time + start_idx / self.sample_rate,
        )
