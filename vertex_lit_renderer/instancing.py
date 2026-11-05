"""GPU instancing for repeated opaque geometry; no evaluated RNA is retained."""
import gpu
import numpy as np

_programs = {}

def clear():
    _programs.clear()

def shader_for(base, vertex, fragment):
    key = id(base)
    if key in _programs:
        return _programs[key][1]
    source = '''
uniform sampler2D uInstanceData;
vec4 vlr_instance(int column) {
    return texelFetch(uInstanceData, ivec2(column, gl_InstanceID), 0);
}
mat4 vlr_instance_model() {
    return mat4(vlr_instance(0), vlr_instance(1), vlr_instance(2), vlr_instance(3));
}
mat3 vlr_instance_normal() {
    return mat3(vlr_instance(4).xyz, vlr_instance(5).xyz, vlr_instance(6).xyz);
}
'''
    vertex = vertex.replace('uniform mat4 uModel;', '#define uModel vlr_instance_model()')
    vertex = vertex.replace('uniform mat3 uNormalMat;', '#define uNormalMat vlr_instance_normal()')
    if 'uniform vec3 uObjId;' in fragment:
        fragment = fragment.replace('uniform vec3 uObjId;',
                                    'flat in vec3 vInstanceObjectId;\n#define uObjId vInstanceObjectId')
        source += '\nflat out vec3 vInstanceObjectId;\n'
        vertex = vertex.replace('void main() {',
                                'void main() {\n vInstanceObjectId = vlr_instance(7).xyz;')
    try:
        shader = gpu.types.GPUShader(source + vertex, fragment)
    except Exception as exc:
        print('[VertexLit] instancing unavailable, using individual draws:', exc)
        shader = None
    _programs[key] = (base, shader)
    return shader

def textures(records):
    """Eight RGBA texels per instance: model columns, normal columns, object ID."""
    chunks = []
    for start in range(0, len(records), 4096):
        part = records[start:start+4096]
        data = np.zeros((len(part), 8, 4), dtype=np.float32)
        # Pack rows in one conversion, avoiding NumPy's costly per-Matrix protocol.
        data[:, :4, :] = np.asarray([tuple(r[2][0])+tuple(r[2][1])+tuple(r[2][2])+tuple(r[2][3])
                                     for r in part], dtype=np.float32).reshape(-1,4,4).transpose(0,2,1)
        data[:, 4:7, :3] = np.asarray([tuple(r[3][0])+tuple(r[3][1])+tuple(r[3][2])
                                       for r in part], dtype=np.float32).reshape(-1,3,3).transpose(0,2,1)
        for i, rec in enumerate(part):
            data[i, 7, :3] = rec[7]
        buf = gpu.types.Buffer('FLOAT', data.size, data.reshape(-1))
        tex = gpu.types.GPUTexture((8, len(part)), format='RGBA32F', data=buf)
        chunks.append([tex, len(part), data])
    return chunks

def update(chunks, changes):
    """Replace affected GPU chunks, retaining packed rows of unchanged instances."""
    dirty = set()
    for index, rec in changes.items():
        ci, row = divmod(index, 4096)
        data = chunks[ci][2]
        data[row, :4, :] = np.asarray(rec[2], dtype=np.float32).T
        data[row, 4:7, :3] = np.asarray(rec[3], dtype=np.float32).T
        dirty.add(ci)
    # Blender 4.4 has no GPUTexture.update; upload cached CPU data into a replacement.
    for ci in dirty:
        chunk = chunks[ci]; data = chunk[2]
        buf = gpu.types.Buffer('FLOAT', data.size, data.reshape(-1))
        chunk[0] = gpu.types.GPUTexture((8, chunk[1]), format='RGBA32F', data=buf)


def draw(batch, shader, chunks):
    if hasattr(batch, 'instanced_batch'):
        batch = batch.instanced_batch()
    for tex, count, _data in chunks:
        shader.uniform_sampler('uInstanceData', tex)
        batch.draw_instanced(shader, instance_count=count)
