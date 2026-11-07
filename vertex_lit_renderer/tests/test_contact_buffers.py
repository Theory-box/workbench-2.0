"""GPU regression for far-plane depth, conservative masking and buffer lifecycle."""
import sys,pathlib,json,traceback
import bpy,gpu,numpy as np
from mathutils import Matrix
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
from vertex_lit_renderer.fx.contact import ContactShadows
from vertex_lit_renderer.fx.gbuffer import GBuffer
out=repo.parent/'work/parallax-tests';out.mkdir(exist_ok=True)

def run():
 result={}
 try:
  size=64
  def tex(a,fmt):return gpu.types.GPUTexture((size,size),format=fmt,data=gpu.types.Buffer('FLOAT',a.shape,a))
  color=np.ones((size,size,4),dtype=np.float32);sun=color.copy()
  depth=np.full((size,size),.9999995,dtype=np.float32);depth[:,32:36]=.9
  c=tex(color,'RGBA32F');s=tex(sun,'RGBA32F');d=tex(depth,'R32F')
  target=gpu.types.GPUTexture((size,size),format='RGBA32F');fb=gpu.types.GPUFrameBuffer(color_slots=(target,))
  effect=ContactShadows();proj=Matrix.Diagonal((1.,1.,-.2,1.))
  ctx={'sun_tex':s,'proj':proj,'inv_proj':proj.inverted(),'contact_sun_dir':(1,0,1),
       'contact_length':1.,'contact_thickness':1.,'contact_steps':64}
  def draw():
   with fb.bind():
    gpu.state.viewport_set(0,0,size,size);gpu.state.blend_set('NONE');gpu.state.depth_test_set('NONE')
    effect.run(c,d,ctx);b=fb.read_color(0,0,size,size,4,0,'FLOAT');b.dimensions=size*size*4
    return np.asarray(b).reshape(size,size,4).copy()
  pixels=draw();count=int((pixels[:,:32,0]<.9).sum());result['far_depth_shadow_pixels']=count
  assert count>100,count
  depth[:]=1;d=tex(depth,'R32F');assert np.max(abs(draw()-color))<1e-5
  result['background_unchanged']=True
  depth[:]=.9999995;depth[:,32:36]=.9;d=tex(depth,'R32F')
  sun[:,:,3]=.75;ctx['sun_tex']=tex(sun,'RGBA32F');assert np.max(abs(draw()-color))<1e-5
  sun[:,:,:3]=0;sun[:,:,3]=1;ctx['sun_tex']=tex(sun,'RGBA32F');assert np.max(abs(draw()-color))<1e-5
  result['alpha_and_no_sun_unchanged']=True
  g=GBuffer()
  for w,h in ((32,32),(64,16),(32,32)):
   g.ensure(w,h,contact=True)
   assert g.sun is not None and g.aux
   with g.fb.bind():
    g.fb.clear(color=(0,0,0,0),depth=1)
    g.fb.read_color(0,0,1,1,4,3,'FLOAT')
   g.ensure(w,h,contact=False);assert g.sun is None
  g.free();assert g.fb is None and g.sun is None and g.normal_fb is None
  result['resize_toggle_free']=True;effect.free();result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (out/'contact_buffers.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
