import bpy,numpy as np,time,tracemalloc,json,pathlib,gc
results={}
class Transfer(bpy.types.RenderEngine):
 bl_idname='TRANSFER_AUDIT';bl_label='Transfer audit'
 def render(self,dg):
  r=self.begin_result(0,0,1024,1024);p=r.layers[0].passes['Combined']
  a=np.full((1024*1024,4),.25,dtype=np.float32)
  for mode in ('list','array','bulk'):
   gc.collect();tracemalloc.start();start=time.perf_counter()
   if mode=='bulk':p.rect.foreach_set(a.reshape(-1))
   else:p.rect=a.tolist() if mode=='list' else a
   elapsed=time.perf_counter()-start;peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
   assert all(abs(v-.25)<1e-6 for v in p.rect[0])
   assert all(abs(v-.25)<1e-6 for v in p.rect[-1])
   results[mode]={'seconds':elapsed,'python_peak_mib':peak/(1024*1024)}
  self.end_result(r)
bpy.utils.register_class(Transfer);bpy.context.scene.render.engine='TRANSFER_AUDIT';bpy.ops.render.render()
p=pathlib.Path(__file__).with_suffix('.json');p.write_text(json.dumps(results,indent=2));print(results)
