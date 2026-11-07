import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import blur,material_shader
out=repo.parent/'work/blur-tests';out.mkdir(exist_ok=True)
def render(name,m):
 # Fixture checks finite pixels, visible geometry and shader compile success.
 return f.render('blur_'+name,m)
def run():
 result={}
 try:
  ob,m,parallax,scale,offset=f.setup();parallax.depth=0;sc=bpy.context.scene;t=m.node_tree
  im=bpy.data.images.new('Blur render height',width=128,height=128,float_buffer=True);im.colorspace_settings.name='Non-Color'
  y,x=np.mgrid[:128,:128];h=((x//16+y//16)%2).astype(np.float32);a=np.stack([h,h,h,np.ones_like(h)],axis=-1)
  im.pixels.foreach_set(a.ravel());im.update()
  tex=t.nodes.new('ShaderNodeTexImage');tex.image=im;t.links.new(scale.outputs[0],tex.inputs[0])
  b=t.nodes.new('VLRShaderNodeBlur');b.resolution='128';b.radius=0
  t.links.new(tex.outputs['Color'],b.inputs[0]);t.links.new(b.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color'])
  sharp=render('sharp',m);b.radius=10;soft=render('soft',m)
  assert np.count_nonzero(np.max(abs(sharp-soft)[:,:,:3],axis=2)>.02)>500
  builds=blur.stats['builds'];repeat=render('repeat',m);assert blur.stats['builds']==builds and abs(repeat-soft).max()<1e-5
  # Upstream UV mapping edits must rebake, unlike camera movement.
  scale.inputs['Scale'].default_value=1.3;updated=render('scale',m);assert blur.stats['builds']==builds+1 and abs(updated-soft).max()>.05
  builds=blur.stats['builds'];sc.camera.location.x=-1.6;sc.camera.rotation_euler=(-sc.camera.location).to_track_quat('-Z','Y').to_euler();render('camera',m);assert blur.stats['builds']==builds
  # Same node is a scalar height source, with no filtering inside the ray loop.
  t.links.new(b.outputs[0],parallax.inputs['Height']);parallax.depth=.2
  height=render('height',m);b.radius=2;sharpheight=render('height_changed',m);assert abs(height-sharpheight).max()>.03
  # Image pixels changed in place must propagate to F12.
  a[:,:,:3]=.3;im.pixels.foreach_set(a.ravel());im.update();constant=render('paint',m)
  visible=constant[:,:,3]>.9;assert np.std(constant[visible,0])<.001
  # Shader groups and animated upstream socket values.
  group=bpy.data.node_groups.new('Blur input group','ShaderNodeTree')
  group.interface.new_socket(name='Color',in_out='INPUT',socket_type='NodeSocketColor');group.interface.new_socket(name='Color',in_out='OUTPUT',socket_type='NodeSocketColor')
  gi=group.nodes.new('NodeGroupInput');go=group.nodes.new('NodeGroupOutput');gb=group.nodes.new('VLRShaderNodeBlur');gb.resolution='128'
  group.links.new(gi.outputs[0],gb.inputs[0]);group.links.new(gb.outputs[0],go.inputs[0])
  gn=t.nodes.new('ShaderNodeGroup');gn.node_tree=group
  gn.inputs[0].default_value=(.2,.4,.8,1);gn.inputs[0].keyframe_insert('default_value',frame=1)
  gn.inputs[0].default_value=(.8,.3,.1,1);gn.inputs[0].keyframe_insert('default_value',frame=2)
  t.links.new(gn.outputs[0],t.nodes.get('Principled BSDF').inputs['Base Color']);parallax.depth=0
  sc.frame_set(1);first=render('frame1',m);sc.frame_set(2);second=render('frame2',m);assert abs(first-second).max()>.2
  # Cached color baking consumes the same general node.
  from vertex_lit_renderer.bake import bake_material_to_array
  baked=bake_material_to_array(m,res=32);assert abs(baked[:,:,:3]-(.8,.3,.1)).max()<.005
  result={'pass':True,'builds':blur.stats['builds'],'cache_bytes':blur.stats['bytes']}
 except Exception:result['error']=traceback.format_exc()
 (out/'render.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=.5)
