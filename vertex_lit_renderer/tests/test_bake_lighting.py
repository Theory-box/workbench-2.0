import bpy,sys,pathlib,json,traceback,math,numpy as np
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import lightmap
from vertex_lit_renderer.bake_lighting import lighting_source
out=repo.parent/'work/lightmap-tests';out.mkdir(exist_ok=True)

def run():
 result={}
 try:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  sc=bpy.context.scene;sc.render.engine='VERTEX_LIT';sc.cycles.device='CPU'
  bpy.ops.mesh.primitive_plane_add(size=2);ob=bpy.context.object
  m=bpy.data.materials.new('White diffuse');m.use_nodes=True;t=m.node_tree;t.nodes.clear()
  diffuse=t.nodes.new('ShaderNodeBsdfDiffuse');diffuse.inputs['Color'].default_value=(1,1,1,1)
  output=t.nodes.new('ShaderNodeOutputMaterial');t.links.new(diffuse.outputs[0],output.inputs['Surface']);ob.data.materials.append(m)
  lamp=bpy.data.lights.new('Existing light','POINT');lamp.energy=1000
  existing=bpy.data.objects.new('Existing light',lamp);sc.collection.objects.link(existing);existing.location=(0,0,2)
  original=sc.world;original.use_nodes=True;original.node_tree.nodes.get('Background').inputs['Strength'].default_value=5
  s=sc.vertex_lit;settings=sc.vlr_lightmap_settings;settings.resolution='128';settings.samples=32;settings.lighting_source='WORKBENCH'
  s.key_intensity=4;s.sun_intensity=.8;s.sun_elevation=.7;s.sun_azimuth=1.2;s.sun_color=(1,1,1)
  s.sky_color=(.6,.4,.2);s.ground_color=(.1,.2,.3);s.hemi_intensity=1
  counts=(len(bpy.data.worlds),len(bpy.data.lights),len(bpy.data.objects))
  def restored():
   assert sc.world==original and not existing.hide_render and lamp.energy==1000
   assert counts==(len(bpy.data.worlds),len(bpy.data.lights),len(bpy.data.objects))
   assert sc.render.engine=='VERTEX_LIT'
  def bake():
   bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
   lightmap.bake_selected(bpy.context);restored()
   px=np.array(ob.vlr_lightmap.image.pixels[:]).reshape(128,128,4)
   return np.median(px[32:96,32:96,:3],axis=(0,1))
  s.use_sky_ground=False;a=bake();target=np.full(3,.8*math.sin(.7));assert abs(a-target).max()<.015,(a,target)
  result['sun_rgb']=a.tolist()
  s.use_sun=False;s.use_sky_ground=True;a=bake();assert abs(a-np.array(s.sky_color)).max()<.025,a
  result['sky_rgb']=a.tolist()
  ob.rotation_euler.x=math.pi;a=bake();assert abs(a-np.array(s.ground_color)).max()<.025,a
  result['ground_rgb']=a.tolist();ob.rotation_euler.x=0
  ob.rotation_euler.y=math.pi/3;a=bake();expected=np.array(s.ground_color)*.25+np.array(s.sky_color)*.75
  assert abs(a-expected).max()<.025,(a,expected)
  result['tilted_hemi_rgb']=a.tolist();ob.rotation_euler.y=0
  s.use_sky_ground=False;a=bake();assert abs(a).max()<1e-5,a
  result['existing_lights_world_key_excluded']=True
  # Emissive mesh still illuminates while both Workbench sources are disabled.
  bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,1));em=bpy.context.object;em.rotation_euler.x=math.pi
  mat=bpy.data.materials.new('Emitter');mat.use_nodes=True;nt=mat.node_tree;nt.nodes.clear();e=nt.nodes.new('ShaderNodeEmission');e.inputs['Strength'].default_value=2;o=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs[0],o.inputs[0]);em.data.materials.append(mat)
  counts=(len(bpy.data.worlds),len(bpy.data.lights),len(bpy.data.objects))
  a=bake();assert a.min()>.1,a;result['emission_retained']=True
  em.hide_render=True
  # A vertical red wall receives sunlight and bounces it onto the floor.
  bpy.ops.mesh.primitive_plane_add(size=2,location=(0,1,1));wall=bpy.context.object;wall.rotation_euler.x=math.pi/2
  red=m.copy();red.node_tree.nodes.get('Diffuse BSDF').inputs['Color'].default_value=(.8,.02,.02,1);wall.data.materials.append(red)
  s.use_sun=True;s.sun_elevation=.4;s.sun_azimuth=math.pi;s.use_sky_ground=False
  counts=(len(bpy.data.worlds),len(bpy.data.lights),len(bpy.data.objects))
  bounced=bake();assert bounced[0]>bounced[1]+.005,bounced
  result['color_bounce_rgb']=bounced.tolist()
  old_bake=lightmap._cycles_bake
  lightmap._cycles_bake=lambda *args:{'CANCELLED'}
  image=ob.vlr_lightmap.image
  try:
   try:bake();raise AssertionError('Expected cancellation')
   except RuntimeError:pass
   restored();assert ob.vlr_lightmap.image==image
  finally:lightmap._cycles_bake=old_bake
  with lighting_source(sc,'SCENE'):assert sc.world==original and not existing.hide_render
  try:
   with lighting_source(sc,'WORKBENCH'):raise RuntimeError('Injected failure')
  except RuntimeError:pass
  restored()
  settings.lighting_source='SCENE';scene_bake=bake();assert scene_bake.max()>1,scene_bake
  result['cancel_restores_and_scene_passthrough']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (out/'bake_lighting.json').write_text(json.dumps(result,indent=2));print(result)

run()
