"""View-ray quality changes must reach GPU in F12 and viewport, including Blur heights."""
import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import material_shader

def setup():
 ob,m,n,scale,offset=f.setup();t=m.node_tree;n.depth=.35;n.self_shadow=False;n.self_ao=False
 im=bpy.data.images.new('Quality height',width=256,height=256,float_buffer=True);im.colorspace_settings.name='Non-Color'
 y,x=np.mgrid[:256,:256];h=((np.sin(x*.6)>0.8)*.8+.1).astype(np.float32)
 im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update()
 tex=t.nodes.new('ShaderNodeTexImage');tex.image=im;t.links.new(t.nodes.get('UV Map').outputs[0],tex.inputs[0])
 blur=t.nodes.new('VLRShaderNodeBlur');blur.resolution='512';blur.radius=5.5;t.links.new(tex.outputs[0],blur.inputs[0]);t.links.new(blur.outputs[0],n.inputs['Height'])
 cam=bpy.context.scene.camera;cam.location=(2,0,1);cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.5
 return ob,m,n

def run():
 result={}
 try:
  ob,m,n=setup();n.steps=8;a=f.render('quality_8',m)
  p=material_shader.get_program(m);param=next(p for p in p['params'] if p.uniform=='uParallax_steps');assert param.value(m.node_tree)==8
  n.steps=128;b=f.render('quality_128',m);assert param.value(m.node_tree)==128
  count=int(np.count_nonzero(np.max(abs(a-b)[:,:,:3],axis=2)>.005));assert count>100,count;result['changed_pixels']=count
  n.steps=8;c=f.render('quality_8_restored',m);assert abs(a-c).max()<.001
  # At shallow depth with a smoothly blurred height, refinement can already converge at 12.
  n.depth=.03;n.steps=12;a=f.render('quality_shallow_12',m);n.steps=128;b=f.render('quality_shallow_128',m)
  result['shallow_changed_pixels']=int(np.count_nonzero(np.max(abs(a-b)[:,:,:3],axis=2)>.005));result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.out/'quality.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
