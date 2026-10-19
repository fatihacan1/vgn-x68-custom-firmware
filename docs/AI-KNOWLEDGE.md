# VGN X68 Custom Firmware: portable engineering context

This is a knowledge export, not a promise that an untested modification is safe.
Certainty labels distinguish static evidence, emulation, device observations,
owner observations and unresolved questions. No private device paths are needed.

## Identity and versions

- Observed device: SUBOR X68, manufacturer Telink, USB VID:PID 320F:5055,
  USB release 0113. Other products share this VID/PID: names, usage and the entire
  HID report descriptor must also match. Ambiguous devices are refused.
- The application's semantic version is independent of the keyboard's version
  field. VGN's version query returned 00000000 on this device. Do not label that
  field 0.5.0 or assume that a matching reported CRC is a complete flash dump.
- Stock V0113 payload: 236916 bytes; SHA256
  791ae619fb2d7dbe44203192bd42b07073029701ad9ad6363032176559136273;
  stored/reported CRC 14961BE6. CRC is zlib.crc32(payload without last 4 bytes)
  XOR FFFFFFFF, stored little endian in the last four bytes.
- Lavender Quest 0.4.0 (EF331DCE) and 0.4.1 (4CB077DE) were early display
  attempts. Owner reported a static clock. Do not distribute them as fixed.
- 0.4.2 (FC2EBCFE): owner confirmed clock and scene movement on the device.
- 0.5.0 (3C866A9B): RAM-only clock command and optional media player added.
  The actual device acknowledged automatic clock sync; the owner confirmed the
  displayed time and date match the computer. Media rendering and RAM
  clock register preservation were emulated; a user-selected GIF upload still
  requires physical confirmation. See bundled manifest for exact hashes.
- For a new release: change source, build, inspect the compiled code, emulate
  actual RV32 code, review allowed write addresses, then explicitly register its
  exact hashes. Changing only a version string or CRC is not a firmware fix.

## Verified transport and OTA

- Report 05 / command 01 is the existing version/CRC query. Its 64-byte request
  is fixed in x68/protocol.py. Descriptor verification precedes sending.
- Report 04 settings frames: report ID; 16-bit sum of bytes 3..63; command;
  length; 24-bit little-endian offset; at most 56 data bytes. ACK header must
  match. Do not confuse decimal 21 (macro bank) with hex 21 (media bank).
- Bounded reads: 03/34 bytes, 05/64 parameters, 08/384 keymap,
  14 hex/4096 macro bank, 1A hex/6 battery. Known persistent writes:
  06/64 parameters, 09/384 keymap, 15 hex/4096 macro bank.
- Stock OTA: report 05 / command 02. Start data 01 FF. Blocks contain LE16
  sequence, 16 firmware bytes and CRC16-Modbus. Three blocks per 64-byte report.
  End data 02 FF plus final index and its negative, each LE16. Final result
  prefix 05 02 03 00 06 FF; result zero means success. Re-enumerate and check
  reported target CRC. No blind packet retries. Interrupted recovery is unproven.
- Settings are backed up before writes. RGB, keymap and macro writes are read
  back. Media ACKs are not a flash readback. Never describe them as one.

## Native display architecture

- Framebuffer: 160x96, row-major RGB565, high byte first, 30720 bytes.
  RAM address 000819E0. Payload source [12B0,A0B4) is copied to RAM
  [1200,A004), so those code addresses differ by B0. GP is 00080800.
- The stock dispatcher entry guard is preserved. Payload 71C0..71C8 redirects
  RAM 7110 to custom code at 20027664, in a retired logo region.
- Custom background is at payload 31664..38E64. Compiled code/rodata are in
  the retired 27664..2EE64 logo area. These are not a user GIF upload.
- Original LCD transport is called at RAM 6EAC. The mode-zero display request
  bit at RAM 80D20 and pending-frame bit at 80C9A must be respected. Altering
  only the pending bit produced a frozen display in an early attempt.
- Software clock state reuses retired display caches 80B80..80B86 and
  80D8C..80D92. Timing reads the 16 MHz MCU system timer at 80140200.
  A full power loss needs computer resynchronization. The app syncs local time
  on connection and every minute while running. Day/month are refreshed by the
  computer; there is no independently verified battery-backed calendar here.
- The brief SUBOR power-on splash remains. Its storage and earliest draw path
  have not been mapped. Do not claim it was replaced or write the bootloader
  based on guesses. Original default screen selection is otherwise bypassed.

## RAM-only live clock, custom 0.5.0 only

- Report 04 / command 18 hex (decimal 24), length 6, offset 0. Data:
  BCD second, minute, hour, ISO weekday 1..7, day, month.
- Slot 1E78C originally points to the unsupported handler 2001BE74. The custom
  firmware changes exactly that table entry to its reviewed clock bridge.
