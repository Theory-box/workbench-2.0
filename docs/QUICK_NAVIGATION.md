# Quick Navigation

Enable **Render Properties > Workbench 2.0 > Shading > Quick Navigation**, beside
Parallax. Off by default. While enabled, viewport navigation, object transform
updates, Edit Mode geometry updates, and viewport animation playback temporarily
set parallax depth to zero for drawing. This also bypasses local height AO,
parallax sun self-shadowing, and depth intersections. Original node values and the
global Parallax toggle are preserved. Ordinary material edits are not a trigger.

Relief returns on the next stationary redraw, with no idle delay; a timer requests the
restoring redraw. Both final stills and final animation renders keep full quality.
Baked reflection capture is outside the temporary viewport bypass. This does not
reduce geometry extraction or other screen-effect costs; no performance multiplier
is promised.

Blender 4.4.3 checks: native viewport transform/navigation activation, pixel changes
and automatic idle restoration, quick viewport playback, identical F12 on/off
output, and two final animation frames identical to the full-quality reference.
