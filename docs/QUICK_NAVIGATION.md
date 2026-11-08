# Quick Navigation

Enable **Render Properties > Workbench 2.0 > Shading > Quick Navigation**, beside
Parallax. Off by default. While enabled, viewport navigation, object transform
updates, Edit Mode geometry updates, and viewport animation playback temporarily
set parallax depth to zero for drawing. This also bypasses local height AO,
parallax sun self-shadowing, and depth intersections. Original node values and the
global Parallax toggle are preserved. Ordinary material edits are not a trigger.

Relief returns after about 0.067 seconds without movement (one third of the original
0.2-second delay); a timer requests the restoring redraw. Both final stills and final animation renders keep full quality.
Baked reflection capture is outside the temporary viewport bypass. This does not
reduce geometry extraction or other screen-effect costs; no performance multiplier
is promised.

Blender 4.4.3 checks: native viewport transform/navigation activation, pixel changes
and automatic idle restoration, quick viewport playback, identical F12 on/off
output, and two final animation frames identical to the full-quality reference.

## Quick Supersampling

The separate Quick checkbox beside Supersampling uses 1x during viewport movement,
object transforms, Edit Mode geometry updates, and viewport playback. It restores
the saved supersampling level after the same ~0.067-second idle delay. It works
independently of parallax Quick Navigation and never modifies the saved value.
FXAA and other effects remain enabled. F12 stills and animation keep full quality.
Native Blender 4.4.3 tests verified actual G-buffer dimensions during movement and
restoration, independent parallax controls, and identical final still/animation output.

## Quick Sun Shadows, AO, and Contact Shadows

Independent Quick checkboxes beside Shadow Res, AO Quality, and Contact Steps use
1024 shadow-map resolution, Low (16) AO samples, and 8 contact-shadow steps during
viewport movement/playback. The same ~0.067-second idle delay restores saved values.
AO's lower budget also applies to parallax height AO. These overrides are viewport
only; final stills, animation, and other captures use the saved settings.
Validated native viewport shadow allocation changes, effect sample inputs,
automatic restoration, playback, saved setting preservation, and matching final
still/animation outputs in Blender 4.4.3.
