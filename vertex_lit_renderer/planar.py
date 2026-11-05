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
