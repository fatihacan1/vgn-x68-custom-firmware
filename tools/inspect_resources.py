"""Read ILSpy's .resx export offline. Does not load/execute vendor code."""
import argparse
import base64
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("resx", type=Path)
parser.add_argument('--payload-output', type=Path, help='Optional offline payload extraction; never flashes a device')
args = parser.parse_args()
resources = ET.parse(args.resx)
values = {entry.attrib["name"]: entry.findtext("value") for entry in resources.findall("data")}
param = base64.b64decode(values["param_128K"])
code = base64.b64decode(values["code_2M"])
if len(param) < 96 or len(code) < 256:
    raise SystemExit("Resource too short")
size = int.from_bytes(code[48:52], "big")
if not 4 <= size <= len(code) - 256:
    raise SystemExit("Invalid embedded payload size")
payload = code[256:256+size]
if args.payload_output:
    args.payload_output.parent.mkdir(parents=True, exist_ok=True)
    args.payload_output.write_bytes(payload)
print(json.dumps({
    "vid": param[64:68].decode("ascii"), "pid": param[68:72].decode("ascii"),
    "report_id": param[72:74].decode("ascii"), "display_version": param[75:78].decode("ascii"),
    "usage_page": param[80:84].decode("ascii"), "payload_bytes": size,
    "stored_crc": f"{int.from_bytes(payload[-4:], 'little'):08X}",
    "payload_sha256": hashlib.sha256(payload).hexdigest(),
}, indent=2))
