import bpy,bmesh,sys,pathlib,json,traceback,numpy as np,gpu
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import engine
engine._KEEP_CPU_ARRAYS=True
original=engine.VertexLitEngine.view_draw
stage=0;pending=False;done=False;captures=[]
out=repo.parent/'work/lightmap-tests/gradient-viewport.json'
def finish(error=None):
 global done
 done=True;out.write_text(json.dumps({'pass':error is None,'error':error}));bpy.ops.wm.quit_blender()
def edit():
 global stage,pending
 try:
  bpy.data.materials['UV gradient'].node_tree.nodes.get('Vector Math').inputs['Scale'].default_value*=2
  stage+=1;pending=False
 except Exception:finish(traceback.format_exc())
def draw(self,context,dg):
 global pending
 try:
  original(self,context,dg)
  if done or pending or self._geo_pending:return
  data=self._mesh_cache.get('UV Test')
  if not data or 'uv' not in data:return
  expected=1
  if abs(float(data['uv'].max())-expected)>.001:return
  w,h=context.region.width,context.region.height
  buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'FLOAT');buf.dimensions=w*h*4
  pixels=np.asarray(buf).reshape(h,w,4).copy()
  if captures:
   delta=np.max(abs(pixels[:,:,:3]-captures[-1][:,:,:3]),axis=2)
   assert np.count_nonzero(delta>.02)>100, 'UV buffers changed but visible gradient did not'
  captures.append(pixels)
  prog=engine.material_shader.get_program(bpy.data.materials['UV gradient'])
  assert not prog['failed'] and 'vec4(vUV, 0.0, 1.0)' in prog['frag']
  pending=True
  if stage<2:bpy.app.timers.register(edit,first_interval=.2)
  else:bpy.app.timers.register(lambda:finish(),first_interval=.2)
 except Exception:
  error=traceback.format_exc();bpy.app.timers.register(lambda:finish(error),first_interval=.1)
engine.VertexLitEngine.view_draw=draw
def begin():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.mesh.primitive_plane_add();bpy.context.object.name='UV Test'
 m=bpy.data.materials.new('UV gradient');m.use_nodes=True;bpy.context.object.data.materials.append(m)
 t=m.node_tree;tc=t.nodes.new('ShaderNodeUVMap');g=t.nodes.new('ShaderNodeTexGradient');vm=t.nodes.new('ShaderNodeVectorMath');vm.operation='SCALE';vm.inputs['Scale'].default_value=.25
 t.links.new(tc.outputs['UV'],vm.inputs[0]);t.links.new(vm.outputs['Vector'],g.inputs['Vector']);t.links.new(g.outputs['Fac'],t.nodes.get('Principled BSDF').inputs['Base Color'])
 bpy.context.scene.render.engine='VERTEX_LIT'
 bpy.ops.wm.save_as_mainfile(filepath=str(repo.parent/'outputs/uv-scale-gradient-test.blend'))
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(pump,first_interval=.2)
def pump():
 if done:return
 for a in bpy.context.screen.areas:a.tag_redraw()
 return .2
bpy.app.timers.register(begin,first_interval=.5)
bpy.app.timers.register(lambda:finish('Timeout: UV buffers did not refresh') if not done else None,first_interval=25)
