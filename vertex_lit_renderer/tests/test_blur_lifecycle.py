import bpy,sys,pathlib,json,traceback,numpy as np,gpu,importlib.util,time
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import blur,material_shader,bake
out=repo.parent/'work/blur-tests';out.mkdir(exist_ok=True)
def run():
 result={}
 try:
  ob,m,p,scale,offset=f.setup();p.depth=0;t=m.node_tree
  uv=t.nodes.get('UV Map');uv.uv_map=''
  b=t.nodes.new('VLRShaderNodeBlur');b.resolution='128';b.radius=8
  noise=t.nodes.new('ShaderNodeTexNoise');t.links.new(uv.outputs[0],noise.inputs[0]);t.links.new(noise.outputs['Fac'],b.inputs[0]);t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  # The general procedural graph is cached; a changed Noise input invalidates it.
  a=bake.bake_material_to_array(m,128);noise.inputs['Scale'].default_value=12;c=bake.bake_material_to_array(m,128);assert abs(a-c).max()>.1
  # RGB must not acquire dark fringes when blurring transparent red pixels.
  im=bpy.data.images.new('Alpha test',width=128,height=128,float_buffer=True);im.colorspace_settings.name='Non-Color'
  y,x=np.mgrid[:128,:128];alpha=(x>63).astype(np.float32);arr=np.stack([alpha,np.zeros_like(alpha),np.zeros_like(alpha),alpha],axis=-1)
  im.pixels.foreach_set(arr.ravel());im.update();tex=t.nodes.new('ShaderNodeTexImage');tex.image=im;t.links.new(tex.outputs['Color'],b.inputs[0])
  source=next(s.image for s in material_shader.build_material_frag(m)[2].samplers if getattr(s.image,'is_blur_source',False))
  blur.begin_frame();texture=blur.texture(source)
  with gpu.types.GPUFrameBuffer(color_slots=(texture,)).bind():
   buf=gpu.state.active_framebuffer_get().read_color(0,0,128,128,4,0,'FLOAT');buf.dimensions=128*128*4;px=np.array(buf).reshape(128,128,4)
  edge=(px[:,:,3]>.02)&(px[:,:,3]<.98);assert edge.sum()>100 and abs(px[edge,0]-1).max()<.002
  # Cache cap is respected; previously evicted nodes remain rebuildable.
  oldcap=blur._MAX_BYTES;blur._MAX_BYTES=128*128*8*2
  for i in range(4):
   n=t.nodes.new('VLRShaderNodeBlur');n.resolution='128';n.inputs[0].default_value=(i/4,.2,.4,1)
   t.links.new(n.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color']);bake.bake_material_to_array(m,32)
   assert blur.stats['bytes']<=blur._MAX_BYTES
  blur._MAX_BYTES=oldcap
  t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color']);b.extension='EXTEND'
  im.pack();before=f.render('blur_saved',m)
  bpy.ops.wm.save_as_mainfile(filepath=str(out/'blur-test.blend'))
  bpy.ops.wm.open_mainfile(filepath=str(out/'blur-test.blend'))
  m=bpy.data.materials['Parallax Test'];after=f.render('blur_reopened',m);assert abs(before-after).max()<1e-5
  result={'pass':True,'alpha_edge_pixels':int(edge.sum()),'cache_bytes':blur.stats['bytes']}
 except Exception:result['error']=traceback.format_exc()
 (out/'lifecycle.json').write_text(json.dumps(result,indent=2));print(result)
 bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender() and None,first_interval=.3)
bpy.app.timers.register(run,first_interval=.5)
