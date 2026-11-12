# Next capture: attribute a signal to a panel before fitting a classifier

The saved door experiments show repeatable scene changes, but cannot separate
the pane from its frame/handle, occlusion and background. The November 11
[signal audit](../evidence/glass-signature-20261111/README.md) also found that the
most consistent coherence effect largely survives a stationary-scene surrogate.

The next experiment asks whether a standalone glass panel produces a repeatable
local effect different from matched non-glass panels when everything else stays
fixed. This is a small attribution pilot, not a validation of glass recognition
across rooms or specimens. No additional live detector is needed to collect it.

## Fixture and conditions

Clamp the radar in one pose. Keep one mounting fixture fixed in the beam; move
only the specimen in and out of it. Use panels of comparable exposed area and
record dimensions, composition, thickness, coatings and mounting. A swinging
door does not isolate the pane from its frame and handle.

| Condition | What occupies the fixture | Purpose |
|---|---|---|
| empty_fixture | No panel; repeat the same handling/step-away procedure | Sham control and repeat variation |
| glass | One identified glass specimen | Panel-present effect |
| acrylic | An identified transparent non-glass panel | Transparency/material control |
| opaque | One identified opaque panel, with material recorded | Generic obstruction control |

If a control is unavailable, mark it missing; do not replace its recordings or
claim the corresponding distinction has been tested. Thickness and material
matching remain imperfect even with comparable panel area.

Use two background conditions without moving the radar or fixture:

- `room`: existing static room background, with geometry recorded.
- `reflector`: the same room plus a fixed reflector behind the panel. Survey
  panel and reflector distances separately. Choose enough separation to resolve
  their returns with the actual acquisition; interpolated FFTs add no resolution.

Start near normal incidence at a surveyed distance where the current profile
has a usable return. Record that distance without fitting the RF scale to it.
First check a readily detected reference object at that location. If it cannot
be localized repeatably, address acquisition/range qualification before treating
panel misses as material evidence. Keep gains, waveform, board pose and RF
profile unchanged across all conditions; record their configuration file/hash.

## Capture order and metadata

Collect three blocks. Within each block/background group, shuffle the four
conditions before acquiring data; alternate background order between blocks.
This gives **24 recordings of 30 seconds** (12 minutes of saved signal plus
setup/handling). Retain the chosen order before capture; do not rearrange it
after looking at scores. No one remains in the beam. Allow at least five seconds
after each change before starting acquisition, with a helper initiating capture
after the operator is clear. Keep sensor power unchanged and log any restart.

The count is an engineering feasibility pilot. Three repeats do not establish
statistical confidence. A second day and new physical specimens are later
validation, after features/criteria have been frozen from this pilot.

Use the existing recorder with a **new** output directory for every run:

```bash
.venv/bin/python -m radar record recordings/panel-pilot/block01-room-glass \
  --port YOUR_PORT --config YOUR_MATCHING_CONFIG.json \
  --metadata YOUR_COMPLETED_METADATA.json --seconds 30
```

The `record` command starts immediately; it has no setup countdown. Complete
the step-away interval before the helper runs it. A config must match the
board's actual profile. This procedure requires no flashing.

Populate metadata before each run. Example fields (replace placeholders and
null measurements; they are not observations):

```json
{
  "label": "glass",
  "material": "glass",
  "condition": "glass",
  "specimen_id": "REPLACE_WITH_PHYSICAL_SPECIMEN_ID",
  "scene_id": "REPLACE_WITH_ROOM_AND_DAY",
  "fixture_id": "REPLACE_WITH_FIXED_FIXTURE_ID",
  "block": 1,
  "capture_order": 1,
  "background_id": "room",
  "distance_m": null,
  "incidence_deg": null,
  "width_m": null,
  "height_m": null,
  "thickness_mm": null,
  "coating": "unknown",
  "background_reflector_distance_m": null,
  "sensor_moved": false,
  "sensor_restart": false,
  "notes": "REPLACE_WITH_GEOMETRY_AND_ANY_DEVIATIONS"
}
```

Use `label: empty` for the fixture control and `label: non_glass` for the
acrylic/opaque controls; keep their exact material in `material`. For the empty
fixture, record the surveyed fixture-plane distance and `specimen_id: none`.
For the room condition, a null added-reflector distance means no added reflector;
record existing background objects in the notes. Never invent unknown material
composition, geometry, calibration or timing verification.

## Decide what the signal supports

Preserve all raw captures and rejects. Check CRC/continuity, device counters,
container rails, host/device timing and coverage, using the existing raw audit
patterns. A failed capture remains marked failed and gets a new directory if
repeated. Summarize at the recording/block level; do not count windows as
independent specimens.

Keep the current audit's native-bin pane ROI and elementary measurements fixed
for this first comparison. Record per-RX power spectra and all RX-pair coherence,
including the stationary-mean surrogate. Use measured panel/background locations
only for diagnostic regions, and preserve other range bins as context.

1. Compare each inserted panel with its block/background fixture control.
   Compare those effects with empty-fixture repeat variation and handling drift.
2. Require an attributed local change to survive repeat handling and the two
   backgrounds. Determine whether a claimed later return follows the surveyed
   background reflector instead of assuming that any spectral tail is transmitted
   energy. Record absent/ambiguous panel returns as misses or unresolved.
3. Compare glass with acrylic and the opaque control at matched geometry.
   A shared effect supports generic panel detection. It does not distinguish
   glass. A coherence effect reproduced by the stationary-mean surrogate is
   insufficient material evidence on its own.
4. If a glass-associated difference remains, freeze its definition and decision
   rule before testing a new pane, room, day, distance or incidence. Reserve
   entire physical specimens and scenes; do not randomly split nearby frames.
   A difference discovered in this pilot remains a hypothesis until that test.

If fixture handling/background changes explain the signal, or glass and controls
remain indistinguishable, document that outcome before collecting a broader
training set. The pilot does not resolve arbitrary incidence, moving-board
operation or collision latency.
