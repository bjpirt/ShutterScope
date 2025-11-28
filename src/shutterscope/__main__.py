"""CLI entry point for ShutterScope."""

import argparse
import sys

from shutterscope.analysis import PulseMeasurementError, measure_pulse_width
from shutterscope.oscilloscope import RigolDS1000Z
from shutterscope.waveform import save_waveform_json, save_waveform_plot

# Default trigger level in volts - adjust as needed
DEFAULT_TRIGGER_LEVEL = 0.2
# Default maximum shutter time in seconds
DEFAULT_MAX_SHUTTER = 0.1
# Default sample interval in seconds (1 microsecond)
DEFAULT_SAMPLE_INTERVAL = 1e-6


def main() -> None:
    """Main entry point for ShutterScope CLI."""
    parser = argparse.ArgumentParser(
        description="Capture waveform data from a Rigol DS1000Z oscilloscope"
    )
    parser.add_argument(
        "address",
        nargs="?",
        help="VISA address (e.g., TCPIP::192.168.1.100::INSTR). "
        "If not provided, auto-discovers via USB.",
    )
    parser.add_argument(
        "--max-shutter",
        type=float,
        default=DEFAULT_MAX_SHUTTER,
        help=f"Maximum shutter time in seconds (default: {DEFAULT_MAX_SHUTTER})",
    )
    parser.add_argument(
        "--trigger-level",
        type=float,
        default=DEFAULT_TRIGGER_LEVEL,
        help=f"Trigger level in volts (default: {DEFAULT_TRIGGER_LEVEL})",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Save a plot of the waveform to capture.png",
    )
    args = parser.parse_args()

    try:
        if args.address:
            print(f"Connecting to {args.address}...")
            scope = RigolDS1000Z(args.address)
            scope.connect()
        else:
            print("Searching for Rigol DS1000Z oscilloscope...")
            scope = RigolDS1000Z.auto_connect()
    except ConnectionError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Connected to oscilloscope")

    try:
        scope.configure_timebase(
            max_duration=args.max_shutter,
            sample_interval=DEFAULT_SAMPLE_INTERVAL,
        )
        print(f"Configured for max {args.max_shutter}s shutter, 1µs sample interval")

        scope.setup_edge_trigger(channel=1, level=args.trigger_level)
        print(f"Trigger set on channel 1 at {args.trigger_level}V (falling edge)")

        print("Waiting for trigger...")
        if scope.wait_for_trigger(timeout=30.0):
            print("Triggered! Downloading waveform...")
            waveform = scope.get_waveform(channel=1)

            # Measure shutter speed
            try:
                metrics = measure_pulse_width(waveform)
                print(
                    f"Shutter speed: {metrics.pulse_width_ms:.2f} ms "
                    f"({metrics.shutter_speed_fraction})"
                )
            except PulseMeasurementError as e:
                print(f"Warning: Could not measure pulse: {e}")
                metrics = None

            save_waveform_json(waveform, "capture.json", metrics)
            print(f"Saved {len(waveform.voltages)} samples to capture.json")
            if args.plot:
                save_waveform_plot(waveform, "capture.png")
                print("Saved plot to capture.png")
        else:
            print("Trigger timeout")
            sys.exit(1)
    finally:
        scope.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    main()
