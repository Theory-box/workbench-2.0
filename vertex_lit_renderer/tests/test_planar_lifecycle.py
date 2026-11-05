import bpy,sys,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from vertex_lit_renderer import planar
planar.register()
bpy.ops.mesh.primitive_cube_add();a=bpy.context.object
b=bpy.data.objects.new('Linked',a.data);bpy.context.collection.objects.link(b)
m=bpy.data.materials.new('Shared');a.data.materials.append(m)
bpy.ops.object.camera_add();camera=bpy.context.object
planar.configure_faces(a,[0],camera)
assert planar.configured_faces(a)==[0]
assert b.vlr_planar.faces==''
assert a.data is b.data and a.data.materials[0] is m
image=bpy.data.images.new('Bake',8,8);a.vlr_planar.image=image
try:planar.configure_faces(a,[0,1],camera);raise AssertionError()
except ValueError:pass
assert a.vlr_planar.image is image and planar.configured_faces(a)==[0]
revision=a.vlr_planar.revision
planar.clear_reflection(a)
assert a.vlr_planar.revision!=revision
assert a.vlr_planar.image is None and not a.vlr_planar.faces
assert bpy.data.images.get('Bake') is image
planar.configure_faces(a,[0],camera)
# Persist to an isolated fixture only.
path=pathlib.Path(__file__).resolve().parents[3]/'work'/'planar-lifecycle.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
a=bpy.data.objects['Cube.001']
assert planar.configured_faces(a)==[0] and a.vlr_planar.camera is not None
planar.unregister()
print('PASS planar object isolation, failed reconfigure, clear, save/reopen')
