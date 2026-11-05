"""Planar reflection math prototype. Not registered or exposed in the UI yet."""
from mathutils import Matrix, Vector


def reflection_matrix(point, normal):
    """Reflect world positions across a plane; no scene duplication."""
    n = Vector(normal)
    if n.length_squared < 1e-16:
        raise ValueError('Reflection plane needs a nonzero normal')
    n.normalize()
    d = n.dot(Vector(point))
    result = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            result[i][j] -= 2.0 * n[i] * n[j]
        result[i][3] = 2.0 * d * n[i]
    return result


def plane_from_faces(mesh, matrix_world, face_indices, tolerance=1e-5):
    """Validate explicitly selected coplanar faces in world space.

    Uses transformed vertices, including nonuniform/mirrored object transforms.
    Returns point and unit normal. Does not edit mesh or material slots.
    """
    indices = list(face_indices)
    if not indices:
        raise ValueError('Select the reflective face or coplanar faces')
    points = []
    normal = None
    origin = None
    for index in indices:
        vertices = [matrix_world @ mesh.vertices[i].co for i in mesh.polygons[index].vertices]
        points.extend(vertices)
        if origin is None:
            origin = vertices[0]
        for i in range(1, len(vertices)-1):
            cross = (vertices[i]-vertices[0]).cross(vertices[i+1]-vertices[0])
            if cross.length_squared > 1e-16 and normal is None:
                normal = cross.normalized()
    if normal is None:
        raise ValueError('Selected faces have no usable area')
    if any(abs((p-origin).dot(normal)) > tolerance for p in points):
        raise ValueError('Selected faces must lie on one plane')
    return origin, normal

# Object-owned metadata deliberately avoids mesh attributes: linked mesh objects
# and shared materials must not inherit another object's reflection assignment.
def topology_signature(mesh):
    import hashlib
    import numpy as np
    loops = np.empty(len(mesh.loops), dtype=np.int32)
    counts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loops)
    mesh.polygons.foreach_get('loop_total', counts)
    return hashlib.sha256(loops.tobytes() + counts.tobytes()).hexdigest()


def configure_faces(obj, face_indices, camera):
    """Validate before replacing metadata; existing bake survives invalid input."""
    if obj.type != 'MESH':
        raise ValueError('Select a mesh object')
    if camera is None or camera.type != 'CAMERA':
        raise ValueError('Choose a scene camera')
    indices = sorted(set(int(i) for i in face_indices))
    point, normal = plane_from_faces(obj.data, obj.matrix_world, indices)
    state = obj.vlr_planar
    state.faces = ','.join(map(str, indices))
    state.topology = topology_signature(obj.data)
    state.camera = camera
    state.point = point
    state.normal = normal
    state.status = 'Needs bake'
    return point, normal


def selected_faces(obj):
    if obj.mode == 'EDIT':
        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        return [i for i, face in enumerate(bm.faces) if face.select]
    return [face.index for face in obj.data.polygons if face.select]


def configured_faces(obj):
    state = obj.vlr_planar
    if not state.faces:
        raise ValueError('No reflection faces configured')
    if topology_signature(obj.data) != state.topology:
        raise ValueError('Mesh topology changed; select the reflection faces again')
    return [int(i) for i in state.faces.split(',')]


def clear_reflection(obj):
    """Detach only this object's bake; never delete possibly shared image data."""
    state = obj.vlr_planar
    old = state.image
    state.image = None
    if old is not None and old.get('vlr_planar_owned',False) and old.users == 0:
        bpy.data.images.remove(old)
    state.camera = None
    state.faces = ''
    state.topology = ''
    state.status = 'Not configured'
    obj.update_tag()


import bpy
from bpy.props import StringProperty, PointerProperty, FloatVectorProperty, IntProperty


class VLRPlanarSettings(bpy.types.PropertyGroup):
    faces: StringProperty()
    topology: StringProperty()
    camera: PointerProperty(type=bpy.types.Object)
    image: PointerProperty(type=bpy.types.Image)
    point: FloatVectorProperty(size=3)
    normal: FloatVectorProperty(size=3, default=(0, 0, 1))
    projection: FloatVectorProperty(size=16)
    resolution: IntProperty(name='Resolution', default=1024, min=64, max=4096)
    status: StringProperty(default='Not configured')


