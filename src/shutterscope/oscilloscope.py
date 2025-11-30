"""Oscilloscope module for ShutterScope.

Re-exports all oscilloscope-related classes for backwards compatibility.
"""

from shutterscope.oscilloscope_protocol import OscilloscopeProtocol
from shutterscope.rigol_ds1000z import RigolDS1000Z
from shutterscope.waveform_data import WaveformData

__all__ = ["WaveformData", "OscilloscopeProtocol", "RigolDS1000Z"]
