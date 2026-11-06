"""GPU output comparison against Blender 4.4 gradient equations, RGBA32F."""
import bpy,gpu,numpy as np,pathlib,sys,json,traceback
from gpu_extras.batch import batch_for_shader
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
from vertex_lit_renderer import node_transpiler as nt
out=repo.parent/'work/gradient-tests.json'
def run():
 result={'checks':0,'max_error':0.0}
 try:
  size=32
  y,x=np.mgrid[:size,:size].astype(np.float32);x=(x+.5)/size;y=(y+.5)/size
  for mapped in (False,True):
   px=x*3-.75 if mapped else x;py=y*3-.75 if mapped else y
   for mode in ('LINEAR','QUADRATIC','EASING','DIAGONAL','RADIAL','SPHERICAL','QUADRATIC_SPHERE'):
    r=np.maximum(.999999-np.sqrt(px*px+py*py),0);t=np.clip(px,0,1)
    expected=np.clip({'LINEAR':px,'QUADRATIC':np.maximum(px,0)**2,'EASING':t*t*(3-2*t),'DIAGONAL':(px+py)/2,'RADIAL':np.arctan2(py,px)/(2*np.pi)+.5,'SPHERICAL':r,'QUADRATIC_SPHERE':r*r}[mode],0,1)
    for output in ('Fac','Color'):
     m=bpy.data.materials.new('Gradient test');m.use_nodes=True;tree=m.node_tree
     g=tree.nodes.new('ShaderNodeTexGradient');g.gradient_type=mode
     if mapped:
      tc=tree.nodes.new('ShaderNodeTexCoord');mp=tree.nodes.new('ShaderNodeMapping')
      mp.inputs['Scale'].default_value=(3,3,1);mp.inputs['Location'].default_value=(-.75,-.75,0)
      tree.links.new(tc.outputs['UV'],mp.inputs['Vector']);tree.links.new(mp.outputs['Vector'],g.inputs['Vector'])
     tree.links.new(g.outputs[output],tree.nodes.get('Principled BSDF').inputs['Base Color'])
     res=nt.transpile_material(m)
     assert not res.notes,res.notes
     vert='in vec2 pos; out vec2 vUV; out vec3 vGenerated; out vec3 vObjPos; out vec4 vColor; void main(){vUV=pos*.5+.5;vGenerated=vec3(vUV,0);vObjPos=vGenerated;vColor=vec4(1);gl_Position=vec4(pos,0,1);}'
     frag='in vec2 vUV;in vec3 vGenerated;in vec3 vObjPos;in vec4 vColor;out vec4 color;'+''.join(d+'\n' for d in res.param_decls)+res.helpers+res.glsl+'\nvoid main(){color=computeBaseColor(vUV);}'
     shader=gpu.types.GPUShader(vert,frag)
     batch=batch_for_shader(shader,'TRI_STRIP',{'pos':[(-1,-1),(1,-1),(-1,1),(1,1)]})
     target=gpu.types.GPUOffScreen(size,size,format='RGBA32F')
     with target.bind():
      gpu.state.viewport_set(0,0,size,size);gpu.state.blend_set('NONE');gpu.state.depth_test_set('NONE');shader.bind()
      for p in res.params:
       try:shader.uniform_float(p.uniform,p.value(tree))
       except ValueError:pass
      batch.draw(shader)
      buf=gpu.state.active_framebuffer_get().read_color(0,0,size,size,4,0,'FLOAT');buf.dimensions=size*size*4
      pixels=np.asarray(buf).reshape(size,size,4).copy()
     target.free()
     error=float(np.max(abs(pixels[:,:,:3]-expected[:,:,None])))
     assert np.isfinite(pixels).all() and error<.0001,(mode,output,mapped,error)
     result['max_error']=max(result['max_error'],error);result['checks']+=1
     bpy.data.materials.remove(m)
  result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 out.write_text(json.dumps(result,indent=2));print(result,flush=True);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
