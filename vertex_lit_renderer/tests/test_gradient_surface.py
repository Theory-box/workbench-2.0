import bpy,sys,pathlib,json,traceback,numpy as np
root=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
import vertex_lit_renderer as addon;addon.register()
def run():
 result={}
 try:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  bpy.ops.mesh.primitive_plane_add(size=2);ob=bpy.context.object
  m=bpy.data.materials.new('Exact screenshot graph');m.use_nodes=True;ob.data.materials.append(m);t=m.node_tree;t.nodes.clear()
  uv=t.nodes.new('ShaderNodeUVMap');vm=t.nodes.new('ShaderNodeVectorMath');vm.operation='SCALE';vm.inputs['Scale'].default_value=4
  g=t.nodes.new('ShaderNodeTexGradient');g.gradient_type='LINEAR';em=t.nodes.new('ShaderNodeEmission');out=t.nodes.new('ShaderNodeOutputMaterial')
  t.links.new(uv.outputs['UV'],vm.inputs[0]);t.links.new(vm.outputs['Vector'],g.inputs['Vector']);t.links.new(g.outputs['Color'],em.inputs['Color']);t.links.new(g.outputs['Color'],out.inputs['Surface'])
  bpy.ops.object.camera_add(location=(0,0,3));cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=2
  sc=bpy.context.scene;sc.camera=cam;sc.render.resolution_x=128;sc.render.resolution_y=128;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='OPEN_EXR';sc.cycles.samples=1
  s=sc.vertex_lit;s.use_ao=False;s.use_cavity=False;s.use_outline=False;s.aa_method='OFF';s.supersampling='1';s.key_intensity=0;s.sun_intensity=0;s.hemi_intensity=1
  for route in ('direct','color_reroute','shader_reroute'):
   for link in list(out.inputs['Surface'].links):t.links.remove(link)
   if route=='direct':t.links.new(g.outputs['Color'],out.inputs['Surface'])
   else:
    reroute=t.nodes.new('NodeReroute')
    t.links.new(g.outputs['Color'] if route=='color_reroute' else em.outputs[0],reroute.inputs[0])
    t.links.new(reroute.outputs[0],out.inputs['Surface'])
   engine='VERTEX_LIT'
   sc.render.engine=engine;sc.render.filepath=str(root/'work'/('gradient-'+engine+'.exr'));bpy.ops.render.render(write_still=True)
   im=bpy.data.images.load(sc.render.filepath,check_existing=False);pixels=np.array(im.pixels[:]).reshape(128,128,4);bpy.data.images.remove(im)
   samples=pixels[64,[8,24,40,56,72,88,104,120],0]
   expected=np.minimum((np.array([8,24,40,56,72,88,104,120])+.5)/128*4,1)
   assert np.max(abs(samples/samples[-1]-expected))<.003,(route,samples)
   result[route]=samples.tolist()
  result['pass']=True

 except Exception:result['error']=traceback.format_exc()
 (root/'work/gradient-direct-after.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)

