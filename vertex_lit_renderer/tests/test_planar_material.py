import bpy,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from vertex_lit_renderer.node_transpiler import transpile_reflection_properties
m=bpy.data.materials.new('Existing');m.use_nodes=True
nt=m.node_tree;p=nt.nodes.get('Principled BSDF');p.inputs['Roughness'].default_value=.25
before=(len(nt.nodes),len(nt.links))
r=transpile_reflection_properties(m)
assert len(r.params)==4 and not r.samplers
assert abs(r.params[0].value(nt)-.25)<1e-6
p.inputs['Roughness'].default_value=.8
assert abs(r.params[0].value(nt)-.8)<1e-6
assert before==(len(nt.nodes),len(nt.links))
t=nt.nodes.new('ShaderNodeTexImage');t.image=bpy.data.images.new('Roughness',4,4)
t.extension='MIRROR';nt.links.new(t.outputs['Color'],p.inputs['Roughness'])
r=transpile_reflection_properties(m)
assert len(r.samplers)==1 and r.samplers[0].image==t.image
assert 'texture(' in r.glsl and 'mod(' in r.glsl
assert len(nt.nodes)==3 and len(nt.links)==2
print('PASS live roughness values, linked image, mirror addressing, unchanged material graph')

# Optional real-GPU compilation when launched in a graphical Blender process.
if not bpy.app.background:
 import gpu
 from vertex_lit_renderer import shaders
 def check_gpu():
  declarations=''.join('uniform sampler2D '+x.uniform+';\n' for x in r.samplers)
  declarations+='\n'.join(r.param_decls)
  fragment=shaders.BAKE_FRAG_HEAD+declarations+r.helpers+r.glsl+'\nvoid main(){fragColor=computeReflectionProperties(vUV);}'
  gpu.types.GPUShader(shaders.PLANE_BAKE_VERT,fragment)
  print('PASS reflection-property GPU shader compilation')
  bpy.ops.wm.quit_blender()
 bpy.app.timers.register(check_gpu,first_interval=1)