- The bridge preserves all caller-saved registers and rejoins the existing ACK
  path at 2001B8A0. It updates only six RAM parameter bytes 80573..80578 and
  the display cache marker. It does not set a flash-dirty flag or write the RTC.
- Only send after the exact supported custom CRC is verified. Old firmware
  treats this as unsupported. Do not use persistent command 06 every minute;
  that needlessly wears settings flash. Manual legacy clock sync is separate.
- Legacy parameter bytes 23..28 hex are the same six BCD fields. Stock setter
  2000F4A4 writes them to the external RTC and hardcodes year 22 hex. Year and
  independently correct external RTC operation were not established.

## Images and GIFs

- The converter accepts Pillow-supported images and GIF frames, composites
  transparency, crops/fits/stretches to 160x96 and uniformly samples at most
  eight frames across the full animation. It uses RGB565 big endian; no manual
  conversion in the vendor app is required. Limits: 30 MB, 16 MP, 500 source frames.
- Custom media uses the original report 04 / command 21 hex writer, verified
  at 2001B918. First offset zero erases physical flash A2000..DE000. This
  replaces the existing custom animation. It is not the firmware OTA area.
- Maximum 8*30720=245760 bytes. Each packet is bounded to 56 bytes, with offset
  inside that bank. Save converted data and metadata before writing. Stop on
  failed ACK; no blind retry. Do not advertise independent flash verification.
- After upload: parameter byte 21 hex=4, 22 hex=frame count 1..8, 2A..2B hex
  is frame duration in milliseconds for OUR custom renderer, 50..5000.
  Do not assume this timing meaning on original V0113.
- The custom renderer uses the original flash-read callback stored at RAM BB4.
  Only A2000..DE000 is read. Cached frame index is at 80D49 and media-active
  state at 80D82. All other screen selections use the single Lavender desktop.
- Media uploads are opt-in. Converting or previewing never writes the device.

## RGB, keymap and macros

- Known RGB parameter bytes: effect 1, brightness 2, reversed speed 3,
  rainbow flag 5, RGB 6..8. Preserve unrelated bytes. Rainbow FF has unknown
  meaning; preserve it unless the user explicitly selects another value.
- Physical key identities use fixed matrix cells from the stock V0113 default
  table at payload offset 397B0, checked against device readbacks. Never infer
  physical identity from the current action: remaps and macros replace it.
  Keymap legends show current device actions; selecting a macro loads its slot.
  The navigation cluster is 2x2: Insert (cell 30) above Delete (46) on
  the left, Page Up (62) above Page Down (63) on the right. Legends show
  their saved actions, e.g. Print Screen and F17 on the owner's keyboard.
  Fn and reserved cells remain protected. Macro events must balance DOWN/UP.
- Keymap supports six media actions through `[30 hex, consumer_usage, 00]`:
  play/pause CD, previous B6, next B5, mute E2, volume down EA, volume up E9.
  Verified in the stock V0113 Fn table at payload 1CD04..1CD1B. Known media
  assignments remain editable after reload; unknown function formats stay protected.
  Media actions are direct key assignments, not macro DSL commands.
- Per-key colour drafts are local only. Device per-key RGB writes are NOT
  verified; a preview changing colour is not proof that an LED was programmed.

## Battery: unresolved, not repaired

- Actual HID battery reports were 00 01 00 00 00 00. Firmware computes a
  0..100 indicator; that is not an independently calibrated state of charge.
- Owner reports a full icon on USB and shutdown when unplugged. Tried another
  charger; no improvement. Same problem existed before Fn+Backspace.
- Static handler 2001BA0C reads cached level at GP+370 and PE4 / PC3 inputs.
  One branch returns fixed level 100/status 2. The native icon uses a separate
  state at GP+501; its status 2 path skips loading the cached level.
- This explains how the icon and HID level can disagree. It does NOT prove
  that the icon disables charging. No verified charge-enable output was found.
- No measured voltage/current/capacity, battery presence, health or charging
  current is available. Keep unknown fields unknown. Never invent percentages.
- Stock reflash, short RGB-load trial and mode change did not establish a repair.
  The USB daughterboard has two battery connectors and a multi-wire connector
  to the main PCB. Photos of both faces did not identify a charging IC.
- Do not bypass battery protections, force an unidentified GPIO or change ADC
  thresholds and call it a charging repair. Display changes leave charge code alone.

## Development and portability

- npm run dev launches the native Python/Tk desktop; this is not a web server.
  Python 3.10+, Tk, hidapi and Pillow are required. The launcher prepares a
  platform-specific venv. npm run dev -- --smoke performs a short UI smoke run.
