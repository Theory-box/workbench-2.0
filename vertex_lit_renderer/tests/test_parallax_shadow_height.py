"""Shadow-height edits stay live and cannot change relief/AO or mutate depth."""
import bpy, pathlib, importlib.util, json, traceback, numpy as np
spec=importlib.util.spec_from_file_location('sun',pathlib.Path(__file__).with_name('test_parallax_sun.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import material_shader
def run():
 result={}
 try:
  ob,m,n=f.setup();s=bpy.context.scene.vertex_lit;n.depth=.1;n.shadow_steps=128
  assert n.shadow_height==1
  a=f.f.render('height_default',m);shader=material_shader.get_program(m)['shader']
  n.shadow_height=3;b=f.f.render('height_exaggerated',m)
  assert n.depth==np.float32(.1);assert shader is material_shader.get_program(m)['shader']
  count=int(((a-b)[:,:,:3].max(axis=2)>.05).sum());assert count>100,count
  result['additional_shadow_pixels']=count
  n.shadow_height=1;c=f.f.render('height_restored',m);assert abs(a-c).max()<1e-5
  n.shadow_height=0;a=f.f.render('height_zero',m)
  n.self_shadow=False;b=f.f.render('height_disabled',m);assert abs(a-b).max()<1e-5
  n.shadow_height=10;c=f.f.render('height_disabled_large',m);assert abs(b-c).max()<1e-5
  result['zero_and_disabled_match']=True
  n.self_shadow=True;s.sun_intensity=0;s.hemi_intensity=1;s.use_ao=True;s.use_cavity=True
  n.shadow_height=.2;a=f.f.render('height_ambient_low',m)
  n.shadow_height=10;b=f.f.render('height_ambient_high',m);assert abs(a-b).max()<1e-5
  result['relief_ao_cavity_unchanged']=True;result['live_uniform']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'shadow_height.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
