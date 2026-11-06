"""Headless regression: honor Blender mute bypasses and invalidate shader topology."""
import bpy, sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from vertex_lit_renderer import node_transpiler as nt

def graph():
 m=bpy.data.materials.new('Mute test');m.use_nodes=True;t=m.node_tree
 return m,t,t.nodes.get('Principled BSDF')

m,t,p=graph();uv=t.nodes.new('ShaderNodeTexCoord');scale=t.nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=4
g=t.nodes.new('ShaderNodeTexGradient');t.links.new(uv.outputs['UV'],scale.inputs[0]);t.links.new(scale.outputs['Vector'],g.inputs['Vector']);t.links.new(g.outputs['Color'],p.inputs['Base Color'])
bpy.context.view_layer.update();sig=nt.topo_signature(m);before=nt.transpile_material(m)
assert any(param.node_name==scale.name and param.index==3 for param in before.params)
scale.mute=True;bpy.context.view_layer.update();after=nt.transpile_material(m)
assert sig!=nt.topo_signature(m)
assert not any(param.node_name==scale.name for param in after.params)
assert 'vUV' in after.glsl and 'n_vvec' not in after.glsl
scale.mute=False;bpy.context.view_layer.update();assert nt.topo_signature(m)==sig

# Blender chooses Color1/A, not the factor, when muting a mix.
for typename in ('ShaderNodeMixRGB','ShaderNodeMix'):
 m,t,p=graph();mix=t.nodes.new(typename)
 if typename=='ShaderNodeMix':mix.data_type='RGBA';a=mix.inputs['A'];output=mix.outputs['Result']
 else:a=mix.inputs['Color1'];output=mix.outputs['Color']
 # The newer Mix node has hidden duplicate-name sockets; use identifiers.
 if typename=='ShaderNodeMix':a=next(s for s in mix.inputs if s.identifier=='A_Color');output=next(s for s in mix.outputs if s.identifier=='Result_Color')
 a.default_value=(.2,.3,.4,1);t.links.new(output,p.inputs['Base Color']);mix.mute=True;bpy.context.view_layer.update()
 result=nt.transpile_material(m);params=[v for v in result.params if v.node_name==mix.name]
 assert len(params)==1 and tuple(params[0].value(t))==tuple(a.default_value)
 assert 'mix(' not in result.glsl
print(json.dumps({'muted_scale_bypass':True,'mute_signature_invalidation':True,'mix_bypass_selection':True,'pass':True}))