- Windows executable is built with PyInstaller, no UPX. The complete folder is
  required. macOS source launch support is implemented but not hardware-tested
  in this Windows session. Raw Input key testing is Windows-only.
- The original vendor EXE was never executed. Its resources/.NET code were
  inspected statically. No Defender bypass or exception was installed.
- No publication, telemetry, automatic remote update or external messaging.
- Portable knowledge exports omit usernames, HID paths and raw private reports.


## Release 0.5.1: app controls and LCD battery badge

- Native image CRC 10EE7CA9; renderer SHA256
  15b6d7a7d9726217791fbe96cbb1bcd47d0b147c37dd0f47156928647515459c;
  payload SHA256
  0ed295763080a581401c40de9c3d87446ca4b03c08bef12961bbd6b96f96f5ac.
- PLAYER 1 is replaced by a small battery outline and percentage read from the
  existing cached firmware indicator at RAM 80B70 (GP+370). Only 0..100 is shown;
  invalid values show --. This is a cached indicator, not a calibrated charge
  measurement. It may differ from the HID status-2 fixed-100 override. No charging
  animation or charging state is invented, and the badge writes no battery state.
- Actual RV32 emulation covers badge values 0, 42, 100 and 255, framebuffer bounds,
  register preservation, RAM clock and optional media. LCD drawing adds no GPIO,
  ADC or charger writes. The owner confirmed the new badge is visible and the clock advances.
- Following this update the known RGB effect/colour fields were observed resetting to stock defaults. They were restored and read back. The reviewed updater now restores only documented RGB fields after reboot, with backup/readback; it does not restore stale full parameter blocks or auto-write an unreviewed image.
- Battery read callbacks now end with a timestamp/result; Start and Stop are
  separate controls and show the retained sample count. USB refresh is an action,
  not a disconnected-state indicator. Sidebar reports verified USB wired mode.
- Keymap uses a local draft: selecting a key or action and adding to draft sends
  nothing. Only Send draft writes; the whole batch is validated first, backed up,
  then written/read back once. Discard sends nothing. Navigation/arrow groups are
  separated visually. Advanced matrix selection is kept in Advanced.
- Per-key colour upload remains unverified. The shared Evision 11-hex command is
  unsupported in this exact firmware table. Handler 12 hex is a candidate RAM RGB
  writer with mapping at payload 38ED4; its LED mapping and safe operation are not
  fully validated. Do not equate the local colour draft with a device write. Global
  lighting Send is disabled while editing a per-key draft to prevent confusion.
- Firmware preview follows the selected build. Original preview is a decoded
  stock background asset, not an emulation of its live overlays. Imported files
  have no trusted visual preview. File selection never installs firmware.
- User firmware import accepts only a full raw .bin with exactly 236916 bytes,
  stock-identical first 256 header bytes and valid inverted CRC32. Unknown code
  requires the explicit unreviewed option and a separate Install click. Structural
  checks do NOT establish compatibility or recoverability. Default protocol
  encoders remain hash-gated; allow_unreviewed is explicit and validates structure.
  Packets are fully prepared before the first OTA command. EXE/HEX/UF2 are rejected.
- Reviewed stock/custom images remain available; to recognize a previously loaded
  unknown CRC for rollback, select that same structurally valid user binary first.
  An unreviewed image can still break USB; hardware recovery is not guaranteed.
- Home artwork and mascot were generated using the owner's explicitly requested
  local image API at 127.0.0.1:3210, in one normal ChatGPT image conversation.
  The owner-provided CleanMyBrain repo was used as a craft/style reference, not
  copied into the app. See ART-PRODUCTION.json for prompts. Hero keyboard art is
  illustrative, not an exact hardware/key-layout photograph. Subtle floating
  motion animates the bitmap; there is no live 3D renderer in the Tk client.

## Primary references

- Official VGN list: https://www.vgnlab.com.cn/api/drive/list
- Official updater source: https://cdn.vgnclub.com/vgn/driver/X68/X68-V0113固件升级.exe
- Telink SDK GPIO definitions: https://github.com/telink-semi/tl_ble_sdk/blob/master/tl_ble_sdk/drivers/B91/reg_include/gpio_reg.h
- Telink boot definitions: https://github.com/telink-semi/tl_ble_sdk/blob/master/tl_ble_sdk/drivers/B91/ext_driver/mcu_boot.h
- Pillow GIF format/disposal documentation: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif
- REA reverse-engineering project, reviewed as a reference, not run against the device: https://github.com/morluto/rea


## Experimental 0.6.0: read-only battery engineering snapshot

This is a diagnostic candidate, not a charging repair. Device installation and
physical readings must be recorded separately; do not infer them from emulation.

