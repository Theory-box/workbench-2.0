"""Temporary Cycles lighting derived from Workbench controls; no mesh duplication."""
from contextlib import contextmanager
import math
import bpy
from mathutils import Vector


@contextmanager
def lighting_source(scene, source):
    if source != 'WORKBENCH':
        yield
        return
    from .engine import _compute_sun
    settings = scene.vertex_lit
    direction, color, sun_strength, hemi_strength = _compute_sun(settings)
    original_world = scene.world
    hidden = []
    world = sun_data = sun_object = None
    try:
        # Include light sources in instanced collections, not just scene.objects.
        # Mesh emission is deliberately untouched.
        for ob in bpy.data.objects:
            if ob.type == 'LIGHT' and not ob.hide_render:
                hidden.append((ob, ob.hide_render))
                ob.hide_render = True
        world = bpy.data.worlds.new('.VLR temporary bake world')
        world.use_nodes = True
        nodes, links = world.node_tree.nodes, world.node_tree.links
        nodes.clear()
        coord = nodes.new('ShaderNodeTexCoord')
        separate = nodes.new('ShaderNodeSeparateXYZ')
        # Cycles world Object coordinates are the outgoing world ray direction.
        links.new(coord.outputs['Object'], separate.inputs[0])
        upper = nodes.new('ShaderNodeMath'); upper.operation = 'GREATER_THAN'
        links.new(separate.outputs['Z'], upper.inputs[0]); upper.inputs[1].default_value = 0
        mix = nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MIX'
        mix.inputs[1].default_value = (*settings.ground_color, 1)
        mix.inputs[2].default_value = (*settings.sky_color, 1)
        links.new(upper.outputs[0], mix.inputs[0])
        background = nodes.new('ShaderNodeBackground')
        background.inputs['Strength'].default_value = hemi_strength
        links.new(mix.outputs[0], background.inputs['Color'])
        output = nodes.new('ShaderNodeOutputWorld')
        links.new(background.outputs[0], output.inputs['Surface'])
        scene.world = world
        if sun_strength > 0:
            sun_data = bpy.data.lights.new('.VLR temporary bake sun', 'SUN')
            sun_data.color = color
            # Workbench diffuse = albedo * intensity * N.L; Cycles diffuse = E/pi.
            sun_data.energy = math.pi * sun_strength
            sun_data.angle = 0.0
            sun_object = bpy.data.objects.new('.VLR temporary bake sun', sun_data)
            scene.collection.objects.link(sun_object)
            sun_object.rotation_euler = Vector(direction).to_track_quat('Z','Y').to_euler()
        yield
    finally:
        scene.world = original_world
        if sun_object is not None: bpy.data.objects.remove(sun_object, do_unlink=True)
        if sun_data is not None and sun_data.users == 0: bpy.data.lights.remove(sun_data)
        if world is not None and world.users == 0: bpy.data.worlds.remove(world)
        for ob, value in hidden: ob.hide_render = value
