import bpy,pathlib,importlib.util,json,traceback,numpy as np
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import material_shader

def run():
 result={}
 try:
  ob,m,par,scale,offset=f.setup();t=m.node_tree;s=bpy.context.scene.vertex_lit
  s.hemi_intensity=.2;s.sun_intensity=1;s.sun_elevation=.6;s.sun_azimuth=-1.5
  p=t.nodes.get('Principled BSDF')
  for link in list(p.inputs['Base Color'].links):t.links.remove(link)
  p.inputs['Base Color'].default_value=(.7,.7,.7,1)
  bump=t.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.05
  noise=t.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=8
  t.links.new(noise.outputs['Fac'],bump.inputs['Height']);t.links.new(bump.outputs[0],p.inputs['Normal'])
  a=f.render('bump_parallax_noise',m)
  shader=material_shader.get_program(m)['shader'];bump.inputs['Strength'].default_value=0;b=f.render('bump_parallax_zero',m)
  assert abs(a-b).max()>.02;assert shader is material_shader.get_program(m)['shader']
  bump.inputs['Strength'].default_value=1;par.depth=0;c=f.render('bump_no_parallax',m)
  assert np.isfinite(c).all()
  image=bpy.data.images.new('Bump image',width=64,height=64,float_buffer=True);image.colorspace_settings.name='Non-Color'
  y,x=np.mgrid[:64,:64];h=(.5+.4*np.sin(x*.3)*np.sin(y*.3)).astype(np.float32)
  image.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());image.update()
  tex=t.nodes.new('ShaderNodeTexImage');tex.image=image;t.links.new(t.nodes.get('UV Map').outputs[0],tex.inputs[0]);t.links.new(tex.outputs[0],bump.inputs['Height'])
  a=f.render('bump_image',m);bump.inputs['Distance'].default_value=0;b=f.render('bump_image_zero',m);assert abs(a-b).max()>.02
  bump.inputs['Distance'].default_value=.05
  # Group input/output traversal for a Bump node's height and normal result.
  group=bpy.data.node_groups.new('Bump group','ShaderNodeTree');group.interface.new_socket(name='Height',in_out='INPUT',socket_type='NodeSocketFloat');group.interface.new_socket(name='Normal',in_out='OUTPUT',socket_type='NodeSocketVector')
  gi=group.nodes.new('NodeGroupInput');go=group.nodes.new('NodeGroupOutput');gb=group.nodes.new('ShaderNodeBump');gb.inputs['Distance'].default_value=.05
  group.links.new(gi.outputs['Height'],gb.inputs['Height']);group.links.new(gb.outputs[0],go.inputs[0])
  gn=t.nodes.new('ShaderNodeGroup');gn.node_tree=group;t.links.new(tex.outputs[0],gn.inputs[0]);t.links.new(gn.outputs[0],p.inputs['Normal'])
  c=f.render('bump_group',m);assert abs(a-c).max()<.002
  result['procedural_image_group_parallax_live_uniform']=True;result['pass']=True
  im=bpy.data.images.load(str(f.out/'bump_image.exr'),check_existing=False);bpy.context.scene.render.image_settings.file_format='PNG';im.save_render(str(f.out/'bump_image.png'));bpy.data.images.remove(im)
 except Exception:result['error']=traceback.format_exc()
 (f.out/'bump_integration.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
