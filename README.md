# Workbench 2.0

Experimental Blender renderer with live material-node previews, shadows, and screen-space ambient occlusion.

> **Very early development — please be careful when testing.** Expect bugs, unsupported nodes, visual differences, slowdowns, and possible crashes. Save your work, back up your projects, and test on copies of .blend files. Do not rely on this renderer for production work yet.

## Status

Current version: **0.19.2 beta**. Development and recent tests use **Blender 4.4.3**. The add-on declares Blender 4.2 as its minimum; other versions have not been verified in this testing pass.

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
