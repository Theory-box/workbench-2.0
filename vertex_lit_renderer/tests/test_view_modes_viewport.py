import bpy,sys,pathlib,json,traceback,numpy as np,gpu
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import engine
original=engine.VertexLitEngine.view_draw
modes=['TEXTURED','SOLID','RANDOM','ATTRIBUTE','NORMAL','DEPTH','SOLID'];index=0;frames=0;pending=False;done=False;result={}
def finish(error=None):
 global done
 done=True;result['error']=error;result['pass']=error is None
 (repo.parent/'work/view-mode-tests/viewport.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
def advance():
 global index,frames,pending
 index+=1;frames=0;pending=False
 if index==len(modes):finish();return
 bpy.context.scene.vertex_lit.view_mode=modes[index]
def draw(self,c,d):
 global frames,pending
 try:
  original(self,c,d)
  if done or pending or self._geo_pending:return
  frames+=1
  if frames<4:return
  w,h=c.region.width,c.region.height
  buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');buf.dimensions=w*h*4
  a=np.asarray(buf).reshape(h,w,4)
  lit=int(np.count_nonzero(np.max(a[:,:,:3],axis=2)>.05))
  assert lit>500,(modes[index],lit)
  result[str(index)+'_'+modes[index]]=lit
  pending=True;bpy.app.timers.register(advance,first_interval=.05)
 except Exception:
  error=traceback.format_exc();pending=True;bpy.app.timers.register(lambda:finish(error),first_interval=.05)
engine.VertexLitEngine.view_draw=draw
def begin():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.mesh.primitive_cube_add()
 s=bpy.context.scene.vertex_lit;s.background_mode='COLOR';s.background_color=(0,0,0);s.use_cavity=True;s.use_outline=True;s.aa_method='OFF'
 bpy.context.scene.render.engine='VERTEX_LIT'
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':
   sp=a.spaces.active;sp.overlay.show_overlays=False;sp.region_3d.view_location=(0,0,0);sp.region_3d.view_distance=8;sp.region_3d.view_rotation=Vector((-4,6,-3)).to_track_quat('-Z','Y');sp.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.1)
def pump():
 if done:return
 for a in bpy.context.screen.areas:a.tag_redraw()
 return .1
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('Timeout') if not done else None,first_interval=30)
