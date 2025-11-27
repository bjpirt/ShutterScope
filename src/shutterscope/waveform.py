"""Waveform data handling for ShutterScope."""

from shutterscope.oscilloscope import WaveformData


def save_waveform(data: WaveformData, filename: str) -> None:
    """Save waveform data to a CSV file.

    Args:
        data: WaveformData to save
        filename: Path to the output CSV file
    """
    with open(filename, "w") as f:
        f.write("time_s,voltage_v\n")
        for t, v in zip(data.times, data.voltages, strict=True):
            f.write(f"{t:.9g},{v:.6g}\n")
