import bpy,sys,pathlib
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from vertex_lit_renderer import planar
planar.register()
bpy.ops.mesh.primitive_plane_add();obj=bpy.context.object
planar._PENDING.append(obj);bpy.data.objects.remove(obj,do_unlink=True)
planar.process_pending(SimpleNamespace(),bpy.context,bpy.context.evaluated_depsgraph_get())
assert not planar._PENDING
planar.unregister()
print('PASS deleted queued object does not interrupt viewport drawing')