def register():
    for cls in (VLRPlanarSettings,VLR_OT_planar_bake,VLR_OT_planar_clear,VLR_PT_planar):
        bpy.utils.register_class(cls)
    bpy.types.Object.vlr_planar = PointerProperty(type=VLRPlanarSettings)


def unregister():
    del bpy.types.Object.vlr_planar
    _PENDING.clear()
    for cls in (VLR_PT_planar,VLR_OT_planar_clear,VLR_OT_planar_bake,VLRPlanarSettings):
        bpy.utils.unregister_class(cls)


def reflected_camera(camera_world, projection, point, normal, clip_bias=0.001):
    """Return reflected view and oblique projection retaining the viewer's side.

    OpenGL clip convention: -w <= z <= w. Works with perspective and
    orthographic projections by deriving the opposite clip corner via inverse P.
    """
    point, n = Vector(point), Vector(normal).normalized()
    if n.length_squared < 1e-12:
        raise ValueError('Invalid plane normal')
    distance = (camera_world.translation-point).dot(n)
    if abs(distance) <= clip_bias:
        raise ValueError('Camera lies on the reflection plane')
    if distance < 0:
        n.negate()
    view = (reflection_matrix(point, n) @ camera_world).inverted()
    # Positive plane half-space is the original viewer's side.
    world_plane = Vector((*n, -n.dot(point)-clip_bias))
    camera_plane = view.inverted().transposed() @ world_plane
    def sign(x): return 1.0 if x >= 0 else -1.0
    corner = projection.inverted() @ Vector((sign(camera_plane.x), sign(camera_plane.y), 1, 1))
    denominator = camera_plane.dot(corner)
    if denominator <= 1e-8:
        raise ValueError('Reflection plane is outside the camera capture range')
    clipped = projection.copy()
    clipped[2] = camera_plane * (2.0/denominator) - projection[3]
    return view, clipped


def cropped_projection(obj, faces, camera_vp, reflection_vp, resolution, aspect):
    """Clip face polygons to the camera frustum before deriving capture bounds."""
    points=[]
    for index in faces:
        poly=[camera_vp @ (obj.matrix_world @ obj.data.vertices[i].co).to_4d()
              for i in obj.data.polygons[index].vertices]
        for axis,sign in ((0,1),(0,-1),(1,1),(1,-1),(2,1),(2,-1)):
            result=[]
            for a,b in zip(poly,poly[1:]+poly[:1]):
                da=a.w+sign*a[axis];db=b.w+sign*b[axis]
                if da>=0:result.append(a)
                if (da>=0)!=(db>=0):result.append(a+(b-a)*(da/(da-db)))
            poly=result
            if not poly:break
        points.extend((p.x/p.w,p.y/p.w) for p in poly if p.w>1e-8)
    if not points:raise ValueError('Selected reflection faces are outside the bake camera view')
    lo=[min(p[i] for p in points) for i in (0,1)]
    hi=[max(p[i] for p in points) for i in (0,1)]
    for i in (0,1):
        span=hi[i]-lo[i]
        if span<1e-6:raise ValueError('Reflection faces are edge-on to the camera')
        padding=max(span*.08,4.0/resolution)
        lo[i]-=padding;hi[i]+=padding
    spans=[hi[i]-lo[i] for i in (0,1)]
    crop=Matrix.Identity(4)
    for i in (0,1):
        crop[i][i]=2.0/spans[i];crop[i][3]=-(hi[i]+lo[i])/spans[i]
    ratio=aspect*spans[0]/spans[1]
    width,height=(resolution,max(1,round(resolution/ratio))) if ratio>=1 else (max(1,round(resolution*ratio)),resolution)
    return crop@reflection_vp,width,height


