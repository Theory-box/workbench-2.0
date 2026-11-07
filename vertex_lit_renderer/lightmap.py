"""Per-object Cycles diffuse lightmaps; no changes to the post-effects pipeline."""
import bpy
import math


class VLRLightmapSettings(bpy.types.PropertyGroup):
    lighting_source: bpy.props.EnumProperty(name='Lighting', items=[
        ('WORKBENCH', 'Cycles — Workbench Lighting', 'Use Workbench Sun and Sky/Ground; ignore existing lights/world, retain emission'),
        ('SCENE', 'Cycles — Scene Lighting', 'Use the existing scene lights and world')], default='SCENE')
    resolution: bpy.props.EnumProperty(name='Resolution', items=[(str(n), str(n), '') for n in (128, 256, 512, 1024, 2048, 4096)], default='1024')
    samples: bpy.props.IntProperty(name='Samples', default=64, min=1, max=4096)


class VLRLightmapState(bpy.types.PropertyGroup):
    image: bpy.props.PointerProperty(type=bpy.types.Image)
    uv_name: bpy.props.StringProperty()
    status: bpy.props.StringProperty(default='Not baked')


def _cycles_bake(uv_name, margin):
    return bpy.ops.object.bake(type='DIFFUSE', pass_filter={'DIRECT', 'INDIRECT'},
                              target='IMAGE_TEXTURES', save_mode='INTERNAL',
                              uv_layer=uv_name, use_selected_to_active=False,
                              use_clear=True, margin=margin, margin_type='EXTEND')


def _temporary_material(original):
    material = original.copy() if original is not None else bpy.data.materials.new('Lightmap bake material')
    if not material.use_nodes:
        color = tuple(material.diffuse_color)
        material.use_nodes = True
        material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = color
    return material


