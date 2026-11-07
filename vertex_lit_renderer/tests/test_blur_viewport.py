import bpy,sys,pathlib,json,traceback,numpy as np,gpu,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import engine,material_shader,blur
out=repo.parent/'work/blur-tests';out.mkdir(exist_ok=True)
original=engine.VertexLitEngine.view_draw
stage=0;pending=False;done=False;frames=0;captures=[];counts=[];builds=[]
def finish(error=None):
 global done
 if done:return
 done=True;(out/'viewport.json').write_text(json.dumps({'pass':error is None,'error':error,'changes':counts,'builds':builds},indent=2));bpy.ops.wm.quit_blender()
def change():
 global stage,pending,frames
 try:
  m=bpy.data.materials['Parallax Test'];t=m.node_tree;b=t.nodes.get('Workbench 2.0 Blur');scale=t.nodes.get('Vector Math')
  if stage==0:b.radius=14
  elif stage==1:scale.inputs['Scale'].default_value=1.4
  elif stage==2:
   im=bpy.data.images['Viewport blur'];y,x=np.mgrid[:128,:128];h=(x//8%2).astype(np.float32);im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update()
  elif stage==3:
   cam=bpy.context.scene.camera;cam.location.x=-1.6;cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler()
  elif stage==4:b.strength=0
  elif stage==5:b.strength=1
  elif stage==6:
   bpy.ops.ed.undo_push(message='Blur before edit');b.radius=3;bpy.ops.ed.undo_push(message='Blur after edit')
  elif stage==7:bpy.ops.ed.undo()
  elif stage==8:bpy.ops.ed.redo()
  stage+=1;pending=False;frames=0
 except Exception:finish(traceback.format_exc())
def draw(self,context,dg):
 global pending,frames
 try:
  original(self,context,dg)
  if done or pending or self._geo_pending or self._mat_pending:return
  frames+=1
  if frames<3:return
  prog=material_shader.get_program(bpy.data.materials['Parallax Test']);assert not prog['failed'],prog['error']
  w,h=context.region.width,context.region.height
  buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');buf.dimensions=w*h*4
  px=np.asarray(buf).reshape(h,w,4).copy();assert np.isfinite(px).all()
  if captures:
   delta=np.max(abs(px[:,:,:3]-captures[-1][:,:,:3]),axis=2);count=int((delta>.005).sum());counts.append(count);assert count>100,(stage,count)
  if stage==4:assert blur.stats['builds']==builds[-1],'Camera rebuilt cache'
  if stage==8:assert abs(px-captures[6]).max()<.002,'Undo did not restore blur'
  if stage==9:assert abs(px-captures[7]).max()<.002,'Redo did not restore blur'
  builds.append(blur.stats['builds']);captures.append(px);pending=True
  if stage<9:bpy.app.timers.register(change,first_interval=.15)
  else:bpy.app.timers.register(lambda:finish(),first_interval=.15)
 except Exception:
  error=traceback.format_exc();pending=True;bpy.app.timers.register(lambda:finish(error),first_interval=.1)
engine.VertexLitEngine.view_draw=draw
def begin():
 ob,m,p,scale,offset=f.setup();p.depth=0
 t=m.node_tree;im=bpy.data.images.new('Viewport blur',width=128,height=128,float_buffer=True);im.colorspace_settings.name='Non-Color'
 y,x=np.mgrid[:128,:128];h=((x//16+y//16)%2).astype(np.float32);im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update()
 tex=t.nodes.new('ShaderNodeTexImage');tex.image=im;t.links.new(scale.outputs[0],tex.inputs[0])
 b=t.nodes.new('VLRShaderNodeBlur');b.name='Workbench 2.0 Blur';b.resolution='128';b.radius=4
 t.links.new(tex.outputs['Color'],b.inputs[0]);t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.region_3d.view_perspective='CAMERA';a.spaces.active.overlay.show_overlays=False;a.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.15)
def pump():
 if done:return
 for a in bpy.context.screen.areas:a.tag_redraw()
 return .15
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('Timeout') if not done else None,first_interval=50)
