# Solid and Normal surface-detail views

Solid uses the regular material shading path with a uniform display albedo. Its color picker defaults to white. Surface Detail defaults on and retains supported material normal inputs, Bump nodes, parallax relief, sun self-shadowing, and height AO. Turning it off suppresses material normal/parallax detail while retaining the regular lighting/lightmap path. The global Parallax toggle and Quick Navigation still apply.

The override is applied after graph evaluation, so color branches shared with height or alpha are not changed. Material alpha is preserved. Baked planar color-reflection overlays are omitted from Solid and Normal views. Existing unsupported shader nodes remain unsupported; this change does not add a Normal Map node implementation.

Normal view now encodes the final shaded normal, including Bump and parallax-derived normals, in the selected World or Screen space. Lighting and height AO do not tint the encoded normal. Parallax depth intersections remain active where enabled.

Validated in Blender 4.4.3 with F12 white-material reference comparison, solid tint, surface-detail toggling, parallax sun shadows, bump and relief normal outputs, screen-space normals, non-node fallback, and native viewport switching/restoration. Quick Navigation tests cover movement, automatic restoration, playback, and unchanged final still/animation output. The idle delay is now 0.2 / 3 seconds.
