import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def setup():
 ob,m,n,scale,offset=f.setup();t=m.node_tree
 base=t.nodes.get('Principled BSDF').inputs['Base Color'];t.links.remove(base.links[0]);base.default_value=(.7,.7,.7,1)
 tex=t.nodes.new('ShaderNodeTexImage');im=bpy.data.images.new('ridge',width=128,height=128,float_buffer=True);im.colorspace_settings.name='Non-Color'
 y,x=np.mgrid[:128,:128];h=np.where((x>56)&(x<72),.9,.1).astype(np.float32)
 im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update();tex.image=im;tex.interpolation='Closest'
 t.links.new(t.nodes.get('UV Map').outputs[0],tex.inputs[0]);t.links.new(tex.outputs[0],n.inputs['Height']);n.depth=.4;n.shadow_steps=64
 sc=bpy.context.scene;sc.camera.location=(0,0,4);sc.camera.rotation_euler=(0,0,0);s=sc.vertex_lit;s.sun_intensity=1;s.sun_elevation=.4;s.sun_azimuth=1.570796;s.hemi_intensity=.15
 return ob,m,n

def run():
 result={}
 try:
  ob,m,n=setup();s=bpy.context.scene.vertex_lit
  n.self_shadow=False;a=f.render('sun_unshadowed',m);n.self_shadow=True;b=f.render('sun_shadowed',m)
  mask=(a[:,:,3]>.9)&(b[:,:,3]>.9);d=(a[:,:,:3]-b[:,:,:3]).mean(axis=2);count=int((d[mask]>.1).sum());assert count>100,count
  assert d[mask].min()>-.002
  result['shadowed_pixels']=count
  s.sun_azimuth=-1.570796;c=f.render('sun_reversed',m);assert abs(b-c).max()>.1
  s.sun_intensity=0;n.self_shadow=False;a=f.render('ambient_off',m);n.self_shadow=True;b=f.render('ambient_on',m);assert abs(a-b).max()<.0001
  result['ambient_unchanged']=True
  s.sun_intensity=1;n.depth=0;n.self_shadow=False;a=f.render('flat_off',m);n.self_shadow=True;b=f.render('flat_on',m);assert abs(a-b).max()<.0001
  result['zero_depth_unchanged']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.out/'sun.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
