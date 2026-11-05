import bpy,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from vertex_lit_renderer import planar
planar.register()
planar._PENDING.append(bpy.context.object);generation=planar._GENERATION
bpy.ops.wm.read_factory_settings(use_empty=True)
assert not planar._PENDING and planar._GENERATION>generation
assert planar._cancel_pending in bpy.app.handlers.load_pre
planar._PENDING.append(None);generation=planar._GENERATION
planar.unregister()
assert not planar._PENDING and planar._GENERATION>generation
assert planar._cancel_pending not in bpy.app.handlers.load_pre
planar.register();planar.unregister()
print('PASS pending bakes cancelled on file replacement and unregister; handler removed cleanly')
