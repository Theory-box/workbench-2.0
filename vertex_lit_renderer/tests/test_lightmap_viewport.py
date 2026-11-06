import bpy,sys,pathlib,json,traceback,numpy as np,gpu
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import engine,lightmap
out=repo.parent/'work/lightmap-tests'
bpy.ops.wm.open_mainfile(filepath=str(out/'workflow.blend'),load_ui=False)
stage=0;frames=0;pending=False;done=False;result={}
original=engine.VertexLitEngine.view_draw

def finish(error=None):
 global done
 done=True
 if error:result['error']=error
 else:result['pass']=True
 (out/'viewport.json').write_text(json.dumps(result,indent=2));print(result,flush=True)
 bpy.ops.wm.quit_blender()

def rebake():
 global stage,frames,pending
 try:
  sc=bpy.context.scene;selected=set(bpy.context.selected_objects);active=bpy.context.active_object
  settings=(sc.vertex_lit.use_ao,sc.vertex_lit.use_cavity,sc.vertex_lit.use_outline)
  before=[(o,o.vlr_lightmap.image.name) for o in selected if o.type=='MESH']
  assert bpy.ops.vertex_lit.lightmap_bake()=={'FINISHED'}
  assert sc.render.engine=='VERTEX_LIT'
  assert selected==set(bpy.context.selected_objects) and bpy.context.active_object is active
  assert settings==(sc.vertex_lit.use_ao,sc.vertex_lit.use_cavity,sc.vertex_lit.use_outline)
  assert all(o.vlr_lightmap.image.name!=name for o,name in before)
  assert all(a.spaces.active.shading.type=='RENDERED' for a in bpy.context.screen.areas if a.type=='VIEW_3D')
  result['rebake_from_rendered_view']=True
  stage=1;frames=0;pending=False
 except Exception:finish(traceback.format_exc())

def draw(self,context,dg):
 global frames,pending
 try:
  original(self,context,dg)
  if done or pending or self._geo_pending or self._mat_pending:return
  frames+=1
  if frames<8:return
  assert len(self._lightmap_geometry)>=2
  w,h=context.region.width,context.region.height
  buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'UBYTE');buf.dimensions=w*h*4
  pixels=np.asarray(buf,dtype=np.uint8).reshape(h,w,4).copy();np.save(out/('viewport-'+str(stage)+'.npy'),pixels)
  assert pixels[:,:,:3].max()>30
  pending=True
  if stage==0:bpy.app.timers.register(rebake,first_interval=.1)
  else:
   result['viewport_uses_lightmaps']=True
   bpy.app.timers.register(lambda:finish(),first_interval=.1)
 except Exception:
  pending=True;error=traceback.format_exc();bpy.app.timers.register(lambda:finish(error),first_interval=.1)
engine.VertexLitEngine.view_draw=draw

def begin():
 for area in bpy.context.screen.areas:
  if area.type=='VIEW_3D':
   sp=area.spaces.active;sp.overlay.show_overlays=False
   sp.region_3d.view_location=(0,1,1.5);sp.region_3d.view_rotation=(Vector((0,1,1.5))-Vector((6,-9,6))).to_track_quat('-Z','Y');sp.region_3d.view_distance=10
   sp.show_region_ui=True;sp.shading.type='RENDERED';area.tag_redraw()
 bpy.app.timers.register(pump,first_interval=.1)
def pump():
 if done:return
 for area in bpy.context.screen.areas:
  if area.type=='VIEW_3D':area.tag_redraw()
 return .1
bpy.app.timers.register(begin,first_interval=1)
bpy.app.timers.register(lambda:finish('Viewport test timeout') if not done else None,first_interval=60)
