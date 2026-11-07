"""Read-only compiler audit: classify node edits as uniform, recompile, or ignored."""
import bpy,sys,pathlib,json
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import node_transpiler as nt
out=[]
def check(kind,label,mutate,prepare=None):
 m=bpy.data.materials.new('Audit '+label);m.use_nodes=True;t=m.node_tree;n=t.nodes.new(kind)
 if prepare:prepare(n)
 output=next((s for s in n.outputs if s.type=='RGBA'),n.outputs[0])
 t.links.new(output,t.nodes.get('Principled BSDF').inputs['Base Color'])
 def snapshot():
  r=nt.transpile_material(m);return nt.topo_signature(m),r.glsl+r.helpers+str(r.param_decls),[p.value(t) for p in r.params]
 a=snapshot();mutate(n);b=snapshot()
 out.append({'edit':label,'signature_changed':a[0]!=b[0],'shader_source_changed':a[1]!=b[1],'uniform_values_changed':a[2]!=b[2]})
 bpy.data.materials.remove(m)
def curve(n):
 n.mapping.initialize();n.mapping.curves[0].points.new(.4,.7);n.mapping.update()
check('ShaderNodeRGBCurve','RGB Curves point movement',curve)
check('ShaderNodeFloatCurve','Float Curve point movement',curve)
check('ShaderNodeVectorCurve','Vector Curves point movement',curve)
check('ShaderNodeTexBrick','Brick offset',lambda n:setattr(n,'offset',.31))
check('ShaderNodeTexBrick','Brick squash',lambda n:setattr(n,'squash',1.7))
check('ShaderNodeTexNoise','Noise scale',lambda n:setattr(n.inputs['Scale'],'default_value',7.2))
check('ShaderNodeTexNoise','Noise normalize',lambda n:setattr(n,'normalize',not n.normalize))
check('ShaderNodeTexNoise','Noise dimension 4D',lambda n:setattr(n,'noise_dimensions','4D'))
check('ShaderNodeTexNoise','Noise type ridged',lambda n:setattr(n,'noise_type','RIDGED_MULTIFRACTAL'))
im=bpy.data.images.new('Audit image',width=8,height=8)
check('ShaderNodeTexImage','Image interpolation Closest',lambda n:setattr(n,'interpolation','Closest'),lambda n:setattr(n,'image',im))
check('ShaderNodeTexImage','Image projection Box',lambda n:setattr(n,'projection','BOX'),lambda n:setattr(n,'image',im))
check('ShaderNodeValToRGB','Ramp stop position',lambda n:setattr(n.color_ramp.elements[0],'position',.2))
check('ShaderNodeValToRGB','Ramp color',lambda n:setattr(n.color_ramp.elements[0],'color',(.2,.3,.4,.5)))
check('ShaderNodeValToRGB','Ramp HSV mode',lambda n:setattr(n.color_ramp,'color_mode','HSV'))
check('ShaderNodeValToRGB','Ramp Linear to Cardinal',lambda n:setattr(n.color_ramp,'interpolation','CARDINAL'))
path=repo.parent/'work/node-update-audit.json';path.write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
