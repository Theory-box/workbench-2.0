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

import time
stage=0;deadline=time.monotonic()+45
out=root.parent/'work'/'planar-workflow.json'
def tick():
 global stage
 try:
  if time.monotonic()>deadline:raise RuntimeError('Bake workflow timeout')
  if stage==0:
   for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':area.spaces.active.shading.type='RENDERED';area.tag_redraw()
   bpy.ops.object.select_all(action='DESELECT');mirror.select_set(True);bpy.context.view_layer.objects.active=mirror
   bpy.ops.object.mode_set(mode='EDIT')
   assert bpy.ops.vertex_lit.planar_bake()=={'FINISHED'}
   bpy.ops.object.mode_set(mode='OBJECT');stage=1
  elif stage==1 and mirror.vlr_planar.image is not None:
   assert bpy.ops.vertex_lit.planar_bake()=={'FINISHED'};stage=2
  elif stage==2 and not planar._PENDING and mirror.vlr_planar.status.startswith('Baked'):
   path=root.parent/'work'/'planar-workflow.blend'
   bpy.ops.wm.save_as_mainfile(filepath=str(path))
   bpy.ops.wm.open_mainfile(filepath=str(path));stage=3
  elif stage==3:
   ob=bpy.data.objects['Plane'];assert ob.vlr_planar.image is not None and ob.vlr_planar.image.packed_file
   sc=bpy.context.scene;sc.render.image_settings.file_format='OPEN_EXR';sc.render.filepath=str(root.parent/'work'/'planar-workflow.exr')
   bpy.ops.render.render(write_still=True)
   im=bpy.data.images.load(sc.render.filepath,check_existing=False)
   a=np.asarray(im.pixels[:],dtype=np.float32).reshape(256,256,4)
   assert np.isfinite(a).all();np.save(root.parent/'work'/'planar-workflow.npy',a)
   bpy.context.view_layer.objects.active=ob
   assert bpy.ops.vertex_lit.planar_clear()=={'FINISHED'}
   assert ob.vlr_planar.image is None
   out.write_text(json.dumps({'pass':True,'operators':True,'save_reopen':True,'f12':True}))
   bpy.ops.wm.quit_blender();return
  return .3
 except Exception:
  out.write_text(json.dumps({'error':traceback.format_exc()}));print(traceback.format_exc());bpy.ops.wm.quit_blender()
bpy.app.timers.register(tick,first_interval=1,persistent=True)
