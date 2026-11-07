# vertex_lit_renderer/__init__.py

bl_info = {
    "name":        "Workbench 2.0",
    "author":      "Theory-box / Claude",
    "version":     (0, 19, 10),
    "blender":     (4, 2, 0),
    "location":    "Properties > Render > Render Engine → Workbench 2.0",
    "description": "Solid studio + live-node material renderer (+ screen-space AO) for retro game look-dev. "
                   "Lighting (diffuse + shadow + ambient) is computed per vertex "
                   "with per-pixel scene lighting, shadows, and live node materials. "
                   "Optional live material-node preview (transpiles the shader graph to GLSL).",
    "warning":     "Blur/parallax branch beta: early development. Experimental. F12 render is viewport-quality. Default: Solid studio shading",
    "category":    "Render",
}

import bpy


def register():
    from . import props, engine, ui, bake, splat_ops, planar, lightmap, parallax, blur
    blur.register()
    parallax.register()
    props.register()
    planar.register()
    lightmap.register()
    engine.register()
    bake.register()
    splat_ops.register()
    ui.register()


def unregister():
    from . import props, engine, ui, bake, splat_ops, planar, lightmap, parallax, blur
    ui.unregister()
    splat_ops.unregister()
    bake.unregister()
    engine.unregister()
    lightmap.unregister()
    planar.unregister()
    props.unregister()
    parallax.unregister()
    blur.unregister()
