# Workbench 2.0 feature guide

Experimental Blender renderer with live material-node previews, shadows, and screen-space ambient occlusion.

> **Very early development — please be careful when testing.** Expect bugs, unsupported nodes, visual differences, slowdowns, and possible crashes. Save your work, back up your projects, and test on copies of .blend files. Do not rely on this renderer for production work yet.

## Status

Published version: **0.19.17 beta**. Development and primary tests use **Blender 4.4.3**. The add-on declares Blender 4.2 as its minimum; the new features have not been validated on 4.2.

Version **0.19.15** adds **Cavity World > Method > XeGTAO
(experimental)**. Classic SSAO remains the default for existing scenes. This is
a GLSL adaptation of XeGTAO's horizon integral with a custom depth-aware 5x5
spatial filter, full-resolution depth sampling and fixed noise. It does not yet
include the upstream depth-MIP optimization, temporal accumulation, bent normals,
or all upstream heuristics. Perspective/orthographic F12, viewport switching,
object/camera movement, alpha preservation, zero strength, parallax, AO exclusion,
and supersampling smoke tests pass in Blender 4.4.3. Heavy-scene performance and
ray-traced-reference accuracy remain unmeasured. MIT attribution is included in
`vertex_lit_renderer/licenses/XeGTAO.txt`. Existing AO/ridge compositing is retained.

Materials have a **Scene AO** reception slider (0–1) in Material Properties >
Workbench 2.0 and on the Parallax node. It scales scene AO and its World Ridge
component for that material, for both Classic SSAO and experimental XeGTAO.
It does not disable casting AO, Height AO, Cavity Screen, or contact shadows.
Shared materials share this setting. It applies to opaque material rendering;
transparent overlays and non-textured diagnostic view modes retain their existing
scene-wide behavior. The existing object-ID buffer's alpha carries the mask, so
AO now enables the auxiliary buffers even without outlines/cavity/contact shadows.

The Parallax node now exposes
**Shadow Height** under Sun Self-Shadow: 1.0 preserves existing shadows, values
above 1 exaggerate shadow height, and 0 disables height-field sun occlusion.
It updates live without changing Depth, visible relief, normals, or height AO.
Large multipliers may need higher Shadow Quality to avoid missing thin features.

**Depth Intersections** (enabled by default) writes the parallax ray hit into the
depth buffer. Raised relief can cover the base of intersecting objects; recessed
relief can reveal them. This uses the existing Depth/Midlevel and updates live.
Screen-space AO and contact shadows see this depth in the normal rendering path.
Disable the toggle to restore flat mesh intersections. It does not expand mesh
silhouettes, create geometry, or change the geometry-only sun shadow map. The
separate AO-exclusion pass and baked planar reflection overlays still use mesh
depth; disable Depth Intersections on those surfaces if they conflict. Transparent
surfaces still do not write opaque occlusion depth. Shader depth writes can reduce
early depth rejection efficiency; heavy-scene performance has not been benchmarked.

Validated on Blender 4.4.3: native viewport live toggles, F12 cube/heightmap overlap,
raised/recessed constant heights against actual geometry in perspective and ortho,
screen-space AO/contact response, zero depth, and existing lightmap/shadow tests.

This release includes material parallax, height-field sun self-shadowing and AO,
UV graph Blur caches, extended-UV alignment fixes, shared full-resolution caches
for periodic textures, live Color Ramp position/color edits, and opt-in screen-space
sun contact shadows.

### Sun contact shadows (0.19.11 beta)

Render Properties > Workbench 2.0 > Lighting > Sun > **Contact Shadows** adds
short-distance screen-space shadows to the live sun. It is off by default.
Trace Distance and Thickness use scene world units; Steps controls sampling
quality (8–64). Keep distances short and reduce Thickness if unrelated surfaces
produce false shadows. Existing sun shadow maps remain responsible for general
coverage and off-screen occluders.

