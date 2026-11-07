import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def run():
 result={}
 try:
  ob,m,node,scale,offset=f.setup();sc=bpy.context.scene;t=m.node_tree
  sc.camera.data.type='PERSP';sc.vertex_lit.key_intensity=.8;sc.vertex_lit.hemi_intensity=.4
  sep=t.nodes.new('ShaderNodeSeparateXYZ');t.links.new(t.nodes.get('UV Map').outputs[0],sep.inputs[0]);t.links.new(sep.outputs['X'],node.inputs['Height'])
  actual=f.render('sloped_parallax',m)
  node.depth=0
  for v in ob.data.vertices:v.co.z=.1*v.co.x
  ob.data.update()
  expected=f.render('sloped_geometry',m)
  mask=(actual[:,:,3]>.99)&(expected[:,:,3]>.99)
  # Exclude silhouette/height-clamp boundary pixels: POM does not move mesh edges.
  for i in range(4):mask=mask&np.roll(mask,1,0)&np.roll(mask,-1,0)&np.roll(mask,1,1)&np.roll(mask,-1,1)
  error=float(abs(actual[:,:,:3]-expected[:,:,:3])[mask].max())
  assert error<.004,error
  result={'pass':True,'max_error':error}
 except Exception:result['error']=traceback.format_exc()
 (f.out/'sloped.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
