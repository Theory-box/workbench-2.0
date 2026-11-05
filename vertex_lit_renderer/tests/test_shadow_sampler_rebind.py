"""Real-GPU regression: repeated materials must rebind the shared shadow texture unit."""
import bpy, sys, pathlib, inspect, textwrap, json, traceback
import numpy as np
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import engine as en
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.render.engine='VERTEX_LIT'
sc.render.resolution_x=384;sc.render.resolution_y=256;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='OPEN_EXR'
s=sc.vertex_lit;s.use_shadows=True;s.use_ao=False;s.use_cavity=False;s.use_outline=False;s.aa_method='OFF';s.supersampling='1'
s.key_intensity=0;s.sun_intensity=2;s.hemi_intensity=0
out=repo.parent/'work/shadow-binding-results';out.mkdir(parents=True,exist_ok=True)
def render(name):
 sc.render.filepath=str(out/(name+'.exr'));bpy.ops.render.render(write_still=True)
 im=bpy.data.images.load(sc.render.filepath,check_existing=False)
 a=np.array(im.pixels[:],dtype=np.float32).reshape(im.size[1],im.size[0],4);bpy.data.images.remove(im)
 np.save(out/(name+'.npy'),a);return a

def variant(source):
 ns=dict(en.__dict__);exec(compile(source,'<shadow-binding-reference>','exec'),ns)
 return ns['_draw_batches']

def run():
 result={}
 original=en.VertexLitEngine._draw_batches
 try:
  mats=[]
  for j in range(3):
   m=bpy.data.materials.new('Shared'+str(j));m.use_nodes=True;mats.append(m)
   p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.7,.4,.2,1)
   for i in range(j):
    img=bpy.data.images.new('Image'+str(j)+'_'+str(i),width=4,height=4)
    pixels=np.tile(np.array([.6,.4,.2,1],dtype=np.float32),16);img.pixels.foreach_set(pixels)
    tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=img
    if i==0:color=tx.outputs['Color']
    else:
     mix=m.node_tree.nodes.new('ShaderNodeMixRGB');mix.inputs[0].default_value=.5
     m.node_tree.links.new(color,mix.inputs[1]);m.node_tree.links.new(tx.outputs['Color'],mix.inputs[2]);color=mix.outputs['Color']
   if j:m.node_tree.links.new(color,p.inputs['Base Color'])
  for i in range(18):
   bpy.ops.mesh.primitive_cube_add(size=1,location=((i%6)*1.5,(i//6)*1.5,0))
   obj=bpy.context.object;obj.data.materials.append(mats[i%3])
   if i in (4,10):
    for k in range(1,5):
     cp=obj.copy();cp.location.z+=k*1.3;sc.collection.objects.link(cp)
  bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,-.6))
  bpy.ops.object.camera_add(location=(13,-15,12));cam=bpy.context.object
  cam.rotation_euler=(Vector((3,1.5,0))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam
  source=textwrap.dedent(inspect.getsource(original))
  old_block="""            if id(sh) in frame_done:
                try: sh.uniform_sampler('uShadowMap', shad_tex)
                except ValueError: pass  # studio programs have no shadow map
"""
  assert old_block in source
  en.VertexLitEngine._draw_batches=variant(source.replace(old_block,''))
  before=render('old-cache')
  en.VertexLitEngine._draw_batches=original
  fixed=render('fixed-cache')
  en.VertexLitEngine._draw_batches=variant(source.replace('if id(sh) not in frame_done:','if True:'))
  reference=render('full-rebind-reference')
  result={'old_changed_pixels':int(np.any(abs(before-reference)>.002,axis=2).sum()),'fixed_max_error':float(abs(fixed-reference).max())}
  assert result['old_changed_pixels']>0, 'Scene did not exercise overwritten shadow bindings'
  assert result['fixed_max_error']==0, 'Cached binding differs from full rebinding'
  result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 finally:en.VertexLitEngine._draw_batches=original
 (out/'result.json').write_text(json.dumps(result,indent=2));print(result,flush=True);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=1)
