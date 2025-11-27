"""CLI entry point for ShutterScope."""

import argparse
import sys

from shutterscope.oscilloscope import RigolDS1000Z
from shutterscope.waveform import save_waveform

# Default trigger level in volts - adjust as needed
DEFAULT_TRIGGER_LEVEL = 1.0


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
        scope.setup_edge_trigger(channel=1, level=DEFAULT_TRIGGER_LEVEL)
        print(f"Trigger set on channel 1 at {DEFAULT_TRIGGER_LEVEL}V")

        print("Waiting for trigger...")
        if scope.wait_for_trigger(timeout=30.0):
            print("Triggered! Downloading waveform...")
            waveform = scope.get_waveform(channel=1)
            save_waveform(waveform, "capture.csv")
            print(f"Saved {len(waveform.voltages)} samples to capture.csv")
        else:
            print("Trigger timeout")
            sys.exit(1)
    finally:
        scope.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    main()
