import bpy,sys,pathlib,json,traceback,numpy as np,importlib.util
repo=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_quality.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def run():
 result={}
 try:
  ob,m,n=f.setup();sc=bpy.context.scene;sc.world.use_nodes=True;sc.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=1;sc.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(1,1,1,1)
  original=np.empty(len(ob.data.loops)*2,dtype=np.float32);ob.data.uv_layers['UVMap'].data.foreach_get('uv',original)
  active=next(uv.name for uv in ob.data.uv_layers if uv.active_render)
  ob.vlr_lightmap_settings.resolution='128';ob.vlr_lightmap_settings.samples=8
  assert bpy.ops.vertex_lit.lightmap_bake()=={'FINISHED'}
  now=np.empty_like(original);ob.data.uv_layers['UVMap'].data.foreach_get('uv',now);assert np.array_equal(now,original)
  assert next(uv.name for uv in ob.data.uv_layers if uv.active_render)==active
  n.depth=0;a=f.f.render('baked_parallax_off',m);n.depth=.35;b=f.f.render('baked_parallax_on',m)
  changed=int((np.max(abs(a-b)[:,:,:3],axis=2)>.005).sum());assert changed>100,changed;result['baked_parallax_changed_pixels']=changed
  sc.vertex_lit.use_cavity=True;c=f.f.render('baked_parallax_cavity',m);assert (np.max(abs(b-c)[:,:,:3],axis=2)>.005).sum()>100
  sc.vertex_lit.use_cavity=False;sc.vertex_lit.use_ao=True;sc.vertex_lit.ao_bias=.002;n.self_ao=False;a=f.f.render('baked_ao_off',m);n.self_ao=True;b=f.f.render('baked_ao_on',m);assert (np.max(abs(a-b)[:,:,:3],axis=2)>.005).sum()>100
  sc.vertex_lit.use_ao=False;sc.vertex_lit.sun_intensity=3;n.self_shadow=False;a=f.f.render('baked_sun_off',m);n.self_shadow=True;b=f.f.render('baked_sun_on',m)
  result['baked_replaces_live_sun']=float(abs(a-b).max())
  assert result['baked_replaces_live_sun']<.001
  result['original_uvs_preserved']=True;result['cavity_ao_with_bake']=True;result['pass']=True
 except Exception:result['error']=traceback.format_exc()
 (f.f.out/'baked_parallax.json').write_text(json.dumps(result,indent=2));bpy.ops.wm.quit_blender()
if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
