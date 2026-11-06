"""Actual Cycles-baked images displayed through the shared viewport/F12 draw path."""
import bpy,sys,pathlib,json,traceback,numpy as np
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
out=repo.parent/'work/lightmap-tests';out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(out/'workflow.blend'),load_ui=False)
sc=bpy.context.scene;sc.render.engine='VERTEX_LIT'
sc.render.resolution_x=320;sc.render.resolution_y=240;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='OPEN_EXR'
s=sc.vertex_lit;s.sun_intensity=0;s.hemi_intensity=0;s.key_intensity=0
for lamp in bpy.data.lights:lamp.energy=0

def render(name):
 sc.render.filepath=str(out/(name+'.exr'));bpy.ops.render.render(write_still=True)
 im=bpy.data.images.load(sc.render.filepath,check_existing=False)
 a=np.array(im.pixels[:],dtype=np.float32).reshape(im.size[1],im.size[0],4);bpy.data.images.remove(im)
 np.save(out/(name+'.npy'),a);return a

def run():
 result={}
 try:
  bpy.ops.object.camera_add(location=(6,-9,6));cam=bpy.context.object;cam.rotation_euler=(Vector((0,1,1.5))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam
  baked=render('baked-room')
  assignments=[(o,o.vlr_lightmap.image) for o in sc.objects if o.type=='MESH' and o.vlr_lightmap.image]
  assert len(assignments)==2
  for o,_ in assignments:o.vlr_lightmap.image=None
  unbaked=render('unbaked-room')
  delta=baked[:,:,:3]-unbaked[:,:,:3]
  assert np.count_nonzero(np.max(delta,axis=2)>.01)>100
  assert s.use_ao and s.use_cavity and s.use_outline
  result['actual_cycles_bake_displayed']=True;result['existing_effects_preserved']=True
  for o,im in assignments:o.vlr_lightmap.image=im
  # Controlled UV and object-binding test on linked meshes with one shared material.
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  s.use_ao=False;s.use_cavity=False;s.use_outline=False;s.aa_method='OFF';s.supersampling='1'
  m=bpy.data.materials.new('Common');m.use_nodes=True;m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.5,.25,.75,1)
  albedo=bpy.data.images.new('Original albedo',width=8,height=8,float_buffer=True);albedo.colorspace_settings.name='Non-Color'
  colors=np.ones((8,8,4),dtype=np.float32);colors[:,:,:3]=(1,0,0);colors[:4,:4,:3]=(.5,.25,.75)
  albedo.pixels.foreach_set(colors.ravel());albedo.update()
  tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=albedo
  m.node_tree.links.new(tx.outputs['Color'],m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
  bpy.ops.mesh.primitive_plane_add(size=1,location=(-3,0,0));source=bpy.context.object;source.data.materials.append(m)
  uv=source.data.uv_layers.new(name='SecondUV');source.data.uv_layers.active_index=0
  # Original material UVs deliberately collapse; lightmap UVs retain the square.
  for datum in source.data.uv_layers[0].data:datum.uv=(.25,.25)
  images=[]
  for color in ((.2,.4,.6),(1,.2,.1)):
   im=bpy.data.images.new('Constant lightmap',width=8,height=8,float_buffer=True);im.colorspace_settings.name='Non-Color'
   im.pixels.foreach_set(np.tile(np.array((*color,1),dtype=np.float32),64));im.update();images.append(im)
  objects=[source]
  for i in range(1,5):
   ob=source.copy();sc.collection.objects.link(ob);ob.location.x=-3+i*1.5;objects.append(ob)
  for i,ob in enumerate(objects):ob.vlr_lightmap.uv_name='SecondUV';ob.vlr_lightmap.image=images[i%2]
  bpy.ops.object.camera_add(location=(0,0,5));sc.camera=bpy.context.object;sc.camera.data.type='ORTHO';sc.camera.data.ortho_scale=8
  sc.render.resolution_x=400;sc.render.resolution_y=100
  mixed=render('shared-material-maps')
  expected=[np.array((.5,.25,.75))*np.array((.2,.4,.6) if i%2==0 else (1,.2,.1)) for i in range(5)]
  for i,ob in enumerate(objects):
   x=int((ob.location.x/8+.5)*400)
   assert np.max(abs(mixed[50,x,:3]-expected[i]))<.002,(i,mixed[50,x,:3],expected[i])
  result['shared_mesh_material_distinct_maps']=True
  # A split lightmap proves the second UV channel is sampled independently.
  pixels=np.ones((8,8,4),dtype=np.float32);pixels[:,:,:3]=(.2,0,0);pixels[:,4:,:3]=(0,.8,0)
  split=bpy.data.images.new('Split lightmap',width=8,height=8,float_buffer=True);split.colorspace_settings.name='Non-Color'
  split.pixels.foreach_set(pixels.ravel());split.update()
  objects[0].vlr_lightmap.image=split
  gradient=render('second-uv')
  x=int((objects[0].location.x/8+.5)*400)
  assert gradient[50,x-15,0]>.09 and gradient[50,x+15,1]>.19
  assert gradient[50,x-15,1]<.01 and gradient[50,x+15,0]<.01
  result['independent_lightmap_uv']=True;result['original_material_texture_uv_preserved']=True
  m.diffuse_color=(.5,.25,.75,1);m.use_nodes=False
  legacy=render('legacy-material-lightmap')
  x=int((objects[1].location.x/8+.5)*400)
  assert np.max(abs(legacy[50,x,:3]-expected[1]))<.002
  result['non_node_material_display']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (out/'render.json').write_text(json.dumps(result,indent=2));print(result,flush=True);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=1)