def capture(engine, depsgraph, obj):
    """Capture from an owning renderer's GPU context, reusing its scene batches.

    Does not create a Blender scene, camera object, or second geometry cache.
    Image publication is separate so a failed bake cannot replace a valid image.
    """
    import gpu
    import numpy as np
    from . import engine as render
    state = obj.vlr_planar
    faces = configured_faces(obj)
    point, normal = plane_from_faces(obj.data, obj.matrix_world, faces)
    scene = depsgraph.scene
    camera = state.camera
    if camera is None:
        raise ValueError('The bake camera was removed')
    camera = camera.evaluated_get(depsgraph)
    settings = scene.vertex_lit
    aspect = (scene.render.resolution_x * scene.render.pixel_aspect_x /
              max(1, scene.render.resolution_y * scene.render.pixel_aspect_y))
    projection = camera.calc_matrix_camera(depsgraph,
        x=scene.render.resolution_x,y=scene.render.resolution_y,
        scale_x=scene.render.pixel_aspect_x,scale_y=scene.render.pixel_aspect_y)
    view, clipped = reflected_camera(camera.matrix_world, projection, point, normal)
    vp,width,height = cropped_projection(obj,faces,projection@camera.matrix_world.inverted(),
                                        clipped@view,state.resolution,aspect)
    names = ('_strict_capture','_final_render','_cull','_cam_pos','_view_mat3','_aux_active',
             '_film_transparent','_sun','_shadow_texel','_shadow_dirty','_shadow_tex_cache')
    absent = object()
    saved = {name:getattr(engine,name,absent) for name in names}
    viewport = gpu.state.viewport_get()
    depth = gpu.state.depth_test_get(); mask = gpu.state.depth_mask_get()
    blend = gpu.state.blend_get()
    target = None
    try:
        engine._strict_capture = True
        engine._final_render = True  # finish material compilation for this capture
        engine._cull = 'FRONT' if settings.backface_cull else 'NONE'
        engine._cam_pos = tuple(view.inverted().translation)
        engine._view_mat3 = view.to_3x3()
        engine._aux_active = False; engine._film_transparent = False
        engine._sun = render._compute_sun(settings)
        sky, ground = tuple(settings.sky_color), tuple(settings.ground_color)
        key = Vector((.25,.35,.90)).normalized()
        studio = (tuple(camera.matrix_world.to_quaternion() @ key), (1,1,1), settings.key_intensity)
        do_shadow = settings.use_shadows and engine._sun[2] > 0
        light_matrix = Matrix.Identity(4); shadow = engine._dummy_depth
        engine._shadow_texel = 0
        if do_shadow:
            light_matrix, engine._shadow_texel = render._build_light_space_fit(
                engine._sun[0], vp, engine._cam_pos, settings.shadow_distance,
                int(settings.shadow_resolution), engine._bounds_cache[1])
            shadow_target = render._ShadowMap(int(settings.shadow_resolution))
            engine._shadow_dirty = True
            # Shadow winding is independent of the reflected viewing camera.
            engine._cull = 'BACK' if settings.backface_cull else 'NONE'
            shadow = engine._shadow_pass(light_matrix, int(settings.shadow_resolution), depsgraph,
                                         shadow_map=shadow_target)
            engine._cull = 'FRONT' if settings.backface_cull else 'NONE'
        target = gpu.types.GPUOffScreen(width, height, format='RGBA16F')
        with target.bind():
            gpu.state.viewport_set(0,0,width,height)
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=(0,0,0,1),depth=1)
            engine._draw_batches(depsgraph,settings,vp,studio,light_matrix,sky,ground,0,
                do_shadow,settings.shadow_bias,settings.shadow_softness,shadow,
                engine._lights_cache,'PIXEL')
            buf = fb.read_color(0,0,width,height,4,0,'FLOAT')
            buf.dimensions=width*height*4
            pixels=np.array(buf,dtype=np.float32).reshape(height,width,4)
        return pixels, vp
    finally:
        if target is not None: target.free()
        for name,value in saved.items():
            if value is absent:
                if hasattr(engine,name): delattr(engine,name)
            else: setattr(engine,name,value)
        gpu.state.viewport_set(*viewport)
        gpu.state.depth_test_set(depth); gpu.state.depth_mask_set(mask); gpu.state.blend_set(blend)
        gpu.state.face_culling_set(getattr(engine,'_cull','NONE'))

_PENDING = []


def publish_capture(obj, pixels, projection):
    """Run outside the draw callback: Blender forbids ID writes during drawing."""
    h,w=pixels.shape[:2]
    image=bpy.data.images.new(obj.name+'_PlanarReflection',width=w,height=h,alpha=True,float_buffer=True)
    try:
        image['vlr_planar_owned']=True
        image.colorspace_settings.name='Non-Color'
        image.pixels.foreach_set(pixels.reshape(-1));image.update();image.pack()
    except Exception:
        bpy.data.images.remove(image);raise
    obj.vlr_planar.projection=tuple(x for row in projection for x in row)
    old=obj.vlr_planar.image
    obj.vlr_planar.image=image
    if old is not None and old.get('vlr_planar_owned',False) and old.users == 0:
        bpy.data.images.remove(old)
    obj.vlr_planar.status='Baked for '+obj.vlr_planar.camera.name+'; rebake after scene changes'


