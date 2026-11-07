import bpy,pathlib,importlib.util,json,traceback,numpy as np
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_sun.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import material_shader
result={}
def run():
 try:
  ob,m,n=f.setup();s=bpy.context.scene.vertex_lit;t=m.node_tree;base=t.nodes.get('Principled BSDF').inputs['Base Color']
  base.default_value=(1,1,1,1);n.self_shadow=True
  reference=f.f.render('solid_white_reference',m)
  base.default_value=(.8,.01,.1,1);s.view_mode='SOLID';s.solid_color=(1,1,1)
  solid=f.f.render('solid_detail',m);assert abs(reference-solid).max()<.0001,float(abs(reference-solid).max())
  n.self_shadow=False;no_shadow=f.f.render('solid_no_shadow',m);assert np.count_nonzero(abs(solid-no_shadow).max(axis=2)>.05)>100
  n.self_shadow=True;s.solid_color=(.2,.5,.8);colored=f.f.render('solid_tinted',m)
  mask=solid[:,:,3]>.99;assert abs(colored[mask,:3]-solid[mask,:3]*np.array((.2,.5,.8))).max()<.002
  s.solid_surface_detail=False;flat=f.f.render('solid_flat',m);assert abs(flat-colored).max()>.1
  s.solid_surface_detail=True;s.view_mode='NORMAL';s.normal_space='WORLD'
  relief=f.f.render('normal_relief',m);n.depth=0;normal=f.f.render('normal_flat',m);assert abs(relief-normal).max()>.1
  # Bump shading must survive in Normal view independently of parallax.
  bump=t.nodes.new('ShaderNodeBump');sep=t.nodes.new('ShaderNodeSeparateXYZ');t.links.new(t.nodes.get('UV Map').outputs[0],sep.inputs[0]);t.links.new(sep.outputs['X'],bump.inputs['Height']);t.links.new(bump.outputs[0],t.nodes.get('Principled BSDF').inputs['Normal']);bump.inputs['Distance'].default_value=.5
  material_shader.mark_dirty(m.name);bumped=f.f.render('normal_bump',m);assert abs(bumped-normal).max()>.05
  s.normal_space='SCREEN';bpy.context.scene.camera.rotation_euler.z=.5;screen=f.f.render('normal_screen',m);assert abs(screen-bumped).max()>.02
  # Fallback/no-node colors also overridden.
  s.view_mode='SOLID';s.solid_color=(.2,.5,.8);m.use_nodes=False;m.diffuse_color=(1,0,0,1)
  fallback=f.f.render('solid_fallback',m);assert fallback[mask,2].mean()>fallback[mask,0].mean()
  result['pass']=True;result['checks']='white-reference, tint, detail toggle, self shadow, parallax normals, bump normals, screen normals, fallback'
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'solid_detail.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
