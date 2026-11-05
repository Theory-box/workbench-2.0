import bpy,sys,pathlib
from mathutils import Vector,Matrix
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from vertex_lit_renderer.planar import reflected_camera
bpy.ops.object.camera_add(location=(0,0,3));cam=bpy.context.object
checks=0
for kind in ('PERSP','ORTHO'):
 cam.data.type=kind;cam.data.ortho_scale=5
 bpy.context.view_layer.update()
 proj=cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=512,y=512)
 view,clipped=reflected_camera(cam.matrix_world,proj,(0,0,0),(0,0,1))
 for z,visible in [(1,True),(-1,False)]:
  p=clipped@view@Vector((0,0,z,1))
  assert (-p.w<=p.z<=p.w)==visible,(kind,z,p)
  checks+=1
 for x in (-.5,0,.5):
  p=Vector((x,0,0,1));a=proj@cam.matrix_world.inverted()@p;b=clipped@view@p
  assert abs(a.x/a.w-b.x/b.w)<1e-5
  checks+=1
print('PASS',checks,'reflection clipping and surface projection checks')
