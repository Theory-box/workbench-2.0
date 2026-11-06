import bpy,sys,pathlib,json
root=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'workbench-2.0'))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import engine
original=engine.VertexLitEngine.view_draw
active=None;before=None

def draw(self,c,d):
 global active
 original(self,c,d);active=self
engine.VertexLitEngine.view_draw=draw

def finish():
 data={'n_tris':sum(d.get('n_tris',0) for d in active._mesh_cache.values()) or None}
 result={'mesh_polygons':len(bpy.data.objects['EmptyProbe'].data.polygons),'cached_triangles':data.get('n_tris'),'batch_still_present':any(bool(batch) for batch in active._batch_dict.values()),'dirty':active._dirty}
 result['pass']=result['mesh_polygons']==0 and result['cached_triangles'] is None and not result['batch_still_present'] and not result['dirty']
 (root/'work/empty-instance-regression.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
def empty():
 ob=bpy.data.objects['EmptyProbe'];ob.data.clear_geometry();ob.data.update();ob.update_tag(refresh={'DATA'})
 bpy.app.timers.register(finish,first_interval=2)
def start():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.mesh.primitive_plane_add();bpy.context.object.name='EmptyProbe'
 ob=bpy.context.object;col=bpy.data.collections.new('Source');col.objects.link(ob)
 for c in list(ob.users_collection):
  if c!=col:c.objects.unlink(ob)
 inst=bpy.data.objects.new('Instance',None);bpy.context.scene.collection.objects.link(inst);inst.instance_type='COLLECTION';inst.instance_collection=col
 bpy.context.scene.render.engine='VERTEX_LIT'
 for a in bpy.context.screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.shading.type='RENDERED'
 bpy.app.timers.register(empty,first_interval=2)
bpy.app.timers.register(start,first_interval=.5)
