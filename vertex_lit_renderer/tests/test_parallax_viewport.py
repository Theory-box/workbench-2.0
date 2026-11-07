import bpy,sys,pathlib,json,traceback,numpy as np,gpu,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('parallax_fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from vertex_lit_renderer import engine,material_shader
original=engine.VertexLitEngine.view_draw
out=fixture.out
stage=0;pending=False;done=False;captures=[];stats=[];frames=0;programs=[]

def finish(error=None):
 global done
 if done:return
 done=True;(out/'viewport.json').write_text(json.dumps({'pass':error is None,'error':error,'changes':stats},indent=2));bpy.ops.wm.quit_blender()

def change():
 global stage,pending,frames
 try:
  if stage==0:node.depth=.35
  elif stage==1:scale.inputs['Scale'].default_value=1.1
  elif stage==2:node.mute=True
  elif stage==3:node.mute=False;node.uv_map='Other'
  elif stage==4:node.uv_map='UVMap'
  elif stage==5:
   bpy.context.scene.camera.location.x=-1.6
   cam=bpy.context.scene.camera;cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler()
  elif stage==6:
   import bmesh
   bpy.ops.object.mode_set(mode='EDIT');bm=bmesh.from_edit_mesh(ob.data);uv=bm.loops.layers.uv.get('UVMap')
   for face in bm.faces:
    for loop in face.loops:loop[uv].uv*=.5
   bmesh.update_edit_mesh(ob.data,loop_triangles=False,destructive=False)
  elif stage==7:
   bpy.ops.object.mode_set(mode='OBJECT')
   im=bpy.data.images.new('Viewport height',width=32,height=32,float_buffer=True);im.colorspace_settings.name='Non-Color'
   y,x=np.mgrid[:32,:32];h=((x//4+y//4)%2).astype(np.float32)
   im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update()
   tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im
   mat.node_tree.links.new(scale.outputs[0],tex.inputs[0]);mat.node_tree.links.new(tex.outputs['Color'],node.inputs['Height'])
  stage+=1;pending=False;frames=0
 except Exception:finish(traceback.format_exc())

def draw(self,context,dg):
 global pending,frames
 try:
  original(self,context,dg)
  if done or pending or self._geo_pending or self._mat_pending:return
  frames+=1
  if frames<3:return
  prog=material_shader.get_program(mat)
  assert not prog['failed'],prog['error']
  if stage in (1,2):assert id(prog['shader'])==programs[-1], 'Value edit recompiled shader'
  programs.append(id(prog['shader']))
  w,h=context.region.width,context.region.height
  buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');buf.dimensions=w*h*4
  px=np.asarray(buf).reshape(h,w,4).copy();assert np.isfinite(px).all()
  if captures:
   delta=np.max(abs(px[:,:,:3]-captures[-1][:,:,:3]),axis=2)
   count=int(np.count_nonzero(delta>.005));stats.append({'stage':stage,'pixels_changed':count});assert (count==0 if stage==4 else count>100),(stage,count)
  captures.append(px);pending=True
  if stage<8:bpy.app.timers.register(change,first_interval=.1)
  else:bpy.app.timers.register(lambda:finish(),first_interval=.1)
 except Exception:
  error=traceback.format_exc();bpy.app.timers.register(lambda:finish(error),first_interval=.1)
engine.VertexLitEngine.view_draw=draw

def begin():
 global ob,mat,node,scale,offset
 ob,mat,node,scale,offset=fixture.setup();node.depth=0
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':
   a.spaces.active.region_3d.view_perspective='CAMERA';a.spaces.active.overlay.show_overlays=False;a.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.15)

def pump():
 if done:return
 for a in bpy.context.screen.areas:a.tag_redraw()
 return .15
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('Viewport timeout') if not done else None,first_interval=45)
