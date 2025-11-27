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

    def setup_edge_trigger(
        self, channel: int, level: float, slope: str = "POS"
    ) -> None:
        """Configure edge trigger on the specified channel.

        Args:
            channel: Channel number (1-4)
            level: Trigger level in volts
            slope: Trigger slope - "POS" for rising edge, "NEG" for falling edge
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
        """Retrieve waveform data from the specified channel.

        Args:
            channel: Channel number (1-4)

        Returns:
            WaveformData containing times, voltages, and sample rate
        """
        if self._instrument is None:
            raise RuntimeError("Not connected to oscilloscope")

        self._instrument.write(f":WAVeform:SOURce CHAN{channel}")
        self._instrument.write(":WAVeform:MODE NORMal")
        self._instrument.write(":WAVeform:FORMat ASCii")

        x_increment = float(self._instrument.query(":WAVeform:XINCrement?"))
        x_origin = float(self._instrument.query(":WAVeform:XORigin?"))

        raw_data = self._instrument.query(":WAVeform:DATA?")
        # Remove header (e.g., "#9000001200") if present
        if raw_data.startswith("#"):
            header_len = int(raw_data[1]) + 2
            raw_data = raw_data[header_len:]

        voltage_strings = raw_data.strip().split(",")
        voltages = [float(v) for v in voltage_strings if v]

        times = [x_origin + i * x_increment for i in range(len(voltages))]
        sample_rate = 1.0 / x_increment if x_increment > 0 else 0.0

        return WaveformData(times=times, voltages=voltages, sample_rate=sample_rate)