The effect runs in the viewport and F12, reuses the scene depth buffer, and stores
the sun contribution separately during the existing draw. It does not redraw the
scene or use temporal history. Extra full-resolution targets consume GPU memory;
heavy-scene performance has not been measured. Ambient/key lighting and baked
lightmaps are not darkened by this effect. Partial-alpha surfaces are skipped;
hidden geometry is absent; parallax height contributes when Depth Intersections is enabled. The effect
is bypassed in scenes with active splat clouds until their compositors support
separate sun output. Long traces, thin geometry, and screen boundaries remain
limitations.

Color Ramp stop positions and RGBA colors update as live uniforms, including in
parallax height graphs and Blur sources. Adding/removing stops or changing the
interpolation mode still recompiles the shader. A ramp edit upstream of Blur still
refreshes the cached image, but reuses its source shader.

## General UV Blur node (0.19.5 development beta)

Add **Workbench 2.0 Blur** in the Shader Editor and connect any supported UV-based
color/value graph through its Color sockets. Use it on color textures, masks,
procedural Noise/ramps/mixes, or before the Parallax node's Height. Color-to-value
conversion works through Blender's usual socket connections. Group inputs and
nested Blur nodes are supported.

- **Radius**: Gaussian support radius at the requested pixels-per-UV resolution (0–64).
- **Strength**: blend between unfiltered and filtered input (0–1).
- **Resolution**: requested pixels per UV unit (128–2048).
- **Max Cache Edge**: appears for extended UV ranges, limits the automatic cache
  dimensions (default 2048). Increase for finer detail on large UV layouts; the
  64 MiB memory cap still applies. The node shows the resulting cache dimensions.
- **UV Cache**: Auto shares the original full-resolution 0–1 tile for graphs proven
  periodic (repeating image textures, supported integer UV transforms, and pointwise
  color operations). Nonperiodic graphs use the object's UV range. Repeat Tile forces
  the original behavior; Object UV Range forces expanded coverage.
- **Edges**: Repeat tiles the cache; Extend clamps it.

Zero Radius, zero Strength, and muting bypass the cache exactly. Otherwise the
upstream graph is evaluated into a linear floating-point GPU texture and filtered
in two passes. Alpha is filtered premultiplied to avoid dark color fringes.

Upstream values, connections, groups, animation, image pixels/color space/reloads,
and Blur settings invalidate relevant cached results. Camera movement reuses them;
mesh UV edits update sampling and cached coverage immediately. Undo/redo and file loading clear runtime
caches. Caches are not saved into the blend file and do not create image datablocks.
The retained texture cache is limited to 64 MiB, plus temporary rebuilding buffers.
Dirty/generated source images receive one CPU content check per draw (shared among
Blur nodes) because Blender does not expose a reliable pixel revision counter;
large edited images can therefore still add redraw overhead.

For nonperiodic graphs, the cache follows each object's actual UV range, including offset/negative UVs,
with padding outside expanded bounds. Periodic image graphs retain the original
shared tile, avoiding resolution loss and repeated large-cache rebuilds. This keeps nonperiodic procedural patterns
aligned with unblurred color, rather than repeating an unrelated 0–1 tile. The same
material can use different coverage on different objects. Existing 0–1 layouts
retain their tile behavior; standalone albedo baking still evaluates a 0–1 tile.
Inputs must use one UV coordinate domain. Sampling beyond the cached region still
repeats or clamps according to Edges; extreme parallax travel can exceed the padding.
Large layouts may need a higher Max Cache Edge to preserve small features.
Different UV maps mixed upstream, Generated/Object/view-dependent inputs, movies,
image sequences, and UDIMs are not supported; the node shows a warning and bypasses
the blur. Other renderers receive a passthrough fallback. Existing limitations of
our material compiler and named-UV reflection-property support still apply.

Checked with native GPU tests, live viewport edits/undo/redo, F12, parallax heights,
animation inside groups, procedural inputs, nested caches, alpha edges, cache
limits, save/reopen, and albedo baking. Tests are small controlled scenes; large
production scenes and other GPU vendors remain unverified.

## Parallax

Add **Workbench 2.0 Parallax** to the Shader Editor Add menu/search.
Connect a Non-Color height image to its **Height**, then connect its **Displacement**
output to **Material Output > Displacement**. Keep the existing surface shader.
Only the connected, unmuted node on the active Material Output enables the effect.

