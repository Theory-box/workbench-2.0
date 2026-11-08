# Workbench 2.0

**A custom Blender render engine for interactive material previews, architectural visualization, and stylized rendering—in the viewport and in F12 renders.**

Workbench 2.0 combines a Workbench-style lighting workflow with textured materials, supported Shader Editor graphs, shadows, ambient occlusion, and height-map surface relief. It is a separate render engine supplied by an add-on, rather than a modification of Blender's built-in Workbench renderer.

It uses Blender's GPU API and custom rasterization shaders. It is not a path tracer or a replacement for all Cycles/Eevee features. Cycles can optionally supply baked lighting for the scene.

> **Very early development — please be careful when testing.** Expect bugs, unsupported nodes, visual differences, slowdowns, and possible crashes. Save your work and test on copies of projects. Not recommended for production-critical work.

[Download the beta](https://github.com/Theory-box/workbench-2.0/releases) · [Detailed feature guide](docs/FEATURE_GUIDE.md) · [Report an issue](https://github.com/Theory-box/workbench-2.0/issues)

## Features

- **Viewport and F12 rendering:** preview your scene interactively and render through Blender's normal render workflow.
- **Live materials:** image textures and supported procedural, color, math, UV, and node-group graphs. Supported parameter edits update live; structural changes can require shader compilation.
- **Simple lighting controls:** camera-relative Key Light, Sky/Ground fill, and Sun, each with an independent on/off checkbox that preserves its settings.
- **Sun shadows:** shadow maps plus optional screen-space contact shadows for nearby detail.
- **AO and cavity:** Classic SSAO, experimental XeGTAO-based AO, screen cavity, and outlines. A per-material Scene AO slider controls how much scene AO a surface receives.
- **Height-map parallax:** the custom Workbench 2.0 Parallax node adds apparent relief without subdivision, with local sun self-shadowing, height AO, relief normals, and depth intersections with other objects. A global toggle lets you disable it across the scene. Optional Quick Navigation temporarily bypasses parallax during viewport movement and playback, with immediate restoration when stationary; final renders retain full quality.
- **Standard Bump node:** height-based normal shading with live controls, image/procedural inputs, and support for chaining and parallax integration.
- **General UV Blur node:** blur supported UV-based color or value graphs, including height maps, using automatically refreshed GPU caches.
- **Baked planar reflections:** capture selected coplanar faces for a fixed camera, retain existing materials, and adjust supported roughness inputs live. Rebake or clear the reflection when needed.
- **Cycles lightmaps:** Bake Selected automatically creates a separate lighting UV layout and bakes diffuse direct, indirect, or both illumination passes. Resolution and samples are remembered per object; rebake and clear are available in the sidebar. Keep Live Lighting adds baked bounce to real-time lighting and parallax self-shadowing.
- **Alternative view modes:** Textured, Solid, Random, Attribute, Normal, and Depth, plus anti-aliasing controls.

## Install and get started

1. Download the **add-on ZIP asset** from [Releases](https://github.com/Theory-box/workbench-2.0/releases), rather than GitHub's source-code archive.
2. In Blender, open **Preferences → Add-ons → Install from Disk**, select the ZIP, and enable Workbench 2.0.
3. Choose **Workbench 2.0** in the Render Engine selector and switch the viewport to **Rendered** shading.
4. Open **Render Properties → Workbench 2.0** for lighting, shading, AO, shadows, and view modes. Press **F12** for a final render.
5. Open the 3D View's **N sidebar → Workbench 2.0** for planar-reflection and Cycles-lightmap baking.

Restart Blender after updating an existing installation.

For parallax, add **Workbench 2.0 Parallax** in the Shader Editor. Connect a UV-based height map to **Height** and its output to **Material Output → Displacement**, keeping your existing surface shader. Use **Non-Color** for height images and start with a small Depth. The global switch is under **Render Properties → Workbench 2.0 → Shading → Parallax**.

## Compatibility and limitations

**Current release: 0.19.19 beta.** Development and primary testing use **Blender 4.4.3**. The add-on declares Blender 4.2 as its minimum, but current features have not been validated on 4.2. Other GPU vendors and large production scenes are not comprehensively tested; performance depends on scene complexity and enabled effects.

- Shader-node support is incomplete. Materials can look different from Cycles or Eevee; custom nodes do not produce equivalent effects in those engines.
- Parallax changes apparent surface depth, not mesh geometry or the outer silhouette. UV seams, extreme grazing angles, and complex height graphs have quality/performance limits.
- Screen-space effects cannot see hidden or off-screen geometry. XeGTAO is an experimental adaptation, not the complete upstream implementation.
- Planar reflections are fixed-view bakes, not general real-time reflections. Rebake after camera, geometry, or lighting changes.
- Lightmaps are static diffuse lighting. Choose existing Cycles scene lighting or the temporary Workbench lighting rig. Bake-target modifiers are temporarily disabled and then restored; generated modifier surfaces may not match the base-mesh lightmap. Baking blocks the interface until completion. They do not bake parallax as real geometry.
- Sun shadow maps use geometry-only depth; material alpha is not evaluated for casting those shadows.

See the [feature guide](docs/FEATURE_GUIDE.md) for controls, tested behavior, cache restrictions, and further known limitations. Release notes record individual changes.

## Latest update

**0.19.19 beta** adds a consolidated **Quick Mode** panel with a master eye toggle and independent parallax, supersampling, sun-shadow, AO, and contact-shadow controls. Selected reductions apply only during viewport movement/playback and restore after about 0.067 seconds. Final renders retain full quality.

**Solid** view retains supported bump/parallax detail with a uniform color picker and Surface Detail toggle; **Normal** view displays bump and parallax-derived normals. Lightmaps gain global intensity, scene-wide lighting source/pass controls, and experimental real-time parallax UV displacement. Resolution and samples remain per object. Large parallax offsets can cross packed lightmap UV islands; test seams before relying on this feature.

See [Quick Mode](docs/QUICK_NAVIGATION.md), [surface-detail views](docs/SOLID_SURFACE_DETAIL.md), and [parallax lightmaps](docs/PARALLAX_LIGHTMAP_SHIFT.md).

### Previous update

**0.19.18 beta** adds Quick Navigation and per-object lightmap bake settings, including Direct / Indirect / Both passes. Bake-target modifiers are temporarily disabled and restored. **Keep Live Lighting** defaults on, preserving live Sun and parallax self-shadowing with baked lighting; choose **Indirect** to avoid doubling direct light. The previous blocking bake behavior is retained so the temporary Solid viewport is not exposed during a background job.

See [Quick Navigation](docs/QUICK_NAVIGATION.md) and [per-object bake settings](docs/OBJECT_BAKE_SETTINGS.md).

### Previous update

**0.19.17 beta** adds support for Blender's standard **Bump** node (Strength, Distance, Filter Width, Invert, and normal chaining), plus **Cycles — Workbench Lighting** for lightmap baking. The new lighting mode transfers our Sun and Sky/Ground into a temporary Cycles rig, preserves mesh emission, and restores original lights/world afterward. **Cycles — Scene Lighting** retains the existing workflow. The silhouette-clipping experiment is not included.

See the [Bump guide](docs/BUMP_NODE.md) and [lightmap lighting guide](docs/WORKBENCH_LIGHTMAP_LIGHTING.md) for tests and limitations.

### Previous update

**0.19.16 beta** adds the global Parallax toggle and separate Key Light, Sky/Ground, and Sun checkboxes. Disabling a control preserves its original settings. F12 tests verified that off matches zero intensity/depth and re-enabling restores the image; live viewport checks covered parallax and sky/ground switching.

## Development and credits

`main` holds published snapshots. Changes are developed and tested on feature branches before release. Scripts in `vertex_lit_renderer/tests` are development tests; some require a graphical GPU context or external fixtures.

- **Theory-box:** project creator and maintainer; direction and hands-on testing.
- **OpenAI Codex:** AI-assisted implementation, debugging, performance investigation, and regression testing. Codex is an AI assistant, not a separate human maintainer or GitHub account.
- **Intel XeGTAO:** the experimental AO adaptation includes [MIT attribution](vertex_lit_renderer/licenses/XeGTAO.txt).
