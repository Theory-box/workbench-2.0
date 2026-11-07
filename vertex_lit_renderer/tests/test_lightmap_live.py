import bpy,pathlib,importlib.util,json,traceback,numpy as np
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_sun.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
result={}
def run():
 try:
  ob,m,n=f.setup();s=bpy.context.scene.vertex_lit
  image=bpy.data.images.new('Constant bounce',width=8,height=8,float_buffer=True);image.colorspace_settings.name='Non-Color';image.pixels.foreach_set(np.tile(np.array((.2,.2,.2,1),dtype=np.float32),64));image.update()
  assert ob.vlr_lightmap_settings.keep_live_lighting
  n.self_shadow=False;plain=f.f.render('live_plain',m)
  n.self_shadow=True;shadow=f.f.render('live_shadow',m)
  ob.vlr_lightmap.image=image;ob.vlr_lightmap.uv_name='UVMap';ob.update_tag(refresh={'DATA'})
  n.self_shadow=False;lit=f.f.render('bounce_plain',m)
  n.self_shadow=True;shaded=f.f.render('bounce_shadow',m)
  mask=(plain[:,:,3]>.99)&(shaded[:,:,3]>.99)
  assert abs((lit-shaded)[mask]-(plain-shadow)[mask]).max()<.002
  assert np.count_nonzero((lit-shaded)[:,:,:3].max(axis=2)>.1)>100
  assert np.median((shaded-shadow)[mask,:3])>.1
  s.sun_intensity=0;no_sun=f.f.render('bounce_no_sun',m);assert abs(no_sun-shaded).max()>.05
  s.sun_intensity=1;ob.vlr_lightmap_settings.keep_live_lighting=False
  replacement=f.f.render('bounce_replace',m)
  s.sun_intensity=0;replacement2=f.f.render('bounce_replace_no_sun',m);assert abs(replacement-replacement2).max()<1e-5
  ob.vlr_lightmap_settings.keep_live_lighting=True;s.sun_intensity=1
  restored=f.f.render('bounce_restore',m);assert abs(restored-shaded).max()<1e-5
  result['sun_self_shadow_additive_and_replace']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'lightmap_live.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
