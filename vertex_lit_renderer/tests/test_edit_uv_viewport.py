import bpy,bmesh,sys,pathlib,json,traceback,numpy as np
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import engine
engine._KEEP_CPU_ARRAYS=True
original=engine.VertexLitEngine.view_draw
stage=0;pending=False;done=False
out=repo.parent/'work/lightmap-tests/edit-uv.json'
def finish(error=None):
 global done
 done=True;out.write_text(json.dumps({'pass':error is None,'error':error}));bpy.ops.wm.quit_blender()
def edit():
 global stage,pending
 try:
  if bpy.context.object.mode!='EDIT':bpy.ops.object.mode_set(mode='EDIT')
  bm=bmesh.from_edit_mesh(bpy.context.object.data);uv=bm.loops.layers.uv.active
  for v in bm.verts:v.co.x+=1
  for f in bm.faces:
   for l in f.loops:l[uv].uv*=2
  bmesh.update_edit_mesh(bpy.context.object.data,loop_triangles=False,destructive=False)
  stage+=1;pending=False
 except Exception:finish(traceback.format_exc())
def draw(self,context,dg):
 global pending
 try:
  original(self,context,dg)
  if done or pending or self._geo_pending:return
  data=self._mesh_cache.get('UV Test')
  if not data or 'uv' not in data:return
  expected=2**stage
  if abs(float(data['uv'].max())-expected)>.001:return
  if abs(float(data['pos'][:,0].max())-(1+stage))>.001:return
  pending=True
  if stage<2:bpy.app.timers.register(edit,first_interval=.2)
  else:bpy.app.timers.register(lambda:finish(),first_interval=.2)
 except Exception:
  error=traceback.format_exc();bpy.app.timers.register(lambda:finish(error),first_interval=.1)
engine.VertexLitEngine.view_draw=draw
def begin():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.mesh.primitive_plane_add();bpy.context.object.name='UV Test'
 bpy.context.scene.render.engine='VERTEX_LIT'
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.2)
def pump():
 if done:return
 for a in bpy.context.screen.areas:a.tag_redraw()
 return .2
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('Timeout: UV buffers did not refresh') if not done else None,first_interval=25)
