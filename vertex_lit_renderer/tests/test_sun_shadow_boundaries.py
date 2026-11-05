import bpy,sys,pathlib,json,traceback,numpy as np
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2]
root=repo.parent/'work'
sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import engine as en,instancing
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.render.engine='VERTEX_LIT'
sc.render.resolution_x=384;sc.render.resolution_y=256;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='OPEN_EXR'
s=sc.vertex_lit;s.use_shadows=True;s.use_ao=False;s.use_cavity=False;s.use_outline=False;s.aa_method='OFF';s.supersampling='1'
s.key_intensity=0;s.sun_intensity=2;s.hemi_intensity=.4
out=root/'sun-audit-results';out.mkdir(exist_ok=True)
def render(name):
 sc.render.filepath=str(out/(name+'.exr'));bpy.ops.render.render(write_still=True)
 im=bpy.data.images.load(sc.render.filepath,check_existing=False)
 a=np.array(im.pixels[:],dtype=np.float32).reshape(im.size[1],im.size[0],4);bpy.data.images.remove(im)
 np.save(out/(name+'.npy'),a);return a
def run():
 result={}
 try:
  for j in range(6):
   m=bpy.data.materials.new('Textured'+str(j));m.use_nodes=True
   img=bpy.data.images.new('Texture'+str(j),width=16,height=16)
   pix=np.ones((16,16,4),dtype=np.float32);pix[:,:,:3]=(.6,.2+(j%3)*.2,.1)
   pix[::2,::2,:3]*=.5;img.pixels.foreach_set(pix.ravel())
   tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=img
   if j%3==1:
    tx2=m.node_tree.nodes.new('ShaderNodeTexImage');tx2.image=img
    mix=m.node_tree.nodes.new('ShaderNodeMixRGB');mix.inputs[0].default_value=.4
    m.node_tree.links.new(tx.outputs['Color'],mix.inputs[1]);m.node_tree.links.new(tx2.outputs['Color'],mix.inputs[2]);tx=mix
   if j%3==2:
    tx=m.node_tree.nodes.new('ShaderNodeRGB');tx.outputs[0].default_value=(.6,.6,.1,1)
   m.node_tree.links.new(tx.outputs['Color'],m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
   bpy.ops.mesh.primitive_cube_add(size=1,location=(j*2,0,0));ob=bpy.context.object;ob.data.materials.append(m)
   for i in range(1,5):
    cp=ob.copy();cp.location.y=i*1.5;sc.collection.objects.link(cp)
  bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,-.6))
  bpy.ops.object.camera_add(location=(12,-15,12));cam=bpy.context.object
  cam.rotation_euler=(Vector((2,3,0))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam
  s.shadow_resolution='1024';s.shadow_softness=0
  a=render('softness-zero-after')
  s.shadow_softness=1
  b=render('softness-one-after')
  result['zero_vs_one']={'max':float(np.max(abs(a-b))),'pixels':int(np.any(abs(a-b)>.002,axis=2).sum())}
  assert result['zero_vs_one']['pixels']>0, 'Zero softness must produce hard shadows'
  s.sun_intensity=0
  ambient=render('boundary-ambient')
  s.sun_intensity=2
  for i,(distance,bias,softness,resolution,elevation) in enumerate([
      (1,0,0,'1024',0), (1000,.02,8,'4096',1.5708),
      (1000,0,.5,'1024',-1.5708), (25,.0004,1.5,'2048',.785398)]):
   s.shadow_distance=distance;s.shadow_bias=bias;s.shadow_softness=softness
   s.shadow_resolution=resolution;s.sun_elevation=elevation
   pixels=render('boundary-'+str(i))
   assert np.isfinite(pixels).all(), 'Nonfinite shadow output'
   assert np.min(pixels[:,:,:3]-ambient[:,:,:3])>=-.002, 'Shadows suppressed ambient fill'
   result['boundary_'+str(i)]={'finite':True,'ambient_preserved':True}
 except Exception:result['error']=traceback.format_exc()
 (out/'shadow-boundaries.json').write_text(json.dumps(result,indent=2));print(result,flush=True);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=1)

