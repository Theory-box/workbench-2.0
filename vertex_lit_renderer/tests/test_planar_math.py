import bpy,sys
from mathutils import Matrix,Vector
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from vertex_lit_renderer.planar import reflection_matrix,plane_from_faces
checks=0
for p,n in [((0,0,0),(0,0,1)),((2,3,4),(1,2,3))]:
 r=reflection_matrix(p,n);p=Vector(p);n=Vector(n).normalized();x=p+n*3
 assert (r@x-(p-n*3)).length<1e-5
 assert (r@(r@x)-x).length<1e-5
 assert (r@p-p).length<1e-5
 assert abs(r.to_3x3().determinant()+1)<1e-5
 checks+=4
bpy.ops.mesh.primitive_cube_add();o=bpy.context.object
p,n=plane_from_faces(o.data,Matrix.Diagonal((-2,3,.1,1)),[0]);checks+=1
try:plane_from_faces(o.data,Matrix.Identity(4),[0,1]);raise AssertionError('Noncoplanar faces accepted')
except ValueError:checks+=1
try:plane_from_faces(o.data,Matrix.Identity(4),[]);raise AssertionError('Empty selection accepted')
except ValueError:checks+=1
print('PASS',checks,'planar geometry checks')
