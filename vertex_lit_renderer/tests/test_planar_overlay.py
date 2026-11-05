import bpy,sys,pathlib,json,traceback,numpy as np
from mathutils import Vector
root=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import vertex_lit_renderer as addon
from vertex_lit_renderer import engine,planar
addon.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.render.engine='VERTEX_LIT';sc.render.resolution_x=256;sc.render.resolution_y=256
sc.vertex_lit.use_shadows=False;sc.vertex_lit.use_ao=False
bpy.ops.mesh.primitive_plane_add(size=6);mirror=bpy.context.object
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,1));cube=bpy.context.object
mat=bpy.data.materials.new('Red');mat.use_nodes=True;mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(1,.01,.01,1);cube.data.materials.append(mat)
bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,-.3));blocker=bpy.context.object
blockmat=bpy.data.materials.new('BehindMirror');blockmat.use_nodes=True
blockmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.01,1,.01,1);blocker.data.materials.append(blockmat)
bpy.ops.object.camera_add(location=(0,-4,3));camera=bpy.context.object;camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler();sc.camera=camera
planar.configure_faces(mirror,[0],camera);mirror.vlr_planar.resolution=256
mirror_mat=bpy.data.materials.new('Mirror');mirror_mat.use_nodes=True
mirror_mat.node_tree.nodes.get('Principled BSDF').inputs['Metallic'].default_value=1
mirror_mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=0
mirror.data.materials.append(mirror_mat)
original=engine.VertexLitEngine.view_draw;done=False
out=root.parent/'work'/'planar-overlay-result.json'
def draw(self,context,dg):
 global done
 original(self,context,dg)
 if done or self._dirty or getattr(self,'_mat_pending',False):return
 done=True
 result={}
 try:
  before={k:id(v) for k,v in self._mesh_cache.items()};cam=self._cam_pos;cull=self._cull
  pixels,vp=planar.capture(self,dg,mirror)
  assert before=={k:id(v) for k,v in self._mesh_cache.items()}
  assert cam==self._cam_pos and cull==self._cull
  assert np.isfinite(pixels).all()
  red=(pixels[:,:,0]>pixels[:,:,1]*2)&(pixels[:,:,0]>.1)
  assert red.sum()>10,'Red object missing from reflected capture'
  green=(pixels[:,:,1]>pixels[:,:,0]*2)&(pixels[:,:,1]>.1)
  assert green.sum()==0,'Geometry behind mirror leaked into capture'
  saved_draw=engine.VertexLitEngine._draw_batches
  def fail(*args,**kwargs):raise RuntimeError('Injected draw failure')
  engine.VertexLitEngine._draw_batches=fail
  try:
   try:planar.capture(self,dg,mirror);raise AssertionError('Failure swallowed')
   except RuntimeError as exc:assert 'Injected' in str(exc)
  finally:engine.VertexLitEngine._draw_batches=saved_draw
  assert self._cam_pos==cam and self._cull==cull
  planar._PENDING.append(mirror)
  planar.process_pending(self,context,dg)
  def verify_published():
   try:
    assert mirror.vlr_planar.image is not None,mirror.vlr_planar.status
    assert mirror.vlr_planar.image.packed_file is not None
    import gpu
    from vertex_lit_renderer import planar_overlay
    projection=camera.calc_matrix_camera(dg,x=256,y=256)
    view=camera.matrix_world.inverted()
    target=gpu.types.GPUOffScreen(256,256,format='RGBA16F')
    try:
     with target.bind():
      gpu.state.viewport_set(0,0,256,256)
      fb=gpu.state.active_framebuffer_get();fb.clear(color=(0,0,0,1),depth=1)
      planar_overlay.draw(self,dg,projection@view)
      buf=fb.read_color(0,0,256,256,4,0,'FLOAT');buf.dimensions=256*256*4
      overlay=np.array(buf).reshape(256,256,4)
      assert overlay[:,:,0].max()>.1,'Overlay has no reflected red object'
      original_signature=planar.topology_signature
      def unexpected_hash(*args):raise AssertionError('Unchanged reflection mesh was hashed again')
      planar.topology_signature=unexpected_hash
      try:planar_overlay.draw(self,dg,projection@view)
      finally:planar.topology_signature=original_signature

      np.save(root.parent/'work'/'planar-overlay.npy',overlay)
      rough_image=bpy.data.images.new('RoughMap',width=4,height=4,float_buffer=True)
      rough_image.colorspace_settings.name='Non-Color'
      rough_image.pixels.foreach_set(np.ones(64,dtype=np.float32));rough_image.update()
      node=mirror_mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=rough_image
      mirror_mat.node_tree.links.new(node.outputs['Color'],mirror_mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'])
      bpy.context.view_layer.update()
      fb.clear(color=(0,0,0,1),depth=1)
      planar_overlay.draw(self,bpy.context.evaluated_depsgraph_get(),projection@view)
      buf=fb.read_color(0,0,256,256,4,0,'FLOAT');buf.dimensions=256*256*4
      rough=np.array(buf).reshape(256,256,4)
      assert np.max(np.abs(rough-overlay))>.02,'Roughness map has no visible effect'
      np.save(root.parent/'work'/'planar-overlay-rough.npy',rough)
      output=mirror_mat.node_tree.nodes.get('Material Output')
      glass=mirror_mat.node_tree.nodes.new('ShaderNodeBsdfGlass')
      mirror_mat.node_tree.links.new(glass.outputs[0],output.inputs['Surface'])
      bpy.context.view_layer.update()
      fb.clear(color=(0,0,0,1),depth=1)
      planar_overlay.draw(self,bpy.context.evaluated_depsgraph_get(),projection@view)
      assert False in self._planar_overlay_cache.values(),'Unsupported graph did not disable overlay'
      mirror_mat.node_tree.links.new(mirror_mat.node_tree.nodes.get('Principled BSDF').outputs[0],output.inputs['Surface'])
      bpy.context.view_layer.update()
      planar_overlay.draw(self,bpy.context.evaluated_depsgraph_get(),projection@view)
      assert False not in self._planar_overlay_cache.values(),'Supported graph did not recover'


    finally:target.free()
    # Repeated successful publication must release the previous owned image.
    oldname=mirror.vlr_planar.image.name
    planar.publish_capture(mirror,pixels,vp)
    assert bpy.data.images.get(oldname) is None
    newname=mirror.vlr_planar.image.name
    planar.clear_reflection(mirror)
    assert bpy.data.images.get(newname) is None
    assert mirror.vlr_planar.image is None
    np.save(root.parent/'work'/'planar-capture.npy',pixels)
    result={'pass':True,'red_pixels':int(red.sum()),'geometry_cache_reused':True,'state_restored':True}
   except Exception:result={'error':traceback.format_exc()}
   out.write_text(json.dumps(result,indent=2));print(result,flush=True)
   bpy.ops.wm.quit_blender()
  bpy.app.timers.register(verify_published,first_interval=.2)
  return

 except Exception:result={'error':traceback.format_exc()}
 out.write_text(json.dumps(result,indent=2));print(result,flush=True)
 bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender() and None,first_interval=.2)
engine.VertexLitEngine.view_draw=draw
def begin():
 for area in bpy.context.screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.shading.type='RENDERED';area.tag_redraw()
bpy.app.timers.register(begin,first_interval=1)
bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender() and None,first_interval=30)
