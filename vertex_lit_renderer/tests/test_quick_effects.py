import bpy,pathlib,importlib.util,json,traceback,numpy as np,gpu,time
from mathutils import Quaternion
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_depth.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import engine
from vertex_lit_renderer.fx.pipeline import Pipeline
post_original=Pipeline.render
seen_effect_quality=set()
def checked_post(self,w,h,draw_scene,ctx,vls,blit=True):
 seen_effect_quality.add((ctx['ao_samples'],ctx['contact_steps']))
 assert (ctx['ao_samples'],ctx['contact_steps']) in {(16,8),(64,64)}
 assert vls.ao_samples=='64' and vls.contact_steps==64
 return post_original(self,w,h,draw_scene,ctx,vls,blit)
Pipeline.render=checked_post
original=engine.VertexLitEngine.view_draw;draw_original=engine.VertexLitEngine._draw_batches
stage=0;done=False;observed=False;start=0;quick=None
def batches(self,*args,**kwargs):
 global observed
 observed=getattr(self,'_quick_shadows',False)
 assert not getattr(self,'_quick_parallax',False)
 if not getattr(self,'_final_render',False):
  assert self._viewport_shadow_map.size == (1024 if observed else 2048)
 return draw_original(self,*args,**kwargs)
engine.VertexLitEngine._draw_batches=batches
def finish(error=None):
 global done
 if done:return
 done=True;(f.f.out/'quick_effects.json').write_text(json.dumps({'pass':error is None,'error':error}));bpy.ops.wm.quit_blender()
def move():
 global stage
 stage=1;cube.location.x+=.2
def orbit():
 global stage
 stage=3
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':
   rv=a.spaces.active.region_3d;rv.view_perspective='PERSP';rv.view_distance=5;rv.view_rotation=Quaternion((1,0,0),.7)
def draw(self,context,dg):
 global stage,quick
 try:
  original(self,context,dg)
  assert not self._quick_parallax
  if done or self._geo_pending or self._mat_pending:return
  if stage==0 and time.monotonic()-start>.6:
   assert not observed;stage=-1;bpy.app.timers.register(move,first_interval=.01)
  elif stage==1:
   assert observed;stage=2
   w,h=context.region.width,context.region.height;b=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');b.dimensions=w*h*4;quick=np.asarray(b).copy()
  elif stage==2 and not observed:
   w,h=context.region.width,context.region.height;b=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');b.dimensions=w*h*4
   assert np.count_nonzero(abs(np.asarray(b)-quick)>.01)>100
   stage=-1;bpy.app.timers.register(orbit,first_interval=.01)
  elif stage==3:
   assert observed;stage=4
  elif stage==4 and not observed:
   stage=5;bpy.app.timers.register(play,first_interval=.01)
  elif stage==6:
   assert context.screen.is_animation_playing and observed
   stage=7;bpy.app.timers.register(stop,first_interval=.01)
 except Exception:
  error=traceback.format_exc();bpy.app.timers.register(lambda:finish(error),first_interval=.01)
engine.VertexLitEngine.view_draw=draw
def play():
 global stage
 stage=6;bpy.ops.screen.animation_play();cube.location.x+=.2
def stop():
 bpy.ops.screen.animation_cancel(restore_frame=False)
 assert {(16,8),(64,64)} <= seen_effect_quality,seen_effect_quality
 finish()
def begin():
 global ob,m,n,cube,start
 ob,m,n,cube=f.setup();sc=bpy.context.scene
 sc.vertex_lit.quick_navigation=False;sc.vertex_lit.use_shadows=True;sc.vertex_lit.sun_intensity=1
 sc.vertex_lit.use_ao=True;sc.vertex_lit.ao_samples='64';sc.vertex_lit.shadow_resolution='2048'
 sc.vertex_lit.use_contact_shadows=True;sc.vertex_lit.contact_steps=64
 a=f.f.render('quick_f12_off',m)
 sc.vertex_lit.quick_shadows=True;sc.vertex_lit.quick_ao=True;sc.vertex_lit.quick_contact=True;b=f.f.render('quick_f12_on',m);assert abs(a-b).max()<1e-5
 sc.frame_start=1;sc.frame_end=2;sc.render.filepath=str(f.f.out/'quick_animation_')
 bpy.ops.render.render(animation=True)
 for frame in (1,2):
  im=bpy.data.images.load(str(f.f.out/('quick_animation_%04d.exr'%frame)),check_existing=False)
  pixels=np.array(im.pixels[:],dtype=np.float32).reshape(256,256,4);bpy.data.images.remove(im)
  assert abs(a-pixels).max()<1e-5
 start=time.monotonic()
 for area in bpy.context.screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False;area.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.1)
def pump():
 if done:return
 # Only pump initial loading. After movement, restoration must schedule itself.
 if stage in (0,-1):
  for a in bpy.context.screen.areas:a.tag_redraw()
 return .1
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('timeout') if not done else None,first_interval=35)
