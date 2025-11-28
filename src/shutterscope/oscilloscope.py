"""Oscilloscope protocol and implementations for ShutterScope."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import pyvisa

if TYPE_CHECKING:
    from pyvisa.resources import MessageBasedResource


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


class RigolDS1000Z:
    """Rigol DS1000Z oscilloscope implementation using SCPI over VISA."""

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
        self._desired_points: int | None = None

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

    # Valid memory depth values for DS1000Z (single channel)
    MEMORY_DEPTHS = [1000, 10000, 100000, 1000000, 6000000, 12000000]

    def configure_timebase(
        self, max_duration: float, sample_interval: float = 1e-6
    ) -> None:
        """Configure timebase for pulse capture.

        Sets up the oscilloscope to capture a pulse of up to max_duration seconds,
        with the trigger point near the right edge of the screen so most of the
        capture window shows the pulse before the falling edge trigger.

        Args:
            max_duration: Maximum expected pulse duration in seconds
            sample_interval: Desired time between samples in seconds (default 1µs)
        """
        if self._instrument is None:
            raise RuntimeError("Not connected to oscilloscope")

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

        # Store the desired depth for optimized downloads
        self._desired_points = desired_depth

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

        # Configure vertical scale for 0-2.5V signal with 1 div margin top/bottom
        # DS1000Z has 8 vertical divisions. With 0.5V/div, total range = 4V
        # Negative offset moves 0V down on screen
        # To put 0V at 1 div from bottom (3 divs below center): offset = -1.5V
        self._instrument.write(":CHAN1:SCALe 0.5")  # 0.5V per division
        self._instrument.write(":CHAN1:OFFSet -1.5")  # Shift 0V down to 1 div from bottom
        self._instrument.write(":CHAN1:DISPlay ON")  # Ensure channel is displayed


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

    def wait_for_trigger(self, timeout: float = 10.0) -> bool:
        """Wait for the oscilloscope to trigger.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if triggered, False if timeout occurred
        """
        if self._instrument is None:
            raise RuntimeError("Not connected to oscilloscope")

        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self._instrument.query(":TRIGger:STATus?").strip()
            if status == "TD":
                return True
            if status == "STOP":
                return True
            time.sleep(0.1)
        return False

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

        # Get preamble for voltage conversion
        # Format: format,type,points,count,xincrement,xorigin,xreference,
        #         yincrement,yorigin,yreference
        preamble_raw = self._instrument.query(":WAVeform:PREamble?").strip()
        preamble = preamble_raw.split(",")
        preamble_xorigin = float(preamble[5])
        y_increment = float(preamble[7])
        y_origin = float(preamble[8])
        y_reference = float(preamble[9])

        # Get channel offset - needed to correct voltage readings
        # The preamble values don't account for the display offset properly
        chan_offset = float(self._instrument.query(f":CHAN{channel}:OFFSet?").strip())

        # Get actual sample rate (preamble x_increment is wrong in RAW mode)
        sample_rate = float(self._instrument.query(":ACQuire:SRATe?").strip())

        # Use preamble's xorigin - it correctly reflects the trigger position
        # even though the x_increment value is wrong in RAW mode
        x_origin = preamble_xorigin

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
        # Formula: voltage = (byte - yorigin - yreference) * yincrement - chan_offset
        # The channel offset must be subtracted as the preamble includes it inverted
        voltages = [
            (byte_val - y_origin - y_reference) * y_increment - chan_offset
            for byte_val in raw_bytes
        ]

        return WaveformData(
            voltages=voltages, sample_rate=sample_rate, start_time=x_origin
        )
