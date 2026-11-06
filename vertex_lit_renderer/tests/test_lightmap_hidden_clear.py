"""Regression: hidden faces receive UVs; clearing respects shared images."""
import bpy, sys, pathlib, json, traceback
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import vertex_lit_renderer as addon
addon.register()
result = {}
try:
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    for collection in (ob.data.vertices, ob.data.edges, ob.data.polygons):
        for element in collection: element.hide = True; element.select = False
    bpy.context.scene.vlr_lightmap_settings.resolution = '128'
    bpy.context.scene.vlr_lightmap_settings.samples = 1
    assert bpy.ops.vertex_lit.lightmap_bake() == {'FINISHED'}
    uv = ob.data.uv_layers[ob.vlr_lightmap.uv_name]
    for face in ob.data.polygons:
        coords = [uv.data[i].uv.copy() for i in face.loop_indices]
        area = abs(sum(a.x*b.y-b.x*a.y for a,b in zip(coords,coords[1:]+coords[:1]))) / 2
        assert area > 0.001, (face.index, area)
    for collection in (ob.data.vertices, ob.data.edges, ob.data.polygons):
        assert all(e.hide and not e.select for e in collection)
    result['hidden_faces_unwrapped_and_state_restored'] = True
    other = ob.copy(); bpy.context.scene.collection.objects.link(other); other.select_set(False)
    image = ob.vlr_lightmap.image; name = image.name; mesh = ob.data
    assert bpy.ops.vertex_lit.lightmap_clear() == {'FINISHED'}
    assert ob.vlr_lightmap.image is None and ob.data is mesh
    assert other.vlr_lightmap.image is image and bpy.data.images.get(name) is image
    ob.select_set(False); other.select_set(True); bpy.context.view_layer.objects.active = other
    assert bpy.ops.vertex_lit.lightmap_clear() == {'FINISHED'}
    assert bpy.data.images.get(name) is None
    assert bpy.ops.vertex_lit.lightmap_bake() == {'FINISHED'}
    assert len(other.data.uv_layers) == 2
    result['clear_selected_shared_image_and_rebake'] = True
    result['pass'] = True
except Exception:
    result['error'] = traceback.format_exc()
path = pathlib.Path(__file__).resolve().parents[3]/'work/lightmap-tests/hidden-clear.json'
path.write_text(json.dumps(result, indent=2)); print(result)
if not result.get('pass'): raise RuntimeError(result['error'])