def process_pending(engine, context, depsgraph):
    if not _PENDING or getattr(engine,'_geo_pending',False) or getattr(engine,'_mat_pending',False):return
    obj = _PENDING.pop(0)
    pixels=projection=None;error=None
    try:
        if obj.name not in context.scene.objects:return
        pixels, projection = capture(engine,depsgraph,obj)
    except Exception as exc:
        error=str(exc)
    # A clear/reconfigure between capture and publication must cancel publication.
    token=(obj.vlr_planar.faces,obj.vlr_planar.topology,obj.vlr_planar.camera)
    def finish():
        try:
            state=obj.vlr_planar
            if token!=(state.faces,state.topology,state.camera) or not state.faces:return
            if error is not None:raise RuntimeError(error)
            publish_capture(obj,pixels,projection)
        except ReferenceError:return
        except Exception as exc:
            obj.vlr_planar.status='Bake failed: '+str(exc)
            print('[VertexLit] planar bake failed:',exc)
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:area.tag_redraw()
    bpy.app.timers.register(finish,first_interval=0.01)


class VLR_OT_planar_bake(bpy.types.Operator):
    bl_idname='vertex_lit.planar_bake'
    bl_label='Bake / Rebake Planar Reflection'
    bl_description='Bake selected coplanar faces for the scene camera; in Object Mode rebake the configured faces'
    def execute(self,context):
        obj=context.active_object
        try:
            if obj is None or obj.type!='MESH':raise ValueError('Select a mesh object')
            if context.scene.render.engine!='VERTEX_LIT':raise ValueError('Choose Workbench 2.0 as the render engine')
            if not any(a.type=='VIEW_3D' and a.spaces.active.shading.type=='RENDERED' for a in context.screen.areas):
                raise ValueError('Open a Rendered viewport before baking')
            if obj.mode=='EDIT':obj.update_from_editmode()
            faces=selected_faces(obj) if obj.mode=='EDIT' or not obj.vlr_planar.faces else configured_faces(obj)
            # Validate material support before changing assignment or queuing work.
            from . import node_transpiler
            for index in faces:
                slot=obj.data.polygons[index].material_index
                mat=obj.material_slots[slot].material if slot<len(obj.material_slots) else None
                node_transpiler.transpile_reflection_properties(mat)
                if node_transpiler.transpile_material(mat).has_alpha:
                    raise ValueError("This bake currently requires an opaque reflector material")
            if any(m.show_viewport for m in obj.modifiers):
                raise ValueError('Apply or disable modifiers on the reflector before baking')
            configure_faces(obj,faces,context.scene.camera)
            if obj not in _PENDING:_PENDING.append(obj)
            obj.vlr_planar.status='Queued: waiting for rendered viewport'
            for a in context.screen.areas:a.tag_redraw()
        except Exception as exc:
            self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class VLR_OT_planar_clear(bpy.types.Operator):
    bl_idname='vertex_lit.planar_clear';bl_label='Clear Reflections'
    bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        obj=context.active_object
        if obj is None:return {'CANCELLED'}
        if obj in _PENDING:_PENDING.remove(obj)
        clear_reflection(obj)
        for a in context.screen.areas:a.tag_redraw()
        return {'FINISHED'}


class VLR_PT_planar(bpy.types.Panel):
    bl_label='Planar Reflection Bake';bl_idname='VLR_PT_planar'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Workbench 2.0'
    @classmethod
    def poll(cls,context):
        return context.active_object is not None and context.active_object.type=='MESH' and context.scene.render.engine=='VERTEX_LIT'
    def draw(self,context):
        layout=self.layout;state=context.active_object.vlr_planar
        layout.label(text='Select coplanar faces in Edit Mode')
        layout.label(text='Uses scene camera and existing material')
        layout.prop(state,'resolution')
        layout.operator('vertex_lit.planar_bake')
        layout.operator('vertex_lit.planar_clear')
        layout.label(text=state.status)
        layout.label(text='Fixed view; rebake after scene changes')
