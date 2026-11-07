import bpy,sys,pathlib,json,traceback,numpy as np,gpu
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import blur,material_shader,node_transpiler
out=repo.parent/'work/blur-tests';out.mkdir(exist_ok=True)
def source(mat):
 p=material_shader.get_program(mat)
 assert not p['failed'],p['error']
 return next(image for uni,image in p['samplers'] if getattr(image,'is_blur_source',False))
def read(src):
 blur.begin_frame();tex=blur.texture(src)
 with gpu.types.GPUFrameBuffer(color_slots=(tex,)).bind():
  b=gpu.state.active_framebuffer_get().read_color(0,0,tex.width,tex.height,4,0,'FLOAT');b.dimensions=tex.width*tex.height*4
  return np.array(b).reshape(tex.height,tex.width,4)
def run():
 result={}
 try:
  m=bpy.data.materials.new('Blur Test');m.use_nodes=True;t=m.node_tree
  tex=t.nodes.new('ShaderNodeTexImage');im=bpy.data.images.new('Input',width=128,height=128,float_buffer=True);im.colorspace_settings.name='Non-Color';tex.image=im
  y,x=np.mgrid[:128,:128];a=np.stack([(x>63)*.8+.1,(y>63)*.6+.2,np.ones_like(x)*.3,np.ones_like(x)],axis=-1).astype(np.float32)
  im.pixels.foreach_set(a.ravel());im.update()
  b=t.nodes.new('VLRShaderNodeBlur');b.resolution='128';b.radius=6
  t.links.new(tex.outputs['Color'],b.inputs[0]);t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  src=source(m);actual=read(src)
  expected=a.copy();sigma=2
  weights=np.exp(-.5*(np.arange(-6,7)/sigma)**2);weights/=weights.sum()
  for axis in (0,1):expected=sum(np.roll(expected,i,axis)*w for i,w in zip(range(-6,7),weights))
  error=float(abs(actual-expected).max());assert error<.002,error
  result['gaussian_error']=error
  builds=blur.stats['builds'];read(src);assert blur.stats['builds']==builds
  b.radius=12;changed=read(src);assert blur.stats['builds']==builds+1 and abs(changed-actual).max()>.03
  # In-place pixels with no depsgraph tag must invalidate the blur.
  a[:,:,:3]=(.2,.7,.4);im.pixels.foreach_set(a.ravel());im.update()
  changed=read(src);assert abs(changed-a).max()<.002,(changed[64,64].tolist(),blur.stats.copy())
  # A mixed graph, including upstream value changes.
  mix=t.nodes.new('ShaderNodeMixRGB');mix.inputs[0].default_value=.5;mix.inputs[2].default_value=(.8,.1,.6,1)
  t.links.new(tex.outputs['Color'],mix.inputs[1]);t.links.new(mix.outputs[0],b.inputs[0])
  src=source(m);first=read(src);mix.inputs[0].default_value=.9;second=read(src)
  assert abs(first-second).max()>.1
  # Nested blur nodes rebuild downstream when the inner graph/settings change.
  nested=t.nodes.new('VLRShaderNodeBlur');nested.resolution='128';t.links.new(b.outputs[0],nested.inputs[0]);t.links.new(nested.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  outer=source(m);first=read(outer);mix.inputs[0].default_value=.2;second=read(outer);assert abs(first-second).max()>.1
  # Zero radius/strength and muting are exact graph bypasses.
  nested.radius=0;b.radius=0
  p=material_shader.get_program(m);assert not p['has_blur']
  # Reject unsupported coordinate domains explicitly, preserving the original graph.
  nested.radius=4;noise=t.nodes.new('ShaderNodeTexNoise');t.links.new(noise.outputs['Fac'],nested.inputs[0])
  p=material_shader.get_program(m);assert not p['failed'] and not p['has_blur']
  assert blur._warnings
  result['invalidation_nested_bypass']=True;result['builds']=blur.stats['builds'];result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (out/'gpu.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
