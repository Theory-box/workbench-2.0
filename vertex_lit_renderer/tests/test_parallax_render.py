"""Native GPU/F12 tests: analytic UV offsets, mapping, lightmaps and toggles."""
import bpy,sys,pathlib,json,traceback,numpy as np
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import material_shader
out=repo.parent/'work/parallax-tests';out.mkdir(exist_ok=True)

def setup():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.mesh.primitive_plane_add(size=2);ob=bpy.context.object;ob.name='Relief'
 other=ob.data.uv_layers.new(name='Other')
 for v in other.data:v.uv=(.15,.25)
 other.active_render=True
 m=bpy.data.materials.new('Parallax Test');m.use_nodes=True;ob.data.materials.append(m)
 t=m.node_tree;uv=t.nodes.new('ShaderNodeUVMap');uv.uv_map='UVMap'
 scale=t.nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=.7
 offset=t.nodes.new('ShaderNodeVectorMath');offset.operation='ADD'
 ramp=t.nodes.new('ShaderNodeTexGradient')
 t.links.new(uv.outputs['UV'],scale.inputs[0]);t.links.new(scale.outputs[0],offset.inputs[0]);t.links.new(offset.outputs[0],ramp.inputs[0]);t.links.new(ramp.outputs['Color'],t.nodes.get('Principled BSDF').inputs['Base Color'])
 node=t.nodes.new('VLRShaderNodeParallax');node.uv_map='UVMap';node.depth=.2;node.inputs['Height'].default_value=1
 t.links.new(node.outputs[0],t.nodes.get('Material Output').inputs['Displacement'])
 bpy.ops.object.camera_add(location=(1.6,-2,3));cam=bpy.context.object;cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=3.5
 sc=bpy.context.scene;sc.camera=cam;sc.render.engine='VERTEX_LIT';sc.render.resolution_x=256;sc.render.resolution_y=256;sc.render.resolution_percentage=100;sc.render.film_transparent=True;sc.render.image_settings.file_format='OPEN_EXR'
 s=sc.vertex_lit;s.use_ao=False;s.use_cavity=False;s.use_outline=False;s.aa_method='OFF';s.supersampling='1';s.key_intensity=0;s.sun_intensity=0;s.hemi_intensity=1
 bpy.context.view_layer.objects.active=ob;ob.select_set(True);cam.select_set(False)
 return ob,m,node,scale,offset

def render(name,m):
 sc=bpy.context.scene;sc.render.filepath=str(out/(name+'.exr'));bpy.ops.render.render(write_still=True)
 prog=material_shader.get_program(m)
 assert not prog['failed'],prog['error']
 im=bpy.data.images.load(sc.render.filepath,check_existing=False);px=np.array(im.pixels[:],dtype=np.float32).reshape(256,256,4);bpy.data.images.remove(im)
 assert np.isfinite(px).all()
 assert (px[:,:,3]>.5).sum()>5000
 return px

def run():
 result={}
 try:
  ob,m,node,scale,offset=setup()
  for factor in (.7,1.3,-.7):
   scale.inputs['Scale'].default_value=factor
   node.depth=.2;bias=.8 if factor<0 else 0;offset.inputs[1].default_value=(bias,0,0)
   actual=render('relief',m)
   node.depth=0;offset.inputs[1].default_value=(bias+factor*.1*1.6/3/2, factor*.1*-2/3/2,0)
   expected=render('reference',m)
   error=float(abs(actual-expected).max());assert error<.003,error
   result['analytic_scale_'+str(factor)]=error
  scale.inputs['Scale'].default_value=.7;offset.inputs[1].default_value=(0,0,0)
  baseline=render('baseline',m)
  node.depth=.2;node.mute=True;muted=render('muted',m);assert abs(baseline-muted).max()<1e-5
  node.mute=False
  t=m.node_tree;link=node.outputs[0].links[0];t.links.remove(link)
  disconnected=render('disconnected',m);assert abs(baseline-disconnected).max()<1e-5
  t.links.new(node.outputs[0],t.nodes.get('Material Output').inputs['Displacement'])
  # Height map is sampled through the same scaled UV graph, not object bounds.
  image=bpy.data.images.new('Height relief',width=64,height=64,float_buffer=True);image.colorspace_settings.name='Non-Color'
  y,x=np.mgrid[:64,:64];h=((x//8+y//8)%2).astype(np.float32)
  image.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());image.update()
  tex=t.nodes.new('ShaderNodeTexImage');tex.image=image;t.links.new(scale.outputs[0],tex.inputs['Vector']);t.links.new(tex.outputs['Color'],node.inputs['Height'])
  relief=render('heightmap',m);assert (abs(relief-baseline)[:,:,:3].max(axis=2)>.005).sum()>1000
  # Separate lightmap UV must remain stationary under parallax.
  lm=bpy.data.images.new('Lighting',width=16,height=16,float_buffer=True)
  y,x=np.mgrid[:16,:16];light=(x.astype(np.float32)+1)/16
  lm.pixels.foreach_set(np.stack([light,light,light,np.ones_like(light)],axis=-1).ravel());lm.update()
  ob.vlr_lightmap.image=lm;ob.vlr_lightmap.uv_name='UVMap';ob.update_tag(refresh={'DATA'})
  principled=t.nodes.get('Principled BSDF');t.links.remove(principled.inputs['Base Color'].links[0]);principled.inputs['Base Color'].default_value=(1,1,1,1)
  lit_on=render('lightmap_on',m);node.depth=0;lit_off=render('lightmap_off',m);assert abs(lit_on-lit_off).max()<1e-5
  result['toggles_heightmap_lightmap']=True
  ob.vlr_lightmap.image=None
  t.links.new(t.nodes.get('Gradient Texture').outputs['Color'],principled.inputs['Base Color'])
  result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (out/'render.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
