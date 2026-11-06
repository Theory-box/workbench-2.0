import bpy,bmesh,sys,pathlib,json,traceback,numpy as np,gpu
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import engine
engine._KEEP_CPU_ARRAYS=True
original=engine.VertexLitEngine.view_draw
stage=0;pending=False;done=False;captures=[]
out=repo.parent/'work/steady-edit-regression.json'
steady=[];flags=[]
def finish(error=None):
 global done
 if not error and (len(flags)<3 or not all(flags)):error='Fast geometry buffers lost during idle Edit Mode'
 if not error and np.max(abs(steady[0]-steady[-1]))>.001:error='Pixels changed after edit stopped'
 done=True;out.write_text(json.dumps({'error':error,'frames':len(steady),'cache_has_vbo':flags,'pixel_delta':float(np.max(abs(steady[0]-steady[-1]))) if len(steady)>1 else None,'changed_pixels':int(np.count_nonzero(np.max(abs(steady[0][:,:,:3]-steady[-1][:,:,:3]),axis=2)>.02)) if len(steady)>1 else None}));bpy.ops.wm.quit_blender()
def edit():
 global stage,pending
 try:
  t=bpy.data.materials['UV gradient'].node_tree
  if stage<2:t.nodes.get('Vector Math').inputs['Scale'].default_value*=2
  elif stage==2:t.nodes.get('UV Map').uv_map='Editing UV'
  elif stage==3:
   t.nodes.get('UV Map').uv_map='UVMap'
   bpy.ops.object.mode_set(mode='EDIT')
   bm=bmesh.from_edit_mesh(bpy.context.object.data);uv=bm.loops.layers.uv.get('UVMap')
   for face in bm.faces:
    for loop in face.loops:loop[uv].uv*=.25
   bmesh.update_edit_mesh(bpy.context.object.data,loop_triangles=False,destructive=False)
  stage+=1;pending=False
 except Exception:finish(traceback.format_exc())
def draw(self,context,dg):
 global pending
 try:
  original(self,context,dg)
  if stage==4 and not done:
   w,h=context.region.width,context.region.height
   buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');buf.dimensions=w*h*4
   steady.append(np.asarray(buf).reshape(h,w,4).copy());flags.append('vbo' in self._mesh_cache.get('UV Test',{}))
  if done or pending or self._geo_pending:return
  data=self._mesh_cache.get('UV Test')
  if not data or 'uv' not in data:return
  expected=10
  if abs(float(data['uv'].max())-expected)>.001:return
  w,h=context.region.width,context.region.height
  buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');buf.dimensions=w*h*4
  pixels=np.asarray(buf).reshape(h,w,4).copy()
  if captures:
   delta=np.max(abs(pixels[:,:,:3]-captures[-1][:,:,:3]),axis=2)
   assert np.count_nonzero(delta>.02)>100, 'UV buffers changed but visible gradient did not'
  captures.append(pixels)
  prog=engine.material_shader.get_program(bpy.data.materials['UV gradient'])
  assert not prog['failed'] and 'vNamedUV0' in prog['frag']
  pending=True
  if stage<4:bpy.app.timers.register(edit,first_interval=.2)
  else:bpy.app.timers.register(lambda:finish(),first_interval=2)
 except Exception:
  error=traceback.format_exc();bpy.app.timers.register(lambda:finish(error),first_interval=.1)
engine.VertexLitEngine.view_draw=draw
def begin():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.mesh.primitive_plane_add();bpy.context.object.name='UV Test'
 m=bpy.data.materials.new('UV gradient');m.use_nodes=True;bpy.context.object.data.materials.append(m)
 t=m.node_tree;tc=t.nodes.new('ShaderNodeUVMap');tc.uv_map='UVMap';g=t.nodes.new('ShaderNodeTexGradient');vm=t.nodes.new('ShaderNodeVectorMath');vm.operation='SCALE';vm.inputs['Scale'].default_value=.25
 t.links.new(tc.outputs['UV'],vm.inputs[0]);t.links.new(vm.outputs['Vector'],g.inputs['Vector']);t.links.new(g.outputs['Color'],t.nodes.get('Material Output').inputs['Surface'])
 primary=bpy.context.object.data.uv_layers.active
 secondary=bpy.context.object.data.uv_layers.new(name='Editing UV')
 for item in secondary.data:item.uv*=10
 bpy.context.object.data.uv_layers.active=secondary;secondary.active_render=True
 bpy.context.scene.render.engine='VERTEX_LIT'

 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.2)
def pump():
 if done:return
 for a in bpy.context.screen.areas:a.tag_redraw()
 return .2
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('Timeout: UV buffers did not refresh') if not done else None,first_interval=25)
