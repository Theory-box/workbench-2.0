import bpy,sys,pathlib,json,traceback
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
import vertex_lit_renderer as addon;addon.register()
from vertex_lit_renderer import lightmap
out=repo.parent/'work/lightmap-tests'
result={}
try:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.mesh.primitive_cube_add();ob=bpy.context.object
 bevel=ob.modifiers.new('Bevel','BEVEL');bevel.width=.1
 mirror=ob.modifiers.new('Mirror','MIRROR');mirror.show_viewport=False
 disabled=ob.modifiers.new('Disabled','SUBSURF');disabled.show_viewport=False;disabled.show_render=False
 state=[(m.show_viewport,m.show_render) for m in ob.modifiers]
 sc=bpy.context.scene;sc.render.engine='VERTEX_LIT';sc.cycles.device='CPU'
 ob.vlr_lightmap_settings.resolution='128';ob.vlr_lightmap_settings.samples=1
 original=lightmap._cycles_bake
 def checked(*args):
  assert all(not m.show_viewport and not m.show_render for m in ob.modifiers)
  return original(*args)
 lightmap._cycles_bake=checked
 lightmap.bake_selected(bpy.context)
 assert [(m.show_viewport,m.show_render) for m in ob.modifiers]==state
 assert ob.vlr_lightmap.image is not None
 old_image=ob.vlr_lightmap.image;old_mesh=ob.data
 for fail in ('CANCEL','EXCEPTION'):
  def broken(*args):
   assert all(not m.show_viewport and not m.show_render for m in ob.modifiers)
   if fail=='EXCEPTION':raise RuntimeError('Injected failure')
   return {'CANCELLED'}
  lightmap._cycles_bake=broken
  try:lightmap.bake_selected(bpy.context);raise AssertionError('Expected error')
  except RuntimeError:pass
  assert [(m.show_viewport,m.show_render) for m in ob.modifiers]==state
  assert ob.data==old_mesh and ob.vlr_lightmap.image==old_image
 result['success_cancel_error_restore']=True;result['pass']=True
except Exception:result['error']=traceback.format_exc()
(out/'modifier_bake.json').write_text(json.dumps(result,indent=2));print(result)