- **Depth** is relief depth in world units. Start small (for example 0.01–0.05).
- **Midlevel** is the original surface height: 0.5 centers relief; 1 recesses it.
- **Quality** sets the maximum ray steps (8–128), followed by five refinement steps.
- **Sun Self-Shadow** traces the height field toward the built-in sun (enabled by default).
  **Shadow Quality** controls 8–128 samples, independently of view-ray quality.
  This adds hard local shadows to sunlight only; ambient/key lighting is unchanged.
  It works independently of the scene shadow-map toggle. Complex height graphs cost
  more per sample; disable this option or reduce quality to regain performance.
- **Height AO** includes the virtual height field in **Cavity World** (scene AO).
  Enable Cavity World to see it; its Distance, Bias, Valley, Ridge and Quality
  controls also govern this local effect. Object AO exclusions are respected.
  The local horizon approximation uses 16–64 extra height samples per shaded pixel;
  complex procedural height graphs can be costly. Disable Height AO to retain only
  ordinary scene AO. Like existing scene AO, it modulates final surface color,
  including baked lighting; it is not a directional sky-light visibility solution.
- **Cavity Screen** already reads parallax relief normals. Use its existing Ridge
  and Valley controls; no second cavity filter is added. It remains screen-space
  and therefore depends on pixel resolution and viewing distance.
- **UV Map** selects the affected map. Blank uses each mesh's render-active map.
  Use that same map for the height and surface textures; Mapping/Vector Math scaling
  remains part of those texture graphs. Implicit and named references to the same
  active map move together. Height values are clamped to 0–1.

The renderer traces the UV height field and derives relief normals for lighting.
Color and alpha sampling on that map follows the intersection, in viewport and F12.
Shared materials share the effect. Baked lightmap coordinates remain unchanged.
A tested Cycles bake preserves surface UVs, parallax movement, local height AO and
screen cavity. A lightmap replaces live lighting: its RGB values contain no light
direction, so relief-normal relighting and live sun self-shadows do not affect the
baked illumination. Directional lightmaps would be a separate lighting feature.
Depth and quality edits use uniforms; they do not recompile the shader.

This is apparent surface relief, not mesh displacement: silhouettes and shadows cast onto other objects
remain unchanged. Height-field self-shadowing cannot cross mesh/UV discontinuities
reliably; low sample counts can miss narrow features, and sun-shadow softness is not implemented.
Local AO assumes a continuous height field and cannot account for nearby separate
objects (ordinary scene AO still handles those). Its tangent-corrected horizon
estimate is approximate, especially on steep relief and UV seams. Extreme grazing angles fade
out to avoid unbounded offsets. Use UV-based height graphs; Generated/Object/triplanar
height coordinates are not supported by this first version. The custom node must be
at material level (a reroute to the output is supported); nesting it inside a group
is not supported. Existing planar reflection overlays/roughness evaluation are not
parallax-warped. Camera-independent albedo baking deliberately excludes parallax.
Other engines see a zero-displacement fallback, not equivalent relief.

Validation covers small native GPU viewport/F12 tests, named/default UV aliases,
scaled and mirrored UVs, perspective/orthographic cameras, nonuniform/mirrored object
scales, Edit Mode UV changes, live parameters/muting, lightmap isolation, and save/reopen.
Heavy-scene performance and other GPU vendors remain unverified.

## Changes in 0.19.3 beta

- Fix the shared shader compile error that prevented Solid, Random, Attribute, Normal, and Depth modes from drawing.
- Initialize auxiliary coverage and object IDs for outline/cavity effects in non-textured modes.
- Report final-render view-mode draw failures instead of silently hiding them.

All six modes were checked in the live viewport and F12, including repeated switching back to Solid. This retains the Edit Mode and empty-geometry fixes from 0.19.2.

## Changes in 0.19.2 beta

- Keep named UV and baked-lighting buffers intact across idle Edit Mode frames.
- Remove obsolete per-frame Edit Mode extraction and forced redraws.
- Evict stale geometry and shadow caches when objects or instance sources become empty.

This supersedes 0.19.1, which could display the correct result for one frame after an edit and then replace it with legacy geometry.

