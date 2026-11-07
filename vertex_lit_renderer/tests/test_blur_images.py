import bpy,sys,pathlib,json,traceback,numpy as np,gpu
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import blur,material_shader,bake
out=repo.parent/'work/blur-tests';out.mkdir(exist_ok=True)
def run():
 result={}
 try:
  m=bpy.data.materials.new('File blur');m.use_nodes=True;t=m.node_tree
  original=bpy.data.images.new('Writer',width=32,height=32,float_buffer=False);original.colorspace_settings.name='Non-Color';original.filepath_raw=str(out/'source.png');original.file_format='PNG'
  original.pixels.foreach_set([.4,.5,.6,1]*1024);original.update();original.save()
  im=bpy.data.images.load(original.filepath_raw);im.colorspace_settings.name='Non-Color'
  tex=t.nodes.new('ShaderNodeTexImage');tex.image=im;b=t.nodes.new('VLRShaderNodeBlur');b.resolution='128';t.links.new(tex.outputs['Color'],b.inputs[0]);t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  first=bake.bake_material_to_array(m,32)
  im.colorspace_settings.name='sRGB';second=bake.bake_material_to_array(m,32);assert abs(first-second).max()>.05
  original.pixels.foreach_set([.8,.2,.4,1]*1024);original.update();original.save();im.reload()
  third=bake.bake_material_to_array(m,32);assert abs(second-third).max()>.1
  # Independent reference: bypass the Blur, so comparison exercises image upload too.
  b.mute=True;reference=bake.bake_material_to_array(m,32);assert abs(third-reference).max()<.006
  result={'pass':True,'colorspace_delta':float(abs(first-second).max()),'reload_delta':float(abs(second-third).max())}
 except Exception:result['error']=traceback.format_exc()
 (out/'images.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
