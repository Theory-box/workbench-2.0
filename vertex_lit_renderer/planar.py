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
    state.image = None
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
    bpy.utils.register_class(VLRPlanarSettings)
    bpy.types.Object.vlr_planar = PointerProperty(type=VLRPlanarSettings)


def unregister():
    del bpy.types.Object.vlr_planar
    bpy.utils.unregister_class(VLRPlanarSettings)


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
