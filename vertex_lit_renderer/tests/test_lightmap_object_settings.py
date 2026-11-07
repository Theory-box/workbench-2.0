import bpy,sys,pathlib,json,traceback,numpy as np
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import lightmap
out=repo.parent/'work/lightmap-tests';result={}
try:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 sc=bpy.context.scene;sc.render.engine='VERTEX_LIT';sc.cycles.device='CPU'
 sc.vertex_lit.use_sun=False;sc.vertex_lit.sky_color=(.8,.8,.8);sc.vertex_lit.ground_color=(.8,.8,.8);sc.vertex_lit.hemi_intensity=1
 objs=[]
 for i,passes in enumerate(('DIRECT','INDIRECT','BOTH')):
  bpy.ops.mesh.primitive_plane_add(size=1,location=(i*3,0,0));ob=bpy.context.object;ob.name='Bake'+passes;objs.append(ob)
  assert ob.vlr_lightmap_settings.resolution=='2048'
  s=ob.vlr_lightmap_settings;s.resolution='128' if i!=1 else '256';s.samples=2+i;s.passes=passes;s.lighting_source='WORKBENCH'
  mat=bpy.data.materials.new('Diffuse');mat.use_nodes=True;t=mat.node_tree;t.nodes.clear();d=t.nodes.new('ShaderNodeBsdfDiffuse');o=t.nodes.new('ShaderNodeOutputMaterial');t.links.new(d.outputs[0],o.inputs[0]);ob.data.materials.append(mat)
 for ob in objs:ob.select_set(True)
 bpy.context.view_layer.objects.active=objs[0]
 calls=[];original=lightmap._cycles_bake
 def checked(uv,margin,passes='BOTH'):
  calls.append((bpy.context.active_object.name,sc.cycles.samples,passes))
  return original(uv,margin,passes)
 lightmap._cycles_bake=checked
 lightmap.bake_selected(bpy.context)
 assert len(calls)==3,calls
 values=[]
 for i,ob in enumerate(objs):
  size=256 if i==1 else 128;assert tuple(ob.vlr_lightmap.image.size)==(size,size)
  a=np.array(ob.vlr_lightmap.image.pixels[:]).reshape(size,size,4);values.append(float(a[size//2,size//2,0]))
 assert values[0]>.7 and values[1]<.001 and abs(values[0]-values[2])<.025,values
 previous=[(ob.data,ob.vlr_lightmap.image) for ob in objs];counter=[0]
 def cancelled(*args):
  counter[0]+=1
  return {'FINISHED'} if counter[0]==1 else {'CANCELLED'}
 lightmap._cycles_bake=cancelled
 try:lightmap.bake_selected(bpy.context);raise AssertionError('Expected cancellation')
 except RuntimeError:pass
 assert [(ob.data,ob.vlr_lightmap.image) for ob in objs]==previous
 assert sc.render.engine=='VERTEX_LIT'
 names=[ob.name for ob in objs]
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'per_object_settings.blend'))
 bpy.ops.wm.open_mainfile(filepath=str(out/'per_object_settings.blend'),load_ui=False)
 for i,name in enumerate(names):
  s=bpy.data.objects[name].vlr_lightmap_settings
  assert s.resolution==('256' if i==1 else '128') and s.samples==2+i
  assert s.passes==('DIRECT','INDIRECT','BOTH')[i] and s.lighting_source=='WORKBENCH'
 result={'pass':True,'pass_values':values,'calls':calls,'mixed_batch_rollback':True,'save_reopen':True}
except Exception:result['error']=traceback.format_exc()
(out/'per_object_settings.json').write_text(json.dumps(result,indent=2));print(result)