## Changes in 0.19.1 beta

- Add selected-object Cycles lightmap baking, rebaking, and clearing in the N sidebar.
- Automatically unwrap a separate lighting UV set, including hidden mesh faces, and preserve existing materials and UVs.
- Refresh geometry and UV coordinates during Edit Mode.
- Honor named UV Map selections in material color/alpha graphs, including live selection changes and baked-lighting combinations.
- Match Blender gradient output bounds; preserve direct color-to-Surface graphs and shader reroutes.
- Respect muted-node bypasses and invalidate shader caches when mute state changes.

## Install

Download the add-on ZIP from [Releases](https://github.com/Theory-box/workbench-2.0/releases), then install that ZIP through Blender Preferences > Add-ons > Install from Disk. Enable the add-on and choose **Workbench 2.0** as the render engine. Restart Blender after replacing an existing installation.

## Planar reflection baking

Select the front face or coplanar faces in Edit Mode, enter Rendered viewport mode, and open **N sidebar > Workbench 2.0 > Planar Reflection Bake**. Set the scene camera, then click **Bake / Rebake**. In Object Mode, rebaking reuses the configured faces. **Clear Reflections** removes the assignment.

The bake retains existing materials and supported roughness maps. Roughness changes filter the reflection live without recapturing the scene. For a sharp mirror, start with Metallic 1 and Roughness 0. Captures are cropped to the selected faces to use texture resolution efficiently, and images are packed into the blend file.

This is a fixed-camera, single-plane bake per object. Rebake after camera, geometry, or lighting changes. Apply or disable reflector modifiers. Transparent and recursive reflections are not supported, and roughness filtering is approximate.

## Cycles lightmaps

In the 3D View **N sidebar > Workbench 2.0 > Cycles Lightmap Bake**, choose
**Resolution** and **Samples**, select mesh objects in Object Mode, then click
**Bake Selected**. The same button rebakes those objects. There is no scene-wide
bake command. **Clear Bake Selected** removes lighting assignments while preserving materials and UV maps. Shared images remain while still used. Hidden mesh elements are temporarily revealed for the unwrap, then restored.

The operator smart-unwraps and packs a separate UV set and bakes Cycles diffuse
Direct + Indirect lighting with Color excluded. Existing material shaders stay
intact. Each object receives its own packed, linear floating-point image, used
for diffuse lighting in the viewport and F12. Original material UVs and scene
settings are restored. AO, cavity, outline, and other existing effects are not
disabled or overridden.

Set up the scene lights/world for Cycles first. Apply topology-changing modifiers
before baking; the operator warns and stops instead of applying them. The bake
is static: rebake after lighting or geometry changes. This is diffuse lighting,
not a bake of metallic reflections or transmission. Collections/GN instances do
not inherit the source object's position-specific lightmap. Shared meshes are
made independent for selected bake targets; shared materials remain shared.

## Known limitations

- Material graphs are translated to GLSL; support is incomplete and results can differ from Cycles or Eevee.
- Partial-alpha sRGB image colors have a known mismatch against Cycles.
- Shadow casters currently use geometry-only depth; material alpha is not evaluated for shadow casting.
- Broader GPU failure recovery remains experimental.
- Shader groups connected directly to Material Output Surface can fall back to simplified shading.
- Mapping X/Y rotations are not implemented; Texture and Normal mapping modes are incomplete.
- UV Map From Instancer is not implemented. Named UV selection currently applies to material color/alpha, not planar-reflection roughness graphs.
- Named-UV materials currently use individual object draws instead of GPU instancing; dense instanced scenes may be slower.

## Development

`main` holds published snapshots. Use a separate branch for each fix or feature, test it in a separate Blender process, and review changes before merging into `main`.

Tests under `vertex_lit_renderer/tests` are development scripts. Some need a graphical GPU context or test fixtures and are not a universal headless test suite.

## Credits

- **Theory-box** — project creator and maintainer; direction and hands-on testing.
- **OpenAI Codex** — AI-assisted implementation, debugging, performance investigation, and regression testing.

Codex is an AI development assistant, not a separate human maintainer or GitHub account.

