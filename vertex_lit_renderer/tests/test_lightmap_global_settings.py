import bpy,sys,pathlib,json,traceback
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import lightmap
result={}
try:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 sc=bpy.context.scene;sc.render.engine='VERTEX_LIT';sc.cycles.device='CPU'
 sc.vlr_lightmap_settings.lighting_source='WORKBENCH';sc.vlr_lightmap_settings.passes='INDIRECT'
 obs=[]
 for i in range(2):
  bpy.ops.mesh.primitive_plane_add(location=(i*3,0,0));ob=bpy.context.object;obs.append(ob)
  ob.vlr_lightmap_settings.resolution=str(128*(i+1));ob.vlr_lightmap_settings.samples=1+i
  ob.vlr_lightmap_settings.lighting_source='SCENE';ob.vlr_lightmap_settings.passes='DIRECT'
 for ob in obs:ob.select_set(True)
 calls=[];original=lightmap._cycles_bake
 def check(uv,margin,passes='BOTH'):
  calls.append(passes);return original(uv,margin,passes)
 lightmap._cycles_bake=check
 assert lightmap.bake_selected(bpy.context)==2
 assert calls==['INDIRECT','INDIRECT'],calls
 for i,ob in enumerate(obs):
  assert tuple(ob.vlr_lightmap.image.size)==(128*(i+1),)*2
  assert 'Indirect' in ob.vlr_lightmap.status
 assert sc.vlr_lightmap_settings.lighting_source=='WORKBENCH'
 result['pass']=True
except Exception:result['error']=traceback.format_exc()
(repo.parent/'work/lightmap-tests/global_settings.json').write_text(json.dumps(result));print(result)
