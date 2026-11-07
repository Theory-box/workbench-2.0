"""GPU/F12 relief AO, existing cavity integration, and isolation checks."""
import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util,time
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('sun_fixture',pathlib.Path(__file__).with_name('test_parallax_sun.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def setup():
 ob,m,n=f.setup();s=bpy.context.scene.vertex_lit;s.sun_intensity=0;s.hemi_intensity=1;s.use_ao=True;s.ao_radius=.35;s.ao_bias=.002;s.ao_strength=1;s.ao_samples='32';s.ao_ridge=0
 y,x=np.mgrid[:128,:128];h=(.1+.8*np.exp(-((x/128-.5)/.07)**2)).astype(np.float32)
 im=bpy.data.images.get('ridge');im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update()
 m.node_tree.nodes.get('Image Texture').interpolation='Linear'
 return ob,m,n

def run():
 result={}
 try:
  ob,m,n=setup();s=bpy.context.scene.vertex_lit
  n.self_ao=False;a=f.f.render('ao_disabled',m);n.self_ao=True;b=f.f.render('ao_enabled',m)
  mask=(a[:,:,3]>.99)&(b[:,:,3]>.99);mask[:60]=False;mask[196:]=False;mask[:,:60]=False;mask[:,196:]=False
  diff=(a[:,:,:3]-b[:,:,:3]).mean(axis=2)
  result['ao_pixels']=int((diff[mask]>.005).sum());assert result['ao_pixels']>100,result
  assert diff[mask].min()>-.001
  s.ao_ridge=1;c=f.f.render('ao_ridge',m);assert ((c[:,:,:3]-b[:,:,:3]).mean(axis=2)[mask]>.003).sum()>50
  s.ao_ridge=0;s.ao_strength=0;c=f.f.render('ao_strength_zero',m);assert abs(a-c).max()<.001
  s.ao_strength=1;s.use_ao=False;n.self_ao=False;a=f.f.render('ao_scene_off_node_off',m);n.self_ao=True;c=f.f.render('ao_scene_off_node_on',m);assert abs(a-c).max()<.001
  # Existing screen cavity must see relief normals, even with AO disabled.
  s.use_cavity=True;s.cavity_ridge=1;s.cavity_valley=1;c=f.f.render('relief_cavity',m)
  delta=(c[:,:,:3]-a[:,:,:3]).mean(axis=2)[mask]
  result['cavity_bright_pixels']=int((delta>.003).sum());result['cavity_dark_pixels']=int((delta<-.003).sum())
  assert result['cavity_bright_pixels']>50 and result['cavity_dark_pixels']>50,result
  s.cavity_ridge=0;s.cavity_valley=0;c=f.f.render('cavity_strength_zero',m);assert abs(a-c).max()<.001
  s.use_cavity=False;s.use_ao=True;ob.vlr_ao_exclude=True;n.self_ao=False;a=f.f.render('excluded_off',m);n.self_ao=True;c=f.f.render('excluded_on',m);assert abs(a-c).max()<.001;ob.vlr_ao_exclude=False
  n.depth=0;n.self_ao=False;a=f.f.render('ao_zero_depth_off',m);n.self_ao=True;c=f.f.render('ao_zero_depth_on',m);assert abs(a-c).max()<.001
  # A constant height has no local occlusion or convexity.
  n.depth=.4;t=m.node_tree;t.links.remove(n.inputs['Height'].links[0]);n.inputs['Height'].default_value=.3;s.ao_ridge=1
  n.self_ao=False;a=f.f.render('ao_constant_off',m);n.self_ao=True;c=f.f.render('ao_constant_on',m);assert abs(a-c).max()<.001
  assert c[0,0,3]==0.0, 'Post effects must preserve transparent film'
  result['isolation_checks']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'ao.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
