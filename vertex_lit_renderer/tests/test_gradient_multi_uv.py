import bpy,sys,pathlib,json,traceback,numpy as np
root=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
import vertex_lit_renderer as addon;addon.register()
def run():
 result={}
 try:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  bpy.ops.mesh.primitive_plane_add(size=2);ob=bpy.context.object
  m=bpy.data.materials.new('Exact screenshot graph');m.use_nodes=True;ob.data.materials.append(m);t=m.node_tree;t.nodes.clear()
  uv=t.nodes.new('ShaderNodeUVMap');vm=t.nodes.new('ShaderNodeVectorMath');vm.operation='SCALE';vm.inputs['Scale'].default_value=79.2;uv.uv_map='UVMap'
  for datum in ob.data.uv_layers['UVMap'].data:datum.uv*=4/79.2
  other=ob.data.uv_layers.new(name='Other');other.active_render=True;ob.data.uv_layers.active=other
  for datum in other.data:datum.uv=(.5,.5)
  g=t.nodes.new('ShaderNodeTexGradient');g.gradient_type='LINEAR';em=t.nodes.new('ShaderNodeBsdfPrincipled');out=t.nodes.new('ShaderNodeOutputMaterial')
  t.links.new(uv.outputs['UV'],vm.inputs[0]);t.links.new(vm.outputs['Vector'],g.inputs['Vector']);t.links.new(g.outputs['Color'],em.inputs['Base Color']);t.links.new(g.outputs['Color'],out.inputs['Surface'])
  bpy.ops.object.camera_add(location=(0,0,3));cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=2
  sc=bpy.context.scene;sc.camera=cam;sc.render.resolution_x=128;sc.render.resolution_y=128;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='OPEN_EXR';sc.cycles.samples=1
  s=sc.vertex_lit;s.use_ao=False;s.use_cavity=False;s.use_outline=False;s.aa_method='OFF';s.supersampling='1';s.key_intensity=0;s.sun_intensity=0;s.hemi_intensity=1
  for route in ('two_named_uvs',):
   mix=t.nodes.new('ShaderNodeMix');mix.data_type='RGBA';mix.inputs[0].default_value=.5
   colors=[s for s in mix.inputs if s.type=='RGBA'];colors[0].default_value=(0,0,0,1)
   t.links.new(g.outputs['Color'],colors[1])
   second_uv=t.nodes.new('ShaderNodeUVMap');second_uv.uv_map='Other'
   second_gradient=t.nodes.new('ShaderNodeTexGradient')
   t.links.new(second_uv.outputs['UV'],second_gradient.inputs['Vector'])
   t.links.new(second_gradient.outputs['Color'],colors[0])
   for link in list(em.inputs['Base Color'].links):t.links.remove(link)
   t.links.new(next(s for s in mix.outputs if s.identifier=='Result_Color'),em.inputs['Base Color'])
   for link in list(out.inputs['Surface'].links):t.links.remove(link)
   t.links.new(em.outputs[0],out.inputs['Surface'])
   if route=='named_uv_lightmap':
    image=bpy.data.images.new('Test lighting',width=4,height=4,float_buffer=True)
    image.pixels.foreach_set(np.ones(64,dtype=np.float32));image.update()
    ob.vlr_lightmap.image=image;ob.vlr_lightmap.uv_name='Other';ob.update_tag(refresh={'DATA'})
   if route=='missing_uv':uv.uv_map='Missing layer'
   if route=='collection_instance':
    uv.uv_map='UVMap'
    col=bpy.data.collections.new('Instance source');col.objects.link(ob)
    for collection in list(ob.users_collection):
     if collection != col:collection.objects.unlink(ob)
    instance=bpy.data.objects.new('Instance',None);sc.collection.objects.link(instance)
    instance.instance_type='COLLECTION';instance.instance_collection=col
   engine='VERTEX_LIT'
   sc.render.engine=engine;sc.render.filepath=str(root/'work'/('gradient-'+engine+'.exr'));bpy.ops.render.render(write_still=True)
   im=bpy.data.images.load(sc.render.filepath,check_existing=False);pixels=np.array(im.pixels[:]).reshape(128,128,4);bpy.data.images.remove(im)
   samples=pixels[64,[8,24,40,56,72,88,104,120],0]
   expected=(np.minimum((np.array([8,24,40,56,72,88,104,120])+.5)/128*4,1)+.5)/1.5
   if route=='missing_uv':assert np.max(abs(samples))<.001,(route,samples)
   else:assert np.max(abs(samples/samples[-1]-expected))<.003,(route,samples)
   result[route]=samples.tolist()
  result['pass']=True

 except Exception:result['error']=traceback.format_exc()
 (root/'work/gradient-multi-uv.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)

