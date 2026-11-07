import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import material_shader

def run():
 result={}
 try:
  ob,m,node,scale,offset=f.setup();sc=bpy.context.scene;t=m.node_tree
  sc.camera.data.type='PERSP';sc.camera.data.lens=50
  for transform in ((1,1,1),(2,.6,1),(-1,1,1)):
   ob.scale=transform;node.depth=.2;ob.location.z=0
   actual=f.render('perspective_parallax',m)
   node.depth=0;ob.location.z=.1
   reference=f.render('perspective_geometry',m)
   mask=(actual[:,:,3]>.99)&(reference[:,:,3]>.99)
   error=float(abs(actual[:,:,:3]-reference[:,:,:3])[mask].max());assert error<.003,(transform,error)
   result['perspective_'+str(transform)]=error
  ob.scale=(1,1,1);ob.location.z=0;sc.camera.data.type='ORTHO';node.depth=.2
  uv=t.nodes.get('UV Map');primary=ob.data.uv_layers['UVMap'];primary.active_render=True
  named=f.render('named',m)
  uv.uv_map='';implicit=f.render('implicit',m);assert abs(named-implicit).max()<1e-5
  uv.uv_map='UVMap';node.uv_map='';default=f.render('default',m);assert abs(named-default).max()<1e-5
  node.uv_map='UVMap'
  v,frag,res=material_shader.build_material_frag(m,'WORKBENCH')
  import gpu
  gpu.types.GPUShader(v,frag)
  v,frag,res=material_shader.build_bake_frag(m);assert 'vlrParallaxOffset' not in frag
  gpu.types.GPUShader(v,frag)
  bpy.ops.wm.save_as_mainfile(filepath=str(f.out/'parallax-test.blend'))
  bpy.ops.wm.open_mainfile(filepath=str(f.out/'parallax-test.blend'))
  m=bpy.data.materials['Parallax Test'];saved=f.render('reopened',m)
  assert abs(named-saved).max()<1e-5
  result['alias_studio_bake_save']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.out/'extended.json').write_text(json.dumps(result,indent=2));print(result);bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender() and None,first_interval=.3)
bpy.app.timers.register(run,first_interval=.5)
