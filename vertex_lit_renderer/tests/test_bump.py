"""Bump normal output against Eevee, plus live-lighting normal consumption."""
import bpy,pathlib,importlib.util,json,traceback,numpy as np
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def setup():
 ob,m,par,scale,offset=f.setup();t=m.node_tree;t.nodes.remove(par)
 sc=bpy.context.scene;sc.eevee.taa_render_samples=1;s=sc.vertex_lit;s.sky_color=(1,1,1);s.ground_color=(1,1,1)
 sc.camera.location=(0,0,3);sc.camera.rotation_euler=(0,0,0)
 bump=t.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.5
 uv=t.nodes.get('UV Map');sep=t.nodes.new('ShaderNodeSeparateXYZ');t.links.new(uv.outputs[0],sep.inputs[0]);t.links.new(sep.outputs['X'],bump.inputs['Height'])
 t.links.new(bump.outputs[0],t.nodes.get('Principled BSDF').inputs['Normal'])
 return ob,m,bump,sep

def run():
 result={}
 try:
  ob,m,bump,sep=setup();t=m.node_tree;sc=bpy.context.scene;s=sc.vertex_lit
  output=t.nodes.get('Material Output');principled=t.nodes.get('Principled BSDF')
  encode=t.nodes.new('ShaderNodeVectorMath');encode.operation='MULTIPLY_ADD';encode.inputs[1].default_value=(.5,.5,.5);encode.inputs[2].default_value=(.5,.5,.5)
  t.links.new(bump.outputs[0],encode.inputs[0]);t.links.new(encode.outputs[0],output.inputs['Surface'])
  for invert,strength in ((False,1),(True,1),(False,0),(False,.3)):
   bump.invert=invert;bump.inputs['Strength'].default_value=strength
   sc.render.engine='VERTEX_LIT';a=f.render('bump_normal',m)
   sc.render.engine='BLENDER_EEVEE_NEXT';b=f.render('bump_eevee',m)
   error=float(abs(a[70:186,70:186,:3]-b[70:186,70:186,:3]).max());assert error<.004,(invert,strength,error)
   result[str((invert,strength))]=error
  bump.invert=False;bump.inputs['Strength'].default_value=1
  mul=t.nodes.new('ShaderNodeMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=30
  sine=t.nodes.new('ShaderNodeMath');sine.operation='SINE';t.links.new(sep.outputs['X'],mul.inputs[0]);t.links.new(mul.outputs[0],sine.inputs[0]);t.links.new(sine.outputs[0],bump.inputs['Height'])
  for width in (.1,2.0):
   bump.inputs['Filter Width'].default_value=width
   sc.render.engine='VERTEX_LIT';a=f.render('bump_sine',m)
   sc.render.engine='BLENDER_EEVEE_NEXT';b=f.render('bump_sine_eevee',m)
   error=float(abs(a[70:186,70:186,:3]-b[70:186,70:186,:3]).max());assert error<.008,(width,error)
   result['filter_'+str(width)]=error
  second=t.nodes.new('ShaderNodeBump');second.inputs['Distance'].default_value=.3
  t.links.new(sep.outputs['Y'],second.inputs['Height']);t.links.new(bump.outputs[0],second.inputs['Normal']);t.links.new(second.outputs[0],encode.inputs[0])
  sc.render.engine='VERTEX_LIT';a=f.render('bump_chain',m)
  sc.render.engine='BLENDER_EEVEE_NEXT';b=f.render('bump_chain_eevee',m)
  error=float(abs(a[70:186,70:186,:3]-b[70:186,70:186,:3]).max());assert error<.008,error
  result['chain']=error
  sc.camera.location.z=-3;sc.camera.rotation_euler=(3.141592653589793,0,0);s.backface_cull=False
  sc.render.engine='VERTEX_LIT';a=f.render('bump_back',m)
  sc.render.engine='BLENDER_EEVEE_NEXT';b=f.render('bump_back_eevee',m)
  error=float(abs(a[70:186,70:186,:3]-b[70:186,70:186,:3]).max());assert error<.008,('backface',error)
  result['backface']=error
  sc.camera.location.z=3;sc.camera.rotation_euler=(0,0,0)
  sc.render.engine='VERTEX_LIT'
  t.links.new(principled.outputs[0],output.inputs['Surface'])
  for link in list(principled.inputs['Base Color'].links):t.links.remove(link)
  principled.inputs['Base Color'].default_value=(.6,.6,.6,1)
  s.hemi_intensity=0;s.sun_intensity=1;s.sun_elevation=.7;s.sun_azimuth=-1.57
  a=f.render('bump_lit',m);bump.inputs['Strength'].default_value=0;b=f.render('bump_flat',m)
  assert abs(a-b).max()>.02
  bump.inputs['Strength'].default_value=1;c=f.render('bump_restore',m);assert abs(a-c).max()<1e-5
  bump.mute=True;c=f.render('bump_mute',m);assert abs(b-c).max()<1e-5;bump.mute=False
  t.links.remove(bump.inputs['Height'].links[0]);c=f.render('bump_unlinked',m);assert abs(b-c).max()<1e-5
  result['lighting_bypass_restore']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.out/'bump.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)

