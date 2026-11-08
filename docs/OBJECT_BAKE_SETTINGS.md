# Per-object lightmap settings

The Cycles Lightmap Bake sidebar edits the **active mesh object's** settings:
Resolution, Samples, and Keep Live Lighting. Lighting source and Lighting Passes are global scene settings at the top of the panel. Selecting another object
shows its values; settings are stored in the blend file. New/unconfigured objects
default to 2048 pixels and 64 samples. Scene lighting controls default to Scene Lighting and Direct + Indirect.

**Bake Selected** uses every selected mesh's own saved values. It groups matching
configurations into bake calls. Images are assigned only after every group succeeds;
failure/cancellation preserves previous lightmap assignments. Modifiers on selected
targets are disabled during the operation and restored afterward.

Direct and Indirect select the corresponding Cycles diffuse bake passes; Color remains excluded. **Keep Live Lighting** is enabled by default per object: the lightmap is added to live Sun, Sky/Ground, and Key Light, preserving parallax self-shadowing. Use Indirect-only for baked bounce plus real-time direct light. Turn Keep Live Lighting off to replace live lighting with a complete bake; otherwise Direct/Both bakes may double direct illumination. This display toggle takes effect without rebaking. Screen AO/cavity retain their existing behavior.

Scene lighting source and pass settings apply to every selected bake target. Older per-object source/pass values are ignored. Resolution and samples remain per object.

Validated with mixed 128/256 images, different sample/pass settings in one selection,
direct/indirect/both outputs, cancellation in the second batch, and save/reopen.
The 2048 default is asserted without allocating an unnecessary large test bake.
