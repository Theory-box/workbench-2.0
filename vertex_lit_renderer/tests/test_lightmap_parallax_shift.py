import bpy,pathlib,importlib.util,json,traceback,numpy as np
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
result={}
def run():
 try:
  ob,m,n,scale,offset=f.setup();t=m.node_tree;bc=t.nodes.get('Principled BSDF').inputs['Base Color'];t.links.remove(bc.links[0]);bc.default_value=(1,1,1,1)
  image=bpy.data.images.new('Analytic lightmap',width=256,height=256,float_buffer=True);image.colorspace_settings.name='Non-Color'
  y,x=np.mgrid[:256,:256];v=(x+.5)/256;w=(y+.5)/256
  image.pixels.foreach_set(np.stack([v,w,.2+v*.3,np.ones_like(v)],axis=-1).astype(np.float32).ravel());image.update()
  lm=ob.data.uv_layers.new(name='LightUV');source=ob.data.uv_layers['UVMap']
  # Rotated, mirrored, anisotropic lightmap basis, distinct from parallax UVs.
  coords=[(.2+.4*u.uv.y,.8-.5*u.uv.x) for u in source.data]
  for uv,c in zip(lm.data,coords):uv.uv=c
  ob.vlr_lightmap.image=image;ob.vlr_lightmap.uv_name='LightUV';ob.vlr_lightmap_settings.keep_live_lighting=False
  n.depth=.2;actual=f.render('lm_shift_actual',m)
  n.depth=0;plain=f.render('lm_shift_plain',m)
  du=.1*1.6/3/2;dv=.1*-2/3/2
  for uv,c in zip(lm.data,coords):uv.uv=(c[0]+.4*dv,c[1]-.5*du)
  ob.data.update();ob.update_tag(refresh={'DATA'})
  expected=f.render('lm_shift_expected',m)
  mask=(actual[:,:,3]>.99)&(expected[:,:,3]>.99)
  error=float(abs(actual[mask]-expected[mask]).max());assert error<.003,error
  assert abs(actual[mask]-plain[mask]).max()>.005
  for uv,c in zip(lm.data,coords):uv.uv=c
  ob.data.update();ob.update_tag(refresh={'DATA'});n.depth=.2;bpy.context.scene.vertex_lit.use_parallax=False
  disabled=f.render('lm_shift_disabled',m);assert abs(disabled-plain).max()<.0001
  result.update({'pass':True,'analytic_max_error':error,'separate_rotated_uvs':True,'global_disable':True})
 except Exception:result['error']=traceback.format_exc()
 (f.out/'lightmap_parallax_shift.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
