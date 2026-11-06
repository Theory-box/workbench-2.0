"""Lazy per-material named UV buffers; reuse existing positions and triangle indices."""
import bpy
import gpu
import numpy as np

class Draw:
    def __init__(self, batch, vbo, start, count):
        self.batch, self.named_uv_vbo, self.start, self.count = batch, vbo, start, count
    def draw(self, shader):
        self.batch.draw_range(shader, elem_start=self.start, elem_count=self.count)

def prepare(engine, depsgraph, name, prog, drawable, draw_key=None):
    names = tuple(prog.get('uv_maps', ())) if prog else ()
    if not names or not hasattr(drawable, 'start'): return drawable
    data = engine._mesh_cache.get(draw_key or name)
    obj = bpy.data.objects.get(name)
    if not data or obj is None or 'vbo2' not in data: return drawable
    key = (id(data['vbo']), obj.name, names)
    engine._named_uv_live.add(key)
    cached = engine._named_uv_cache.get(key)
    if cached is None:
        evaluated = obj.evaluated_get(depsgraph)
        editing = obj.data.is_editmode
        mesh = evaluated.to_mesh() if editing else evaluated.data
        try:
            count = data['n_loops']
            fmt = gpu.types.GPUVertFormat()
            for i in range(len(names)): fmt.attr_add(id='namedUV'+str(i), comp_type='F32', len=2, fetch_mode='FLOAT')
            vbo = gpu.types.GPUVertBuf(fmt, count)
            for i, uv_name in enumerate(names):
                coords = np.zeros(count*2, dtype=np.float32)
                uv = mesh.uv_layers.get(uv_name)
                if uv is not None and len(uv.data)==count: uv.data.foreach_get('uv', coords)
                vbo.attr_fill(id='namedUV'+str(i), data=coords.reshape(-1,2))
        finally:
            if editing: evaluated.to_mesh_clear()
        batch = gpu.types.GPUBatch(type='TRIS', buf=data['vbo'], elem=data['ibo'])
        batch.vertbuf_add(data['vbo2']); batch.vertbuf_add(vbo)
        cached = engine._named_uv_cache[key] = (batch,vbo)
    return Draw(*cached, drawable.start, drawable.count)
