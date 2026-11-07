import bpy,pathlib,importlib.util,json,traceback,numpy as np
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_depth.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def run():
 result={}
 try:
  ob,m,n,cube=f.setup();n.depth=0;s=bpy.context.scene.vertex_lit;s.ao_ridge=0;s.ao_samples='32'
  # Distinct materials sharing the shader must receive independent AO weights.
  other=m.copy();other.name='Other AO';cube.data.materials[0]=other
  other.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.7,.04,.02,1)
  for method in ('SSAO','GTAO'):
   s.ao_method=method;s.use_ao=False;base=f.f.render('material_ao_base',m)
   s.use_ao=True;m.vlr_scene_ao=1;other.vlr_scene_ao=1;full=f.f.render('material_ao_full',m)
   m.vlr_scene_ao=0;zero=f.f.render('material_ao_zero',m)
   m.vlr_scene_ao=.5;half=f.f.render('material_ao_half',m)
   green=base[:,:,1]>base[:,:,0]*2
   assert ((full-zero)[:,:,:3][green]<-.01).any()
   assert abs(zero[green]-base[green]).max()<.003, (float(abs(zero[green]-base[green]).max()),int((abs(zero-base).max(axis=2)[green]>.003).sum()))
   assert abs(half[green]-(full[green]+zero[green])*.5).max()<.003
   red=base[:,:,0]>base[:,:,1]*2
   assert abs(full[red]-zero[red]).max()<.003
   result[method]='zero/full/half and independent materials passed'
  result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'material_ao.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)