- Payload SHA256 861fb1bb65e18f07b74a89448fbdec1fb9eca7655011d2d7e55c34c5d3477c0d,
  CRC 127F9EB4, renderer SHA256
  304ed2037060a1cdedaa86e563a2df5c10b997cf4fa2f88484b0c1ea500a345a.
- New report 04 / command 19 hex (decimal 25), exact 48-byte read, offset zero.
  Table slot 1E790 changes from unsupported 2001BE74 to battery_bridge 20028010.
  Clock bridge is now 2002812E; existing RAM clock semantics are preserved.
- Snapshot magic XBD + schema byte 01. Bytes 4/5: cached and previous indicators;
  6/7: raw PE/PC GPIO inputs; 8: native UI state; 9: transport mode; 10/11: ADC
  multipliers; 12..27: eight cached ADC samples; 28..37: original calibration and
  threshold bytes; 38..41: scheduler timestamp; 42..45: MCU timer;
  46/47: native low-level flag and filter counter. Multibyte fields are LE.
- The handler reads original locations 80B70, 808D3, 80140320, 80140310, 80D01,
  80C9C, 80D30..31, 80D9C..80DAB, 1130..1139, 80D40..43, 80140200,
  80BFE and 80CFD. Only the output packet is changed. The bridge preserves all
  caller-saved registers and rejoins the original ACK path. No ADC start,
  calibration change, GPIO output, flash-dirty flag or charge-control write.
- Actual RV32 emulation passed 12 cases including valid and malformed diagnostic
  requests, write scopes, register preservation, display, clock and media reads.
  Eighty-one Python/UI tests passed. Neither is physical charging validation.
- Decoder reproduces the native integer arithmetic from 20010524..200106B6:
  sum middle four sorted samples after each is shifted right by two; multiply by
  unsigned native factors and calibration, wrap to signed 32 bits, arithmetic
  shift right 13, add signed calibration offset, retain lower 16 bits. Compare
  native lower/upper thresholds and UI override before the later percentage
  filter. Result is labelled unfiltered_firmware_indicator, never physical SOC.
- Comparing that value with cached_indicator may identify a display/filter issue.
  Equal low readings cannot identify battery failure vs wiring vs ADC input alone.
  Raw counts are not calibrated battery voltage. GPIO input states do not prove
  charge current or establish a safe charge-enable output.
- tools/read_battery_diagnostic.py requires the exact experimental CRC and records
  snapshots with standard 1A reports. It performs no settings/control writes.
  Stable 0.5.1 remains the bundled release; experimental binary is in private
  reports/battery-diagnostic-v1. Do not run concurrent GUI/HID polling during OTA.
- The custom screen currently has no charging lightning glyph. Its absence is a
  design omission, not a sensor report. USB connectivity and actual charging are
  different facts. Do not invent a charging animation from a connected cable.
- Computer clock synchronization is verified over wired USB only. The MCU clock
  continues while powered in other modes; automatic sync through 2.4G/Bluetooth
  remains unverified. 2.4G is a keyboard radio link, not a Wi-Fi internet clock.


### Actual 0.6.0 device observations (18 October 2026)

- OTA result 0; reported CRC 127F9EB4. No GUI was launched. Existing keymap and
  macro bytes matched before/after. The only remaining parameter difference was
  byte 41 changing 0 to 1 (native RTC update flag); do not claim a full unchanged
  parameter block. PC local clock was resynchronized with the RAM command.
- Six snapshots, five seconds apart: cached/previous indicators always 0;
  all 48 ADC samples ranged 0..8; cached samples varied and scheduler timestamp
  advanced. This is not a frozen display reading or only the final filter clamp.
- ADC factors 4 and 1; calibration scale 1172; signed offset +12; native lower
  threshold 1510 and upper threshold 2035. Native arithmetic result 12..13 code
  units, giving unfiltered_firmware_indicator 0 in all snapshots. Do NOT label
  12..13 as measured battery millivolts or infer battery terminal voltage.
- PE4=1, PC3=1, native UI state=1, transport mode=2, standard report status=1.
  No fixed-100 branch was active in these samples. No charge-enable output or
  actual charge current has been established.
- Stock boot writes analog register EB = AF at payload 8204..820C, i.e. PD1
  positive ADC input and GND negative according to the Telink B91 adc.h enum and
  adc_set_diff_input. PD1 output is disabled and ADC pin setup is present in that
  boot region. This is static initialization evidence, not runtime analog mux
  readback or a proof that the board routes the battery divider to PD1 correctly.
- Distinguishing low pack voltage, protection cutoff, a broken connection/divider
  or an incorrect runtime ADC input now needs an independent voltage measurement
  or further hardware evidence. No charging repair is claimed. User was asked
  for DC voltage across PH1 B+/B- with USB removed and then connected; no readings
  have yet been supplied. Do not invent them or bypass battery protections.
