"""Lightmap variants reuse existing geometry/material shaders plus one optional UV buffer."""
import gpu
import numpy as np
from . import shaders


def begin_frame(engine):
    if not hasattr(engine, '_lightmap_geometry'):
        engine._lightmap_geometry = {}
        engine._lightmap_programs = {}
    engine._lightmap_geometry_live = set()
    engine._lightmap_programs_live = set()


def end_frame(engine):
    for cache, live in ((engine._lightmap_geometry, engine._lightmap_geometry_live),
                        (engine._lightmap_programs, engine._lightmap_programs_live)):
        for key in list(cache):
            if key not in live: del cache[key]


def object_for_record(engine, record):
    # A source object's static bake is not valid at a collection/GN instance's location.
    if record[0] != record[1]: return None
    return engine._lightmap_objects.get(record[1])


class _DrawRange:
    def __init__(self, batch, start, count):
        self.batch, self.start, self.count = batch, start, count

    def draw(self, shader):
        self.batch.draw_range(shader, elem_start=self.start, elem_count=self.count)


def prepare(engine, depsgraph, obj, prog, mode, drawable):
    if obj is None: return None
    state = obj.vlr_lightmap
    data = engine._mesh_cache.get(obj.name)
    if not data or 'vbo2' not in data or not hasattr(drawable, 'start'):
        return None
    geometry_key = (id(data['vbo']), state.uv_name, id(getattr(drawable, 'named_uv_vbo', None)))
    geometry = engine._lightmap_geometry.get(geometry_key)
    if geometry is None:
        evaluated = obj.evaluated_get(depsgraph)
        editing = obj.data.is_editmode
        mesh = evaluated.to_mesh() if editing else evaluated.data
        try:
            uv = mesh.uv_layers.get(state.uv_name)
            if uv is None or len(uv.data) != data['n_loops']: return None
            coords = np.empty(len(uv.data) * 2, dtype=np.float32)
            uv.data.foreach_get('uv', coords)
        finally:
            if editing: evaluated.to_mesh_clear()
        fmt = gpu.types.GPUVertFormat()
        fmt.attr_add(id='lightmapUV', comp_type='F32', len=2, fetch_mode='FLOAT')
        vbo = gpu.types.GPUVertBuf(fmt, data['n_loops'])
        vbo.attr_fill(id='lightmapUV', data=coords.reshape(-1, 2))
        batch = gpu.types.GPUBatch(type='TRIS', buf=data['vbo'], elem=data['ibo'])
        batch.vertbuf_add(data['vbo2']); batch.vertbuf_add(vbo)
        if hasattr(drawable, 'named_uv_vbo'): batch.vertbuf_add(drawable.named_uv_vbo)
        geometry = engine._lightmap_geometry[geometry_key] = (batch, vbo)
    engine._lightmap_geometry_live.add(geometry_key)
    fragment = prog['frag'] if prog is not None else (shaders.WORKBENCH_FRAG if mode == 'WORKBENCH' else shaders.PHONG_FRAG)
    keep_live = obj.vlr_lightmap_settings.keep_live_lighting
    program_key = (fragment, keep_live)
    shader = engine._lightmap_programs.get(program_key)
    if shader is None:
        vertex = 'in vec2 lightmapUV;\nout vec2 vLightmapUV;\n' + (prog['vert'] if prog is not None else shaders.PHONG_VERT)
        vertex = vertex.replace('void main() {', 'void main() {\n    vLightmapUV = lightmapUV;')
        frag = 'uniform float uLightmapIntensity;\nuniform sampler2D uLightmap;\nin vec2 vLightmapUV;\n' + fragment
        if keep_live:
            # Add irradiance after the live-light clamp. Preserve the separate sun
            # output so contact shadows only remove sunlight, never baked bounce.
            frag = frag.replace('outColor = vec4(lit *',
                                'outColor = vec4((lit + (texture(uLightmap, vLightmapUV).rgb * uLightmapIntensity)) *')
        else:
            frag = frag.replace('vlr_light(vWpos, N)', '(texture(uLightmap, vLightmapUV).rgb * uLightmapIntensity)')
            frag = frag.replace('uKeyCol * ndl + vec3(uAmbient)', '(texture(uLightmap, vLightmapUV).rgb * uLightmapIntensity)')
            # Lightmaps are linear HDR lighting, not restricted to the live-light cap.
            frag = frag.replace('clamp(light, 0.0, 12.0)', 'light')
            frag = frag.replace('vlr_write_aux(N);', 'vlrSunOutput = vec3(0.0); vlr_write_aux(N);')
        if prog is not None and 'vlrReliefScreenOffset' in fragment:
            # Map the hit into the separately packed lightmap UV basis. No extra ray march.
            # Use original derivatives for filtering, not derivatives of the displaced hit.
            lookup = ('textureGrad(uLightmap, vLightmapUV + '
                      'dFdx(vLightmapUV) * vlrReliefScreenOffset.x + '
                      'dFdy(vLightmapUV) * vlrReliefScreenOffset.y, '
                      'dFdx(vLightmapUV), dFdy(vLightmapUV))')
            frag = frag.replace('texture(uLightmap, vLightmapUV)', lookup)
        shader = engine._lightmap_programs[program_key] = gpu.types.GPUShader(vertex, frag)
    engine._lightmap_programs_live.add(program_key)
    from .engine import _get_gpu_tex
    texture = _get_gpu_tex(state.image)
    if texture is None: return None
    return shader, _DrawRange(geometry[0], drawable.start, drawable.count), texture
