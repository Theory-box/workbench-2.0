# Per-object lightmap settings

The Cycles Lightmap Bake sidebar edits the **active mesh object's** settings:
Resolution, Samples, Lighting source, and Lighting Passes. Selecting another object
shows its values; settings are stored in the blend file. New/unconfigured objects
default to 2048 pixels, 64 samples, Scene Lighting, and Direct + Indirect.

**Bake Selected** uses every selected mesh's own saved values. It groups matching
configurations into bake calls. Images are assigned only after every group succeeds;
failure/cancellation preserves previous lightmap assignments. Modifiers on selected
targets are disabled during the operation and restored afterward.

Direct and Indirect select the corresponding Cycles diffuse bake passes; Color remains excluded. **Keep Live Lighting** is enabled by default per object: the lightmap is added to live Sun, Sky/Ground, and Key Light, preserving parallax self-shadowing. Use Indirect-only for baked bounce plus real-time direct light. Turn Keep Live Lighting off to replace live lighting with a complete bake; otherwise Direct/Both bakes may double direct illumination. This display toggle takes effect without rebaking. Screen AO/cavity retain their existing behavior.

Existing scene-wide settings are retained as legacy data but are
no longer used to choose object bake settings.

Validated with mixed 128/256 images, different sample/pass settings in one selection,
direct/indirect/both outputs, cancellation in the second batch, and save/reopen.
The 2048 default is asserted without allocating an unnecessary large test bake.

## Responsive baking

The Bake Selected button starts native asynchronous Cycles bake jobs. Object preparation yields between objects, and matching per-object settings are baked in successive jobs. Blender keeps redrawing during the bake; Esc cancels it. Scene input is temporarily locked while private meshes/materials and temporary lighting are in use. Completed images are published only after all groups finish. Cancellation restores the previous bakes and original modifiers/lighting after the native job has stopped.

UV unwrap/packing and final image packing still execute on the main thread and can pause briefly on large meshes/images. This does not promise uninterrupted interaction during those preparation/finalization steps.

Validation: Blender 4.4.3 native UI job test with two sample-setting groups, timer heartbeat during active jobs, simulated Esc cancellation, previous-image/mesh preservation, modifier/world restoration, and handler cleanup. Existing per-object pass/settings and modifier cancellation/error regression tests pass. Native lifecycle was checked against Blender v4.4.3 `object_bake_api.cc`.
