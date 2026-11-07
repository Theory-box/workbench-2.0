import bpy,sys,pathlib,json,time,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import material_shader,blur,bake

def setup():
 ob,m,n,scale,offset=f.setup();n.depth=.06;n.steps=8;n.self_shadow=False;n.self_ao=False
 t=m.node_tree;noise=t.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=39.57;noise.inputs['Detail'].default_value=5.5;noise.inputs['Roughness'].default_value=.712
 t.links.new(t.nodes.get('UV Map').outputs[0],noise.inputs['Vector'])
 ramp=t.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.233
 t.links.new(noise.outputs['Fac'],ramp.inputs[0]);t.links.new(ramp.outputs[0],n.inputs['Height']);t.links.new(ramp.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
 return ob,m,n,ramp

def run():
 result={}
 try:
  ob,m,n,r=setup();start=time.perf_counter();p=material_shader.get_program(m);assert not p['failed'],p['error'];result['initial_compile_seconds']=time.perf_counter()-start
  shader=p['shader'];frag=p['frag'];a=f.render('ramp_initial',m);times=[]
  for i,value in enumerate((.31,.42,.57)):
   r.color_ramp.elements[0].position=value;material_shader.mark_dirty(m.name)
   start=time.perf_counter();q=material_shader.get_program(m);times.append(time.perf_counter()-start)
   assert q['shader'] is shader and q['frag']==frag
   b=f.render('ramp_position_'+str(i),m);assert (np.max(abs(a-b)[:,:,:3],axis=2)>.01).sum()>100;a=b
  r.color_ramp.elements[1].color=(.7,.2,.4,.4);material_shader.mark_dirty(m.name);q=material_shader.get_program(m);assert q['shader'] is shader
  b=f.render('ramp_color',m);assert abs(a-b).max()>.03
  result['live_update_seconds']=times
  # Adding a stop changes structure and must rebuild safely.
  r.color_ramp.elements.new(.8);material_shader.mark_dirty(m.name);q=material_shader.get_program(m);assert not q['failed'] and q['shader'] is not shader
  result['structural_recompile']=True
  # Ramp inside a blur: update the cached pixels without recompiling its source shader.
  t=m.node_tree;n.depth=0;bn=t.nodes.new('VLRShaderNodeBlur');bn.resolution='128';t.links.new(r.outputs[0],bn.inputs[0]);t.links.new(bn.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  a=bake.bake_material_to_array(m,32);entry=next(iter(blur._cache.values()));cached_shader=entry['shader'];builds=blur.stats['builds']
  r.color_ramp.elements[1].color=(.05,.8,.1,1);material_shader.mark_dirty(m.name);b=bake.bake_material_to_array(m,32)
  assert abs(a-b).max()>.02
  entry=next(iter(blur._cache.values()));assert entry['shader'] is cached_shader and blur.stats['builds']==builds+1
  result['blur_updates_without_source_compile']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.out/'ramp_live.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
