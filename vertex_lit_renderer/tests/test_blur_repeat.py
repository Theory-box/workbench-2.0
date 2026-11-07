"""Repeating textures keep their original tile resolution and share one cache."""
import bpy,sys,pathlib,json,traceback,numpy as np,gpu,importlib.util,time
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import blur,material_shader

def read(tex):
 with gpu.types.GPUFrameBuffer(color_slots=(tex,)).bind():
  buf=gpu.state.active_framebuffer_get().read_color(0,0,tex.width,tex.height,4,0,'FLOAT');buf.dimensions=tex.width*tex.height*4
  return np.array(buf).reshape(tex.height,tex.width,4)

def run():
 result={}
 try:
  ob,m,n,scale,offset=f.setup();n.depth=0;t=m.node_tree
  for layer in ob.data.uv_layers:layer.active_render=layer.name=='UVMap'
  im=bpy.data.images.new('fine stone test',width=512,height=512,float_buffer=True);im.colorspace_settings.name='Non-Color'
  y,x=np.mgrid[:512,:512];h=((x//3+y//5)%2).astype(np.float32);im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update()
  tex=t.nodes.new('ShaderNodeTexImage');tex.image=im;t.links.new(t.nodes.get('UV Map').outputs[0],tex.inputs[0])
  ramp=t.nodes.new('ShaderNodeValToRGB');t.links.new(tex.outputs[0],ramp.inputs[0])
  b=t.nodes.new('VLRShaderNodeBlur');b.radius=.5;t.links.new(ramp.outputs[0],b.inputs[0]);t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  p=material_shader.get_program(m);src=next(s for _,s in p['samplers'] if getattr(s,'is_blur_source',False))
  b.cache_space='TILE';blur.begin_frame();baseline=read(blur.texture(src))
  b.cache_space='AUTO';blur.clear();builds=blur.stats['builds'];start=time.perf_counter()
  objects=[ob]
  for i in range(1,8):
   other=ob.copy();other.data=ob.data.copy();bpy.context.scene.collection.objects.link(other);objects.append(other)
  for i,obj in enumerate(objects):
   for uv in obj.data.uv_layers['UVMap'].data:uv.uv=(uv.uv.x*(12+i)+17+i*9,uv.uv.y*(18+i)-5-i*3)
   obj.data.update()
  dg=bpy.context.evaluated_depsgraph_get()
  for frame in range(3):
   blur.begin_frame()
   for obj in objects:
    blur.set_object(obj,dg);actual=blur.texture(src)
    assert (actual.width,actual.height)==(512,512)
    assert src.domain==(0.,0.,1.,1.)
  error=float(abs(read(actual)-baseline).max());assert error==0,error
  assert blur.stats['builds']-builds==1,blur.stats
  result={'pixel_error_vs_original_tile':error,'objects':8,'frames':3,'cache_builds':blur.stats['builds']-builds,'cache_bytes':blur.stats['bytes'],'elapsed_seconds':time.perf_counter()-start}
  # Reproduce the previous all-object-bounds behavior for the same 24 draws.
  b.cache_space='OBJECT';blur.clear();oldbuilds=blur.stats['builds'];oldstart=time.perf_counter()
  for frame in range(3):
   blur.begin_frame()
   for obj in objects:
    blur.set_object(obj,dg);old=blur.texture(src)
  read(old) # synchronize GPU before reporting elapsed time
  result['expanded_cache_builds']=blur.stats['builds']-oldbuilds
  result['expanded_elapsed_seconds']=time.perf_counter()-oldstart
  result['expanded_texels_per_uv']=old.width/src.domain[2]
  assert result['expanded_cache_builds']>8
  b.cache_space='AUTO'
  # Integer UV scaling remains periodic; noninteger scaling is conservative.
  t.links.new(scale.outputs[0],tex.inputs[0]);scale.inputs['Scale'].default_value=3
  blur.begin_frame();assert blur.periodic_input(b.inputs[0])
  scale.inputs['Scale'].default_value=3.2;blur.begin_frame();assert not blur.periodic_input(b.inputs[0])
  result['mapping_proof']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.out/'blur_repeat.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
