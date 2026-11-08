# Live parallax lightmap coordinates (experimental)

Lightmapped parallax materials now translate the existing relief hit into the
lightmap UV basis using screen derivatives. This supports separate rotated,
mirrored and scaled lightmap UV layouts without an extra height ray march or
additional lightmap samples. Filtering uses the original lightmap derivatives.
Zero depth, global parallax disable and quick-parallax bypass retain original UVs.
Both additive and replacement lightmap paths use this lookup.

This is a local tangent approximation, not newly baked relief lighting. It does
not generate additional bounce or baked shadows. Large offsets can cross packed
UV island boundaries and read neighboring charts: this prototype has no island
ownership guard. Test seams and grazing views before relying on it.

Blender 4.4.3 F12 comparison against an analytically shifted separate rotated,
mirrored, anisotropic UV map passed (maximum channel error 0.0002442). Native
viewport depth edits and global toggle restoration passed. No GPU timing benchmark
or production-scene island validation has been performed.
