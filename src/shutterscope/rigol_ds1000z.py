"""Rigol DS1000Z oscilloscope implementation for ShutterScope."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pyvisa

from shutterscope.waveform_data import WaveformData

if TYPE_CHECKING:
    from pyvisa.resources import MessageBasedResource


class RigolDS1000Z:
    """Rigol DS1000Z oscilloscope implementation using SCPI over VISA."""

    # Valid memory depth values for DS1000Z (single channel)
    MEMORY_DEPTHS = [1000, 10000, 100000, 1000000, 6000000, 12000000]

    @classmethod
    def auto_connect(cls) -> RigolDS1000Z:
        """Find first Rigol DS1000Z on VISA bus and return connected instance.

        Raises:
            ConnectionError: If no Rigol DS1000Z oscilloscope is found.
        """
        rm = pyvisa.ResourceManager()
        for resource in rm.list_resources():
            try:
                instr: MessageBasedResource = rm.open_resource(resource)  # type: ignore[assignment]
                idn = instr.query("*IDN?")
                if "RIGOL" in idn and "DS1" in idn:
                    instance = cls(resource)
                    instance._instrument = instr
                    return instance
                instr.close()
            except Exception:
                pass
        raise ConnectionError("No Rigol DS1000Z oscilloscope found")

    def __init__(self, resource: str) -> None:
        """Initialize with a VISA resource string.

        Args:
            resource: VISA resource string (e.g., "USB0::...")
        """
        self._resource = resource
        self._instrument: MessageBasedResource | None = None

    def connect(self) -> None:
        """Connect to the oscilloscope."""
        if self._instrument is None:
            rm = pyvisa.ResourceManager()
            self._instrument = rm.open_resource(self._resource)  # type: ignore[assignment]

    def disconnect(self) -> None:
        """Disconnect from the oscilloscope."""
        if self._instrument is not None:
            self._instrument.close()
            self._instrument = None

    def configure_timebase(
        self,
        max_duration: float,
        sample_interval: float = 1e-6,
        channels: list[int] | None = None,
    ) -> None:
        """Configure timebase for pulse capture.

        Sets up the oscilloscope to capture a pulse of up to max_duration seconds,
        with the trigger point near the right edge of the screen so most of the
        capture window shows the pulse before the falling edge trigger.

        Args:
            max_duration: Maximum expected pulse duration in seconds
            sample_interval: Desired time between samples in seconds (default 1µs)
            channels: List of channels to configure (default: [1])
        """
        if self._instrument is None:
            raise RuntimeError("Not connected to oscilloscope")

        if channels is None:
            channels = [1]

        # Stop acquisition before changing settings
        self._instrument.write(":STOP")

        # Calculate timebase scale (time per division)
        # DS1000Z has 12 horizontal divisions
        # We want max_duration to fit in ~10 divisions (leaving margin)
        time_per_div = max_duration / 10.0

        # Calculate memory depth needed for desired sample interval
        # Sample Rate = Memory Depth / (TimePerDiv * 12)
        # Memory Depth = Sample Rate * TimePerDiv * 12
        # Sample Rate = 1 / sample_interval
        total_time = time_per_div * 12
        desired_depth = int(total_time / sample_interval)

        # Find the closest valid memory depth to our requirement
        # Larger depth = higher sample rate (not longer time), so pick closest match
        memory_depth = self.MEMORY_DEPTHS[0]
        for depth in self.MEMORY_DEPTHS:
            if depth <= desired_depth:
                memory_depth = depth
            else:
                # Check if this larger depth is closer than the smaller one
                if abs(depth - desired_depth) < abs(memory_depth - desired_depth):
                    memory_depth = depth
                break

        # Set timebase scale first
        self._instrument.write(f":TIMebase:MAIN:SCALe {time_per_div}")

        # Set memory depth (must use valid values)
        self._instrument.write(f":ACQuire:MDEPth {memory_depth}")

        # Set trigger offset to put trigger near right edge of screen
        # Negative offset shifts trigger to the right, showing more pre-trigger data
        trigger_offset = -time_per_div * 5  # 5 divisions to the right
        self._instrument.write(f":TIMebase:MAIN:OFFSet {trigger_offset}")

        # Configure vertical scale for each channel
        # 0-2.5V signal with 1 div margin top/bottom
        # DS1000Z has 8 vertical divisions. With 0.5V/div, total range = 4V
        # Negative offset moves 0V down on screen
        # To put 0V at 1 div from bottom (3 divs below center): offset = -1.5V
        for channel in channels:
            self._instrument.write(f":CHAN{channel}:SCALe 0.5")
            self._instrument.write(f":CHAN{channel}:OFFSet -1.5")
            self._instrument.write(f":CHAN{channel}:DISPlay ON")

    def setup_edge_trigger(
        self, channel: int, level: float, slope: str = "NEG"
    ) -> None:
        """Configure edge trigger on the specified channel.

        Args:
            channel: Channel number (1-4)
            level: Trigger level in volts
            slope: Trigger slope - "NEG" for falling edge, "POS" for rising edge
        """
        if self._instrument is None:
            raise RuntimeError("Not connected to oscilloscope")

        self._instrument.write(":TRIGger:MODE EDGE")
        self._instrument.write(f":TRIGger:EDGe:SOURce CHAN{channel}")
        self._instrument.write(f":TRIGger:EDGe:LEVel {level}")
        slope_cmd = "POSitive" if slope == "POS" else "NEGative"
        self._instrument.write(f":TRIGger:EDGe:SLOPe {slope_cmd}")
        self._instrument.write(":TRIGger:SWEep SINGle")
        self._instrument.write(":SINGle")

    def wait_for_trigger(self) -> None:
        """Wait indefinitely for the oscilloscope to trigger."""
        if self._instrument is None:
            raise RuntimeError("Not connected to oscilloscope")

        while True:
            status = self._instrument.query(":TRIGger:STATus?").strip()
            if status in ("TD", "STOP"):
                return
            time.sleep(0.1)

    def get_waveform(self, channel: int) -> WaveformData:
        """Retrieve waveform data from the specified channel using RAW binary mode.

        Downloads the full memory depth in chunks for efficient transfer.

        Args:
            channel: Channel number (1-4)

        Returns:
            WaveformData containing times, voltages, and sample rate
        """
        if self._instrument is None:
            raise RuntimeError("Not connected to oscilloscope")

        # Ensure acquisition is stopped
        self._instrument.write(":STOP")
        time.sleep(0.1)  # Give scope time to finish stopping

        # Configure waveform source and RAW binary mode
        self._instrument.write(f":WAVeform:SOURce CHAN{channel}")
        self._instrument.write(":WAVeform:MODE RAW")
        self._instrument.write(":WAVeform:FORMat BYTE")

        # Query actual memory depth to know total points available
        mem_depth_str = self._instrument.query(":ACQuire:MDEPth?").strip()
        # Handle "AUTO" or numeric response
        if mem_depth_str == "AUTO":
            # Query the actual sample rate and calculate
            sample_rate = float(self._instrument.query(":ACQuire:SRATe?").strip())
            timebase_str = self._instrument.query(":TIMebase:MAIN:SCALe?")
            timebase = float(timebase_str.strip())
            total_points = int(sample_rate * timebase * 12)
        else:
            total_points = int(float(mem_depth_str))

        # Set initial range to get preamble with correct scaling
        self._instrument.write(":WAVeform:STARt 1")
        self._instrument.write(f":WAVeform:STOP {min(total_points, 250000)}")

        # Calculate y_increment from channel scale instead of trusting the preamble
        # The preamble values can be wrong in RAW mode (firmware bug)
        # DS1000Z has 8-bit ADC (256 levels) and 8 vertical divisions
        # y_increment = (scale_per_div * 8_divisions) / 256_levels = scale / 32
        chan_scale = float(self._instrument.query(f":CHAN{channel}:SCALe?").strip())
        y_increment = chan_scale / 32.0

        # Get channel offset for voltage calculation
        chan_offset = float(self._instrument.query(f":CHAN{channel}:OFFSet?").strip())

        # For RAW mode byte->voltage conversion:
        # - Raw bytes are unsigned 8-bit (0-255)
        # - Center of ADC range is 128, representing the channel's offset voltage
        # - voltage = (byte - 128) * y_increment + chan_offset
        y_reference = 128.0

        # Get actual sample rate (preamble x_increment is wrong in RAW mode)
        sample_rate = float(self._instrument.query(":ACQuire:SRATe?").strip())

        # Calculate x_origin for RAW mode
        # In RAW mode, we download the entire memory buffer. The trigger point
        # is at a specific position within this buffer, determined by the
        # trigger offset setting. Total duration = total_points / sample_rate.
        # The trigger offset tells us where t=0 is relative to screen center.
        total_duration = total_points / sample_rate
        trigger_offset = float(self._instrument.query(":TIMebase:MAIN:OFFSet?").strip())
        # With negative trigger offset, trigger is to the right of center,
        # meaning more pre-trigger data. The start of memory is at:
        # -(half of total duration) + trigger_offset
        # (trigger_offset is negative when trigger is right of center)
        x_origin = -(total_duration / 2) + trigger_offset

        # Read data in chunks (max 250000 points per read for stability)
        chunk_size = 250000
        raw_bytes: list[float] = []

        for start in range(1, total_points + 1, chunk_size):
            stop = min(start + chunk_size - 1, total_points)
            self._instrument.write(f":WAVeform:STARt {start}")
            self._instrument.write(f":WAVeform:STOP {stop}")

            # Read binary data (returns unsigned bytes)
            chunk = list(
                self._instrument.query_binary_values(
                    ":WAVeform:DATA?", datatype="B", container=list
                )
            )
            raw_bytes.extend(chunk)

        # Convert bytes to voltages
        # Raw byte 128 = center of display = chan_offset voltage
        # voltage = (byte - 128) * y_increment - chan_offset
        # (subtract offset because positive offset moves trace down)
        voltages = [
            (byte_val - y_reference) * y_increment - chan_offset
            for byte_val in raw_bytes
        ]

        return WaveformData(
            voltages=voltages, sample_rate=sample_rate, start_time=x_origin
        )

    def get_waveforms(self, channels: list[int]) -> dict[int, WaveformData]:
        """Retrieve waveform data from multiple channels.

        All channels are captured with synchronized timing from the same trigger.
        Downloads each channel sequentially after the trigger completes.

        Args:
            channels: List of channel numbers (1-4)

        Returns:
            Dictionary mapping channel number to WaveformData
        """
        waveforms = {}
        for channel in channels:
            waveforms[channel] = self.get_waveform(channel)
        return waveforms
