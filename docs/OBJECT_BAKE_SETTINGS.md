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
