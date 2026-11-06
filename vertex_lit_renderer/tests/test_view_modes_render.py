import bpy,sys,pathlib,json,traceback,numpy as np
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
out=repo.parent/'work/view-mode-tests';out.mkdir(exist_ok=True)
def run():
 result={}
 try:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  bpy.ops.mesh.primitive_cube_add();ob=bpy.context.object
  colors=ob.data.color_attributes.new(name='Color',type='FLOAT_COLOR',domain='CORNER')
  for c in colors.data:c.color=(.2,.6,.3,1)
  bpy.ops.object.camera_add(location=(4,-6,3));cam=bpy.context.object;cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler()
  sc=bpy.context.scene;sc.camera=cam;sc.render.engine='VERTEX_LIT';sc.render.resolution_x=128;sc.render.resolution_y=128;sc.render.resolution_percentage=100;sc.render.film_transparent=True;sc.render.image_settings.file_format='OPEN_EXR'
  settings=sc.vertex_lit;settings.supersampling='1'
  for mode in ('TEXTURED','SOLID','RANDOM','ATTRIBUTE','NORMAL','DEPTH','SOLID'):
   settings.view_mode=mode;settings.aa_method='OFF'
   # Exercise the auxiliary render targets in lit modes too.
   if mode not in ('NORMAL','DEPTH'):settings.use_cavity=True;settings.use_outline=True
   sc.render.filepath=str(out/(mode+'.exr'));bpy.ops.render.render(write_still=True)
   im=bpy.data.images.load(sc.render.filepath,check_existing=False);px=np.array(im.pixels[:],dtype=np.float32).reshape(128,128,4);bpy.data.images.remove(im)
   visible=px[:,:,3]>.5
   assert np.isfinite(px).all() and visible.sum()>200,(mode,int(visible.sum()))
   assert px[visible,:3].max()>.05,(mode,'black')
   result[mode]={'visible_pixels':int(visible.sum()),'max_rgb':float(px[visible,:3].max())}
  result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (out/'render.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
