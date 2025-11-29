"""Debug script to check channel scaling parameters."""

import sys
sys.path.insert(0, '/Users/bjpirt/Documents/personal/projects/ShutterScope/src')

from shutterscope.oscilloscope import RigolDS1000Z

address = sys.argv[1] if len(sys.argv) > 1 else None

if address:
    print(f"Connecting to {address}...")
    scope = RigolDS1000Z(address)
    scope.connect()
else:
    print("Connecting to oscilloscope (auto-discover)...")
    scope = RigolDS1000Z.auto_connect()
print("Connected!\n")

# Stop acquisition
scope._instrument.write(":STOP")

for channel in [1, 2, 3]:
    print(f"=== Channel {channel} ===")
    
    # Query channel scale and offset
    scale = scope._instrument.query(f":CHAN{channel}:SCALe?").strip()
    offset = scope._instrument.query(f":CHAN{channel}:OFFSet?").strip()
    print(f"  Scale: {scale} V/div")
    print(f"  Offset: {offset} V")
    
    # Set waveform source and get preamble
    scope._instrument.write(f":WAVeform:SOURce CHAN{channel}")
    scope._instrument.write(":WAVeform:MODE RAW")
    scope._instrument.write(":WAVeform:FORMat BYTE")
    scope._instrument.write(":WAVeform:STARt 1")
    scope._instrument.write(":WAVeform:STOP 1000")
    
    preamble_raw = scope._instrument.query(":WAVeform:PREamble?").strip()
    preamble = preamble_raw.split(",")
    y_increment = float(preamble[7])
    y_origin = float(preamble[8])
    y_reference = float(preamble[9])
    
    print(f"  Preamble y_increment: {y_increment}")
    print(f"  Preamble y_origin: {y_origin}")
    print(f"  Preamble y_reference: {y_reference}")
    print()

scope.disconnect()
print("Done")
