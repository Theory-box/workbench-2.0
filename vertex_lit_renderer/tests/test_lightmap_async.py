"""Real UI bake jobs, heartbeat responsiveness, mixed batches and Esc rollback."""
import bpy,sys,pathlib,json,time,traceback
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import lightmap
out=repo.parent/'work/lightmap-tests/async_bake.json'
result={};state={'phase':'start','ticks':0,'job_ticks':0,'start':time.monotonic()}
sc=bpy.context.scene;sc.render.engine='VERTEX_LIT';sc.cycles.device='CPU'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
objs=[]
for i in range(2):
 bpy.ops.mesh.primitive_cube_add(location=(i*3,0,0));ob=bpy.context.object;objs.append(ob)
 ob.vlr_lightmap_settings.resolution='128';ob.vlr_lightmap_settings.samples=8+i
 ob.vlr_lightmap_settings.lighting_source='WORKBENCH'
 mod=ob.modifiers.new('Restore me','BEVEL');mod.show_render=False
for ob in objs:ob.select_set(True)
original_world=sc.world
base_handlers=(len(bpy.app.handlers.object_bake_complete),len(bpy.app.handlers.object_bake_cancel))
def finish():
 out.write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
def tick():
 try:
  state['ticks']+=1
  if time.monotonic()-state['start']>90:raise RuntimeError('timeout '+str(state))
  if bpy.app.is_job_running('OBJECT_BAKE'):state['job_ticks']+=1
  if state['phase']=='start':
   assert bpy.ops.vertex_lit.lightmap_bake('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
   state['phase']='success'
  elif state['phase']=='success' and lightmap._active_bake is None:
   assert all(ob.vlr_lightmap.image for ob in objs)
   assert state['job_ticks']>2,state
   assert sc.render.engine=='VERTEX_LIT' and sc.world==original_world
   assert all(ob.modifiers[0].show_viewport and not ob.modifiers[0].show_render for ob in objs)
   result['success_heartbeat_ticks']=state['job_ticks']
   state['previous']=[(ob.data,ob.vlr_lightmap.image) for ob in objs]
   objs[0].vlr_lightmap_settings.samples=512
   assert bpy.ops.vertex_lit.lightmap_bake('INVOKE_DEFAULT')=={'RUNNING_MODAL'}
   state['phase']='cancel'
  elif state['phase']=='cancel' and bpy.app.is_job_running('OBJECT_BAKE'):
   bpy.context.window.event_simulate(type='ESC',value='PRESS')
   bpy.context.window.event_simulate(type='ESC',value='RELEASE')
   state['phase']='wait_cancel'
  elif state['phase']=='wait_cancel' and lightmap._active_bake is None:
   assert [(ob.data,ob.vlr_lightmap.image) for ob in objs]==state['previous']
   assert sc.render.engine=='VERTEX_LIT' and sc.world==original_world
   assert all(ob.modifiers[0].show_viewport and not ob.modifiers[0].show_render for ob in objs)
   assert base_handlers==(len(bpy.app.handlers.object_bake_complete),len(bpy.app.handlers.object_bake_cancel))
   result.update({'pass':True,'esc_rollback':True,'handler_cleanup':True});finish();return
 except Exception:
  result['error']=traceback.format_exc();finish();return
 return .02
bpy.app.timers.register(tick,first_interval=.5)
