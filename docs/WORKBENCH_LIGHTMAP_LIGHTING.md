# Cycles lightmap lighting sources

In **N sidebar > Workbench 2.0 > Cycles Lightmap Bake**, choose Lighting:

- **Cycles — Workbench Lighting:** temporarily disables existing light objects
  (including Sun objects and light sources in instanced collections), replaces the
  world with a Sky/Ground environment, and adds a Sun using the Workbench direction,
  color, intensity, and enabled state. Key Light is excluded. Mesh emission stays
  active. Sun and Sky/Ground checkboxes are respected.
- **Cycles — Scene Lighting:** uses the scene as configured. This remains the
  default to preserve existing bake behavior.

The existing Bake Selected workflow, resolution, samples, and clear/rebake controls
remain unchanged. Materials are not whitened. This uses Cycles direct + indirect
diffuse baking with Color excluded. Scene bounce and other Cycles settings remain
in effect. Original world and light visibility are restored on completion,
cancellation, or exceptions; temporary lighting datablocks are removed.

The conversion uses a sharp directional Sun with energy pi times Workbench's
intensity, and two constant world hemispheres. On an unoccluded diffuse surface,
their cosine-weighted integration reproduces our normal-based Sky/Ground blend.
Cycles then adds real occlusion, shadows, and bounce lighting. This means enclosed
rooms can be darker and colored surfaces can produce color bleeding. Workbench
shadow-map softness, AO, cavity, and camera Key Light are not baked into this rig.
Normal Cycles shadows remain enabled regardless of the Workbench shadow-map toggle.
The world is an illumination match, not a match for our visible background gradient.

Blender 4.4.3 CPU bake tests at 128px validated Sun brightness, upward/downward/tilted
hemisphere response, existing lights/world/Key Light exclusion, retained mesh
emission, red-wall bounce onto a floor, Scene Lighting mode, and state restoration
after success, cancellation, and an injected exception. Large scenes, linked
libraries, animated light visibility, and collection-instance light exclusion
have not been separately validated. No Parallax Window capture is implemented yet.

This development branch includes the previously tested standard Bump-node support;
it does not include the abandoned silhouette experiment.
