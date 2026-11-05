"""Selected-face planar compositing using the renderer's existing vertex buffers."""
import gpu
from mathutils import Matrix
from . import shaders, node_transpiler, planar

_FRAGMENT = '''
in vec2 vUV;
in vec4 vColor;
in vec3 vWpos;
in vec3 vNrm;
in vec3 vGenerated;
in vec3 vObjPos;
uniform sampler2D uReflection;
uniform mat4 uReflectionProjection;
uniform vec3 uViewer;
layout(location=0) out vec4 fragColor;
layout(location=1) out vec4 keepNormal;
layout(location=2) out vec4 keepId;
'''
_MAIN = '''
void main(){
 keepNormal=vec4(0);keepId=vec4(0);
 vec4 projected=uReflectionProjection*vec4(vWpos,1.0);
 if(projected.w<=0.0)discard;
 vec2 uv=projected.xy/projected.w*.5+.5;
 if(any(lessThan(uv,vec2(0)))||any(greaterThan(uv,vec2(1))))discard;
 vec4 properties=computeReflectionProperties(vUV);
 float rough=properties.x;
 vec3 reflected=vec3(0);
 // Finite spatial filter: a practical glossy approximation, not ray-traced roughness.
 float radius=rough*rough*.06;
 for(int i=0;i<16;i++){
  float angle=float(i)*2.39996323;
  vec2 offset=vec2(cos(angle),sin(angle))*sqrt((float(i)+.5)/16.0)*radius;
  reflected+=texture(uReflection,clamp(uv+offset,vec2(.001),vec2(.999))).rgb;
 }
 reflected/=16.0;
 float cosine=abs(dot(normalize(vNrm),normalize(uViewer-vWpos)));
 float f0=pow((properties.z-1.0)/(properties.z+1.0),2.0)*properties.w*2.0;
 float weight=mix(f0+(1.0-f0)*pow(1.0-cosine,5.0),1.0,properties.y);
 fragColor=vec4(reflected,clamp(weight,0.0,1.0));
}
'''


def draw(engine,depsgraph,view_projection):
    if getattr(engine,'_strict_capture',False):return
    cache=getattr(engine,'_planar_overlay_cache',None)
    if cache is None:cache=engine._planar_overlay_cache={}
    live=set()
    old_depth=gpu.state.depth_test_get();old_mask=gpu.state.depth_mask_get();old_blend=gpu.state.blend_get()
    try:
        gpu.state.depth_test_set('LESS_EQUAL');gpu.state.depth_mask_set(False)
        gpu.state.blend_set('ALPHA');gpu.state.face_culling_set('NONE')
        for obj in depsgraph.scene.objects:
            state=getattr(obj,'vlr_planar',None)
            if obj.type!='MESH' or state is None or state.image is None:continue
            if obj.name not in getattr(engine,'_normal_records',{}):continue
            data=engine._mesh_cache.get(obj.name)
            if not data or 'vbo2' not in data:continue
            try:faces=set(planar.configured_faces(obj))
            except ValueError:continue
            evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.data
            # Face indices must still refer to the configured source topology.
            if planar.topology_signature(mesh)!=state.topology:continue
            mesh.calc_loop_triangles()
            groups={}
            for tri in mesh.loop_triangles:
                if tri.polygon_index in faces:groups.setdefault(tri.material_index,[]).append(tuple(tri.loops))
            for slot,indices in groups.items():
                mat=evaluated.material_slots[slot].material if slot<len(evaluated.material_slots) else None
                if mat is None:continue
                key=(obj.as_pointer(),slot,id(data['vbo']),state.faces,node_transpiler.topo_signature(mat))
                live.add(key)
                item=cache.get(key)
                if item is None:
                    res=node_transpiler.transpile_reflection_properties(mat)
                    decl=''.join('uniform sampler2D '+s.uniform+';\n' for s in res.samplers)+'\n'.join(res.param_decls)
                    sh=gpu.types.GPUShader(shaders.PHONG_VERT,_FRAGMENT+decl+res.helpers+res.glsl+_MAIN)
                    ibo=gpu.types.GPUIndexBuf(type='TRIS',seq=indices)
                    batch=gpu.types.GPUBatch(type='TRIS',buf=data['vbo'],elem=ibo);batch.vertbuf_add(data['vbo2'])
                    item=cache[key]=(sh,batch,res,data['vbo'])
                sh,batch,res,_=item;sh.bind()
                sh.uniform_float('uViewProj',view_projection);sh.uniform_float('uModel',evaluated.matrix_world)
                sh.uniform_float('uNormalMat',evaluated.matrix_world.to_3x3().inverted_safe().transposed())
                for name,value in [('uGenMin',data['gen_min']),('uGenScale',data['gen_scale'])]:
                    try:sh.uniform_float(name,value)
                    except ValueError:pass
                sh.uniform_float('uReflectionProjection',Matrix([state.projection[i:i+4] for i in range(0,16,4)]))
                sh.uniform_float('uViewer',engine._cam_pos)
                sh.uniform_sampler('uReflection',gpu.texture.from_image(state.image))
                for p in res.params:
                    try:sh.uniform_float(p.uniform,p.value(mat.node_tree))
                    except ValueError:pass
                for s in res.samplers:sh.uniform_sampler(s.uniform,gpu.texture.from_image(s.image))
                batch.draw(sh)
        for key in list(cache):
            if key not in live:del cache[key]
    finally:
        gpu.state.depth_test_set(old_depth);gpu.state.depth_mask_set(old_mask);gpu.state.blend_set(old_blend)
        gpu.state.face_culling_set(getattr(engine,'_cull','NONE'))
