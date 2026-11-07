"""Global controls: F12 off matches zero, on restores without changing materials."""
import bpy, pathlib, importlib.util, json, traceback
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_depth.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def run():
 result={}
 try:
  ob,m,n,cube=f.setup();s=bpy.context.scene.vertex_lit
  for toggle, owner, value in [('use_parallax',n,'depth'),('use_key_light',s,'key_intensity'),('use_sky_ground',s,'hemi_intensity'),('use_sun',s,'sun_intensity')]:
   if value!='depth':setattr(owner,value,1)
   saved=getattr(owner,value)
   a=f.f.render('toggle_on',m)
   setattr(s,toggle,False);b=f.f.render('toggle_off',m)
   assert getattr(owner,value)==saved
   setattr(s,toggle,True);c=f.f.render('toggle_restored',m)
   assert abs(a-c).max()<1e-5
   assert abs(a-b).max()>.01,toggle
   setattr(owner,value,0);d=f.f.render('toggle_zero',m)
   assert abs(b-d).max()<1e-5,toggle
   setattr(owner,value,saved);result[toggle]=True
  result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'global_toggles.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
