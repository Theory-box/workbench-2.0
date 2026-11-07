"""Exercise native viewport toggles, trace-distance and sun changes."""
import bpy,sys,pathlib,json,traceback,numpy as np,gpu,importlib.util
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_contact_shadows.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import engine
original=engine.VertexLitEngine.view_draw
stage=0;frames=0;pending=False;done=False;captures=[]

def finish(error=None):
 global done
 if done:return
 done=True;(f.f.out/'contact_viewport.json').write_text(json.dumps({'pass':error is None,'error':error}));bpy.ops.wm.quit_blender()

def change():
 global stage,frames,pending
 stage+=1;frames=0;pending=False;s=bpy.context.scene.vertex_lit
 if stage==1:s.use_contact_shadows=True
 if stage==2:s.contact_length=.1
 if stage==3:s.sun_azimuth=3.14159
 if stage==4:s.use_contact_shadows=False

def draw(self,context,dg):
 global frames,pending
 try:
  original(self,context,dg)
  if done or pending or self._geo_pending or self._mat_pending:return
  frames+=1
  if frames<3:return
  w,h=context.region.width,context.region.height;b=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');b.dimensions=w*h*4
  px=np.asarray(b).reshape(h,w,4).copy();assert np.isfinite(px).all()
  if captures:assert np.count_nonzero(np.max(abs(px-captures[-1]),axis=2)>.005)>20
  captures.append(px);pending=True
  if stage<4:bpy.app.timers.register(change,first_interval=.1)
  else:bpy.app.timers.register(lambda:finish(),first_interval=.1)
 except Exception:
  error=traceback.format_exc();bpy.app.timers.register(lambda:finish(error),first_interval=.1)
engine.VertexLitEngine.view_draw=draw

def begin():
 f.setup();bpy.context.scene.vertex_lit.use_contact_shadows=False
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':
   a.spaces.active.region_3d.view_perspective='CAMERA';a.spaces.active.overlay.show_overlays=False;a.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.15)
def pump():
 if done:return
 for a in bpy.context.screen.areas:a.tag_redraw()
 return .15
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('timeout') if not done else None,first_interval=45)