def bake_selected(context):
    """Stage UVs/images on private meshes; publish only after the entire bake succeeds."""
    if context.mode != 'OBJECT':
        raise ValueError('Bake lightmaps in Object Mode')
    objects = [ob for ob in context.selected_objects if ob.type == 'MESH']
    if not objects:
        raise ValueError('Select at least one mesh object')
    if any(ob.library or ob.data.library for ob in objects):
        raise ValueError('Make linked library objects local before baking')
    # A second UV map on the base mesh cannot uniquely unwrap duplicated/generated
    # modifier surfaces. Do not silently bake overlapping lightmap charts.
    topology_modifiers = {'ARRAY', 'BEVEL', 'BOOLEAN', 'BUILD', 'DECIMATE', 'EDGE_SPLIT',
                          'MASK', 'MIRROR', 'MULTIRES', 'NODES', 'REMESH', 'SCREW', 'SKIN',
                          'SOLIDIFY', 'SUBSURF', 'TRIANGULATE', 'WELD', 'WIREFRAME'}
    depsgraph = context.evaluated_depsgraph_get()
    for ob in objects:
        if not ob.data.polygons:
            raise ValueError(ob.name + ': mesh has no faces')
        if any(mod.type in topology_modifiers and (mod.show_viewport or mod.show_render) for mod in ob.modifiers):
            raise ValueError(ob.name + ': apply topology-changing modifiers before lightmap baking')
        evaluated = ob.evaluated_get(depsgraph).data
        if len(evaluated.loops) != len(ob.data.loops) or len(evaluated.vertices) != len(ob.data.vertices):
            raise ValueError(ob.name + ': apply topology-changing modifiers before lightmap baking')
        if any(mod.show_render != mod.show_viewport for mod in ob.modifiers):
            raise ValueError(ob.name + ': modifier viewport/render visibility must match for baking')
    scene = context.scene
    resolution = int(scene.vlr_lightmap_settings.resolution)
    margin = max(2, min(16, resolution // 128))
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    engine, samples = scene.render.engine, scene.cycles.samples
    # bpy.ops.object.bake also writes Render Bake settings: restore every changed field.
    saved_bake = {}
    for prop in scene.render.bake.bl_rna.properties:
        if prop.is_readonly or prop.identifier == 'rna_type': continue
        value = getattr(scene.render.bake, prop.identifier)
        if getattr(prop, 'is_array', False): value = tuple(value)
        elif isinstance(value, set): value = set(value)
        saved_bake[prop.identifier] = value
    saved_type = scene.cycles.bake_type
    views = [area.spaces.active for window in context.window_manager.windows for area in window.screen.areas
             if area.type == 'VIEW_3D' and area.spaces.active.shading.type == 'RENDERED']
    staged, temporary_materials = [], []
    published = False
    # One common, collision-free name lets a single Cycles call target all meshes.
    uv_name = 'VLR_Lightmap'
    suffix = 1
    while any(uv_name in ob.data.uv_layers and ob.vlr_lightmap.uv_name != uv_name for ob in objects):
        uv_name = 'VLR_Lightmap_' + str(suffix); suffix += 1
    try:
        for space in views: space.shading.type = 'SOLID'
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = scene.vlr_lightmap_settings.samples
        for ob in objects:
            original = ob.data
            mesh = original.copy()
            selection = [(collection, [element.select for element in collection]) for collection in (mesh.vertices, mesh.edges, mesh.polygons)]
            hidden = [(collection, [element.hide for element in collection]) for collection in (mesh.vertices, mesh.edges, mesh.polygons)]
            record = {'hidden': hidden, 'selection': selection, 'object': ob, 'original': original, 'mesh': mesh,
                      'slots': [(slot.link, slot.material) for slot in ob.material_slots], 'image': None}
            staged.append(record)
            ob.data = mesh
            # Preserve both the editable UV selection and the UV set used by textures.
            active_uv = mesh.uv_layers.active.name if mesh.uv_layers.active else None
            render_uv = next((uv.name for uv in mesh.uv_layers if uv.active_render), None)
            if not mesh.uv_layers:
                mesh.uv_layers.new(name='UVMap')
                active_uv = render_uv = mesh.uv_layers[0].name
            previous_uv = ob.vlr_lightmap.uv_name
            if previous_uv and previous_uv in mesh.uv_layers:
                mesh.uv_layers.remove(mesh.uv_layers[previous_uv])
            layer = mesh.uv_layers.new(name=uv_name)
            mesh.uv_layers.active = layer
            bpy.ops.object.select_all(action='DESELECT')
            ob.select_set(True); context.view_layer.objects.active = ob
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.reveal(select=True)
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0)
            bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=(margin * 2 + 2) / resolution)
            bpy.ops.object.mode_set(mode='OBJECT')
            for collection, flags in selection:
                for element, flag in zip(collection, flags): element.select = flag
            mesh.uv_layers.active = mesh.uv_layers.get(active_uv) or mesh.uv_layers[0]
            if render_uv and render_uv in mesh.uv_layers: mesh.uv_layers[render_uv].active_render = True
            image = bpy.data.images.new(ob.name + '_Lightmap', width=resolution, height=resolution,
                                        alpha=False, float_buffer=True)
            record['image'] = image
            image['vlr_lightmap_owned'] = True
            image.colorspace_settings.name = 'Non-Color'
            if not mesh.materials: mesh.materials.append(None)
            copies = {}
            for slot in ob.material_slots:
                source = slot.material
                key = source.as_pointer() if source is not None else 0
                material = copies.get(key)
                if material is None:
                    material = _temporary_material(source)
                    temporary_materials.append(material); copies[key] = material
                    target = material.node_tree.nodes.new('ShaderNodeTexImage')
                    target.image = image
                    for node in material.node_tree.nodes: node.select = False
                    target.select = True; material.node_tree.nodes.active = target
                slot.link = 'DATA'; slot.material = material
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects: ob.select_set(True)
        context.view_layer.objects.active = objects[0]
        from .bake_lighting import lighting_source
        with lighting_source(scene, scene.vlr_lightmap_settings.lighting_source):
            context.view_layer.update()
            if _cycles_bake(uv_name, margin) != {'FINISHED'}:
                raise RuntimeError('Cycles lightmap bake was cancelled')
        for record in staged:
            record['image'].pack()
        for record in staged:
            ob = record['object']; state = ob.vlr_lightmap
            old_image = state.image
            state.uv_name = uv_name; state.image = record['image']
            state.status = 'Baked: ' + str(resolution) + ' px, ' + str(scene.vlr_lightmap_settings.samples) + ' samples'
            if old_image is not None and old_image.get('vlr_lightmap_owned') and old_image.users == 0:
                from .engine import _invalidate_tex
                _invalidate_tex(old_image.name); bpy.data.images.remove(old_image)
        published = True
    finally:
        if context.object is not None and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for record in staged:
            ob, mesh, original = record['object'], record['mesh'], record['original']
            if not published: ob.data = original
            else:
                for collection, flags in record['hidden']:
                    for element, flag in zip(collection, flags): element.hide = flag
                for collection, flags in record['selection']:
                    for element, flag in zip(collection, flags): element.select = flag
                mesh.materials.clear()
                for material in original.materials: mesh.materials.append(material)
            for slot, (link, material) in zip(ob.material_slots, record['slots']):
                slot.link = link; slot.material = material
            if not published:
                if mesh.users == 0: bpy.data.meshes.remove(mesh)
                if record['image'] is not None: bpy.data.images.remove(record['image'])
            if published:
                mesh['vlr_lightmap_staging_mesh'] = True
                mesh.update(); ob.update_tag(refresh={'DATA'})
        if published:
            # Do this after every slot has been restored: multiple selected
            # objects may have shared the same original mesh.
            originals = {record['original'] for record in staged}
            for original in originals:
                if original.users == 0 and not original.use_fake_user:
                    bpy.data.meshes.remove(original)
        for material in temporary_materials:
            if material.users == 0: bpy.data.materials.remove(material)
        scene.cycles.samples = samples
        scene.cycles.bake_type = saved_type
        for name, value in saved_bake.items(): setattr(scene.render.bake, name, value)
        scene.render.engine = engine
        bpy.ops.object.select_all(action='DESELECT')
        for ob in selected: ob.select_set(True)
        context.view_layer.objects.active = active
        for space in views: space.shading.type = 'RENDERED'
        for window in context.window_manager.windows:
            for area in window.screen.areas: area.tag_redraw()
    return len(objects)


