import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import blur,material_shader

def setup():
 ob,m,n,scale,offset=f.setup();n.depth=0
 for layer in ob.data.uv_layers:layer.active_render=(layer.name=='UVMap')
 for v in ob.data.uv_layers['UVMap'].data:v.uv=(v.uv.x*10.142263+17.542,v.uv.y*13.867487-4.5565)
 ob.data.update();scale.inputs['Scale'].default_value=1/64;offset.inputs[1].default_value=(.5,.5,.5)
 t=m.node_tree;b=t.nodes.new('VLRShaderNodeBlur');b.radius=4.43
 t.links.new(offset.outputs[0],b.inputs[0]);t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
 return ob,m,n,b

def run():
 result={}
 try:
  ob,m,n,b=setup();b.radius=0;a=f.render('uv_domain_direct',m);b.radius=4.43;c=f.render('uv_domain_blurred',m)
  mask=(a[:,:,3]>.99)&(c[:,:,3]>.99);err=float(abs(a[mask,:3]-c[mask,:3]).max());assert err<.003,err
  result['offset_uv_linear_error']=err
  # A single Blur shared by surface and height produces separate compiler sources.
  t=m.node_tree;t.links.new(b.outputs[0],n.inputs['Height']);n.depth=.2
  b.radius=0;a=f.render('uv_domain_shared_height_direct',m);b.radius=4.43;c=f.render('uv_domain_shared_height_blur',m)
  assert abs(a[mask,:3]-c[mask,:3]).max()<.004
  n.depth=0;b.radius=0;a=f.render('uv_domain_direct_again',m);b.radius=4.43
  # Nested Blur must use the same actual domain in its own cache pass.
  t=m.node_tree;outer=t.nodes.new('VLRShaderNodeBlur');outer.radius=3;t.links.new(b.outputs[0],outer.inputs[0]);t.links.new(outer.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  c=f.render('uv_domain_nested',m);assert abs(a[mask,:3]-c[mask,:3]).max()<.004
  # Live UV edits invalidate bounds as well as mesh data.
  for v in ob.data.uv_layers['UVMap'].data:v.uv.x-=40
  ob.data.update();b.radius=0;outer.radius=0;a=f.render('uv_domain_moved_direct',m);b.radius=4.43;outer.radius=3;c=f.render('uv_domain_moved_blur',m)
  assert abs(a[mask,:3]-c[mask,:3]).max()<.004
  result['negative_uv_edit_nested']=True
  # Shared material, distinct UV coverage: rebinding must happen for each object.
  ob.scale=(.5,.5,.5);ob.location.x=-.55
  other=ob.copy();other.data=ob.data.copy();bpy.context.scene.collection.objects.link(other);other.location.x=.55
  for v in other.data.uv_layers['UVMap'].data:v.uv.x+=30
  other.data.update()
  b.radius=0;outer.radius=0;a=f.render('uv_domain_shared_direct',m)
  b.radius=4.43;outer.radius=3;c=f.render('uv_domain_shared_blur',m)
  mask=(a[:,:,3]>.99)&(c[:,:,3]>.99);assert abs(a[mask,:3]-c[mask,:3]).max()<.004
  result['shared_material_domains']=True;result['cache_bytes']=blur.stats['bytes'];result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.out/'blur_domain.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
