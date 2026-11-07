"""Cycles lightmap workflow/state isolation; run with Blender --background."""
import bpy,sys,pathlib,json,traceback,numpy as np
from math import pi
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import lightmap
out=repo.parent/'work/lightmap-tests';out.mkdir(parents=True,exist_ok=True)
result={}
try:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 sc=bpy.context.scene;sc.render.engine='VERTEX_LIT';sc.cycles.samples=17
 sc.vertex_lit.use_ao=True;sc.vertex_lit.use_cavity=True;sc.vertex_lit.use_outline=True
 sc.world.use_nodes=True;sc.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.1
 def material(name,color):
  m=bpy.data.materials.new(name);m.use_nodes=True
  m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*color,1)
  return m
 floor=material('Floor',(.8,.02,.02));wall=material('Shared blue wall',(.05,.1,.6))
 bpy.ops.mesh.primitive_plane_add(size=8);bpy.context.object.data.materials.append(floor)
 bpy.ops.mesh.primitive_plane_add(size=3,location=(-1.6,1,1.5),rotation=(pi/2,0,0));a=bpy.context.object;a.data.materials.append(wall)
 b=a.copy();sc.collection.objects.link(b);b.location.x=1.6
 untouched=a.copy();sc.collection.objects.link(untouched);untouched.location.x=10
 override=material('Object linked material',(.2,.4,.6));b.material_slots[0].link='OBJECT';b.material_slots[0].material=override
 original=a.data
 original_uv=np.array(original.uv_layers.active.data[:][0].uv) # capture all UVs below
 original_uv=np.empty(len(original.loops)*2,dtype=np.float32);original.uv_layers.active.data.foreach_get('uv',original_uv)
 bpy.ops.object.light_add(type='AREA',location=(0,-1,3));bpy.context.object.data.energy=300;bpy.context.object.data.size=2
 bpy.ops.object.select_all(action='DESELECT');a.select_set(True);b.select_set(True);bpy.context.view_layer.objects.active=a
 for target in (a,b):target.vlr_lightmap_settings.resolution='128';target.vlr_lightmap_settings.samples=8
 before_nodes=len(wall.node_tree.nodes);before_active=wall.node_tree.nodes.active
 before_bake=sc.render.bake.margin;before_materials=len(bpy.data.materials)
 assert bpy.ops.vertex_lit.lightmap_bake()=={'FINISHED'}
 assert a.data is not b.data and untouched.data is original
 assert len(a.data.uv_layers)==2 and len(b.data.uv_layers)==2
 for ob in (a,b):
  uv=np.empty(len(ob.data.loops)*2,dtype=np.float32);ob.data.uv_layers['UVMap'].data.foreach_get('uv',uv)
  assert np.array_equal(uv,original_uv)
  assert ob.data.uv_layers.active.name=='UVMap'
  assert ob.data.uv_layers['UVMap'].active_render
  assert ob.data.materials[0] is wall
  assert ob.vlr_lightmap.image.packed_file
  assert max(ob.vlr_lightmap.image.pixels[:])>0
 assert b.material_slots[0].link=='OBJECT' and b.material_slots[0].material is override
 assert a.vlr_lightmap.image is not b.vlr_lightmap.image
 assert untouched.vlr_lightmap.image is None
 assert len(wall.node_tree.nodes)==before_nodes and wall.node_tree.nodes.active==before_active
 assert len(bpy.data.materials)==before_materials
 assert sc.cycles.samples==17 and sc.render.engine=='VERTEX_LIT' and sc.render.bake.margin==before_bake
 assert sc.vertex_lit.use_ao and sc.vertex_lit.use_cavity and sc.vertex_lit.use_outline
 assert set(bpy.context.selected_objects)=={a,b} and bpy.context.active_object is a
 result['bake_and_state_restoration']=True
 old_image=a.vlr_lightmap.image;old_name=old_image.name
 assert bpy.ops.vertex_lit.lightmap_bake()=={'FINISHED'}
 assert bpy.data.images.get(old_name) is None and len(a.data.uv_layers)==2
 result['rebake_cleanup']=True
 before_mesh=a.data;before_image=a.vlr_lightmap.image;materials=len(bpy.data.materials);meshes=len(bpy.data.meshes);images=len(bpy.data.images)
 original_bake=lightmap._cycles_bake
 def fail(*args):raise RuntimeError('Injected bake failure')
 lightmap._cycles_bake=fail
 try:
  try:lightmap.bake_selected(bpy.context);raise AssertionError('Failure swallowed')
  except RuntimeError as e:assert 'Injected' in str(e)
 finally:lightmap._cycles_bake=original_bake
 assert a.data is before_mesh and a.vlr_lightmap.image is before_image
 assert (len(bpy.data.materials),len(bpy.data.meshes),len(bpy.data.images))==(materials,meshes,images)
 assert sc.render.engine=='VERTEX_LIT' and sc.cycles.samples==17 and sc.vertex_lit.use_ao
 result['failure_rollback']=True
 mod=a.modifiers.new('Test topology warning','ARRAY');mod.count=2
 try:
  try:lightmap.bake_selected(bpy.context);raise AssertionError('Topology-changing modifier not rejected')
  except ValueError as e:assert a.name in str(e) and 'apply topology-changing' in str(e)
 finally:a.modifiers.remove(mod)
 assert a.data is before_mesh and a.vlr_lightmap.image is before_image
 result['modifier_warning_without_mutation']=True
 saved_pixels=np.array(a.vlr_lightmap.image.pixels[:],dtype=np.float32)
 result['baked_rgb_max']=float(saved_pixels.reshape(-1,4)[:,:3].max())
 saved_name=a.name
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'workflow.blend'))
 bpy.ops.wm.open_mainfile(filepath=str(out/'workflow.blend'))
 restored=bpy.data.objects[saved_name].vlr_lightmap.image
 assert restored.packed_file
 result['packed_max_error']=float(abs(np.array(restored.pixels[:])-saved_pixels).max())
 assert result['packed_max_error']<.002
 result['save_reopen']=True;result['pass']=True
except Exception:result['error']=traceback.format_exc()
(out/'workflow.json').write_text(json.dumps(result,indent=2));print(result)
