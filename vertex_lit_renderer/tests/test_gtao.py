import bpy,pathlib,importlib.util,json,traceback,numpy as np,time
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_depth.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def run():
 result={}
 try:
  ob,m,n,cube=f.setup();n.depth=0;sc=bpy.context.scene;s=sc.vertex_lit
  m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.7,.7,.7,1)
  cube.data.materials[0].node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.7,.7,.7,1)
  s.ao_ridge=0;s.ao_samples='32'
  for camera in ('PERSP','ORTHO'):
   sc.camera.data.type=camera;s.use_ao=False;base=f.f.render('gtao_base',m)
   s.use_ao=True;s.ao_method='SSAO';classic=f.f.render('gtao_classic_'+camera,m)
   s.ao_method='GTAO';a=f.f.render('gtao_new_'+camera,m)
   count=int(((base-a)[:,:,:3].max(axis=2)>.01).sum());assert count>100,count
   assert (a-base)[:,:,:3].max()<.003
   assert abs(a[:,:,3]-base[:,:,3]).max()<.0001
   b=f.f.render('gtao_repeat',m);assert abs(a-b).max()<1e-5
   result[camera+'_ao_pixels']=count
   f.save_png('gtao_new_'+camera);f.save_png('gtao_classic_'+camera)
   cube.hide_render=True;s.use_ao=False;base=f.f.render('gtao_flat_base',m)
   s.use_ao=True;a=f.f.render('gtao_flat',m)
   err=float(abs(a[30:226,30:226]-base[30:226,30:226]).max());assert err<.015,err
   result[camera+'_flat_error']=err;cube.hide_render=False
  s.ao_strength=0;a=f.f.render('gtao_zero',m);s.use_ao=False;b=f.f.render('gtao_disabled',m)
  assert abs(a-b).max()<1e-5;result['strength_zero']=True
  s.ao_strength=1;s.use_ao=True
  cube.vlr_ao_exclude=True;a=f.f.render('gtao_excluded',m)
  assert np.isfinite(a).all();cube.vlr_ao_exclude=False
  n.depth=.4;a=f.f.render('gtao_parallax',m);assert np.isfinite(a).all()
  s.supersampling='1.5';a=f.f.render('gtao_supersampling',m);assert np.isfinite(a).all()
  result['parallax_exclusion_supersampling']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'gtao.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