class VLR_OT_lightmap_bake(bpy.types.Operator):
    bl_idname = 'vertex_lit.lightmap_bake'
    bl_label = 'Bake Selected'
    bl_description = 'Smart unwrap a separate UV map and bake Cycles direct and indirect diffuse lighting'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(ob.type == 'MESH' for ob in context.selected_objects)

    def execute(self, context):
        try:
            count = bake_selected(context)
        except ValueError as exc:
            self.report({'WARNING'}, str(exc)); return {'CANCELLED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        self.report({'INFO'}, 'Baked lightmaps for ' + str(count) + ' object(s)')
        return {'FINISHED'}


class VLR_OT_lightmap_clear(bpy.types.Operator):
    bl_idname = 'vertex_lit.lightmap_clear'
    bl_label = 'Clear Bake Selected'
    bl_description = 'Remove baked lighting from selected objects; preserve materials and UV maps'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(ob.type == 'MESH' and ob.vlr_lightmap.image for ob in context.selected_objects)

    def execute(self, context):
        objects = [ob for ob in context.selected_objects if ob.type == 'MESH' and ob.vlr_lightmap.image]
        if any(ob.library for ob in objects):
            self.report({'WARNING'}, 'Make linked library objects local before clearing lightmaps')
            return {'CANCELLED'}
        images = set()
        for ob in objects:
            images.add(ob.vlr_lightmap.image)
            ob.vlr_lightmap.image = None
            # Retain the owned UV name so a future bake replaces it, rather than
            # accumulating unused UV sets. Do not alter shared mesh data here.
            ob.vlr_lightmap.status = 'Not baked'
            ob.update_tag(refresh={'DATA'})
        from .engine import _invalidate_tex
        for image in images:
            if image.get('vlr_lightmap_owned') and image.users == 0:
                _invalidate_tex(image.name)
                bpy.data.images.remove(image)
        for window in context.window_manager.windows:
            for area in window.screen.areas: area.tag_redraw()
        self.report({'INFO'}, 'Cleared lightmaps for ' + str(len(objects)) + ' object(s)')
        return {'FINISHED'}


class VLR_PT_lightmap(bpy.types.Panel):
    bl_label = 'Cycles Lightmap Bake'
    bl_idname = 'VLR_PT_lightmap'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Workbench 2.0'

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine in {'VERTEX_LIT', 'CYCLES'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.vlr_lightmap_settings
        layout.prop(settings, 'lighting_source')
        if settings.lighting_source == 'WORKBENCH':
            layout.label(text='Sun + Sky/Ground; emission retained')
            layout.label(text='Key Light excluded')
        layout.prop(settings, 'resolution'); layout.prop(settings, 'samples')
        layout.operator('vertex_lit.lightmap_bake')
        layout.operator('vertex_lit.lightmap_clear')
        ob = context.active_object
        if ob is not None and ob.type == 'MESH': layout.label(text=ob.vlr_lightmap.status)


_CLASSES = (VLRLightmapSettings, VLRLightmapState, VLR_OT_lightmap_bake, VLR_OT_lightmap_clear, VLR_PT_lightmap)


def register():
    for cls in _CLASSES: bpy.utils.register_class(cls)
    bpy.types.Scene.vlr_lightmap_settings = bpy.props.PointerProperty(type=VLRLightmapSettings)
    bpy.types.Object.vlr_lightmap = bpy.props.PointerProperty(type=VLRLightmapState)


def unregister():
    del bpy.types.Object.vlr_lightmap
    del bpy.types.Scene.vlr_lightmap_settings
    for cls in reversed(_CLASSES): bpy.utils.unregister_class(cls)
