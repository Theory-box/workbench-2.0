import bpy,sys,pathlib,json,numpy as np,gpu
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from vertex_lit_renderer import engine
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=8);obj=bpy.context.object
out=pathlib.Path(__file__).parent/('geometry-memory-'+sys.argv[-1]+'.json')
def run():
 data=engine._extract_geometry(obj,bpy.context.evaluated_depsgraph_get())
 seen=set();arrays={}
 def visit(value,path):
  if id(value) in seen:return
  seen.add(id(value))
  if isinstance(value,np.ndarray):arrays[path]=value.nbytes
  elif isinstance(value,dict):
   for k,v in value.items():visit(v,path+'/'+str(k))
  elif isinstance(value,(tuple,list)):
   for i,v in enumerate(value):visit(v,path+'/'+str(i))
  elif isinstance(value,engine._RangeDraw):visit(value._geometry,path+'/geometry')
 visit(data,'cache')
 # Exercise shadow creation and full-range instancing after CPU data is released.
 assert engine._build_shadow_batch_from_cache(data) is not None
 for batch,_,_ in data['slots_list']:assert batch.instanced_batch() is not None
 result={'loops':data['n_loops'],'triangles':data['n_tris'],'retained_numpy_bytes':sum(arrays.values()),'arrays':arrays,'gpu_buffer_payload_estimate_bytes':data['n_loops']*48+data['n_tris']*12}
 out.write_text(json.dumps(result,indent=2));print(result,flush=True);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=1)
