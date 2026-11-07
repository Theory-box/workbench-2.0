# Blender Bump node support

Development branch: `feature/bump-node`, based on published main 0.19.16.
The experimental silhouette branch is not included.

Use Blender's standard **Bump** node: connect a supported height graph to Height,
then Normal to the surface shader's Normal input (for example Principled BSDF).
Use Non-Color for height images. Strength, Distance, Filter Width, and Invert
update without shader recompilation. Muting or leaving Height unconnected passes
through the input normal. Bump nodes can be chained through Normal and used inside
node groups.

The height graph is sampled at the shading point and two pixel-coordinate offsets,
using Filter Width, to derive a world-space surface gradient. Supported UV,
Generated, and Object coordinate graphs use the renderer's existing graph compiler.
No mesh displacement or silhouette change occurs. With parallax, bump builds on
the relief normal and samples the displaced UVs. The resulting normal is used for
live lighting and the normal buffer used by screen cavity/AO.

This does not implement every Blender material closure or unsupported upstream node.
Normal Map nodes are not added by this change. Existing mixed-shader/surface-group
limitations remain. Static lightmaps contain no lighting direction and cannot be
relit by changing a bump normal. Bump in albedo-bake or Blur-source graphs has no
surface context and falls back with a compiler note. Nested bump-derived heights
and arbitrary view-dependent height graphs have not been validated.

Validation in Blender 4.4.3: encoded normals compared against Eevee at one render
sample for linear and sinusoidal heights, Strength, Invert, Filter Width, chained
normals, and backfaces. Tests also cover F12 lighting changes, mute/unconnected
bypasses, live viewport edits, image/procedural heights, a node group, parallax
integration, and shader reuse after a Strength edit. A rendered image-height test
was visually inspected. These are controlled scenes, not a claim of universal
Cycles/Eevee equivalence or production-scene performance.

Behavior references examined:
- https://docs.blender.org/manual/en/4.4/render/shader_nodes/vector/bump.html
- https://github.com/blender/blender/blob/v4.4.3/source/blender/nodes/shader/nodes/node_shader_bump.cc
- https://github.com/blender/blender/blob/v4.4.3/source/blender/gpu/shaders/material/gpu_shader_material_bump.glsl
