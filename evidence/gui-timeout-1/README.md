# Empty capture stops around six seconds

Latest GUI session gui-20261101-153315-782345 has three completed attempts
(empty-001, empty-002, empty-004), all zero frames, no transport file, zero parser
counters, and a serial_timeout reading. The code delays five seconds to allow
stepping away, then acquisition times out after one second without a complete
frame. These files show zero received transport bytes, not a range-estimator
failure or evidence of a GUI rendering freeze. No baseline was produced.

KitProg3 still enumerated as /dev/cu.usbmodem103 with serial 170D0E8300023400.
Enumeration does not establish that the radar MCU is running/responding. Physical
cause remains unresolved; no new board access or flash was attempted in this fix.
User recovery step: close serial readers, reconnect board USB, reopen GUI, retry
empty capture. A successful subsequent capture is needed to verify recovery.

Changes: distinguish no bytes, bytes without a complete radar frame, and a stream
stall after frames; persist byte counts and details. GUI states the five-second
delay separately from its ten-second capture, shows opening/waiting state, and
saves gui-error.json in an existing capture folder when the worker fails. The
one-second freshness timeout remains intact. Failed recordings remain preserved.

Tests cover all three timeout cases, preserving raw bytes and closing the port.
42 tests pass. No DSP, detector thresholds, firmware or existing recordings changed.
