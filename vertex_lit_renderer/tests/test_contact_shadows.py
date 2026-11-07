"""Native F12 contact-shadow checks on a thin raised blocker and flat receiver."""
import bpy, sys, pathlib, json, traceback, numpy as np, importlib.util
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def setup():
    ob,m,n,_,_=f.setup();n.depth=0
    t=m.node_tree;p=t.nodes.get('Principled BSDF')
    for link in list(p.inputs['Base Color'].links):t.links.remove(link)
    p.inputs['Base Color'].default_value=(.7,.5,.3,1)
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,.08))
    blocker=bpy.context.object;blocker.scale=(.06,1.4,.12);blocker.data.materials.append(m)
    sc=bpy.context.scene;sc.camera.location=(1,-2,3);sc.camera.rotation_euler=(-sc.camera.location).to_track_quat('-Z','Y').to_euler()
    s=sc.vertex_lit;s.sun_intensity=1;s.sun_elevation=.5;s.sun_azimuth=0;s.hemi_intensity=.3
    s.contact_length=.5;s.contact_thickness=.08;s.contact_steps=64;s.use_shadows=False
    return ob,m,blocker

def run():
    result={}
    try:
        ob,m,blocker=setup();sc=bpy.context.scene;s=sc.vertex_lit
        for camtype in ('ORTHO','PERSP'):
            sc.camera.data.type=camtype
            s.use_contact_shadows=False;a=f.render('contact_'+camtype+'_off',m)
            s.use_contact_shadows=True;b=f.render('contact_'+camtype+'_on',m)
            d=a[:,:,:3]-b[:,:,:3];count=int((d.max(axis=2)>.03).sum())
            assert count>100,(camtype,count);assert d.min()>-.003,float(d.min())
            assert abs(a[:,:,3]-b[:,:,3]).max()<.001
            result[camtype+'_shadow_pixels']=count
            for state in ('off','on'):
                path=f.out/('contact_'+camtype+'_'+state+'.exr')
                im=bpy.data.images.load(str(path),check_existing=False)
                sc.render.image_settings.file_format='PNG'
                im.save_render(str(path.with_suffix('.png')),scene=sc)
                sc.render.image_settings.file_format='OPEN_EXR';bpy.data.images.remove(im)
        s.sun_intensity=0;s.use_contact_shadows=False;a=f.render('contact_ambient_off',m)
        s.use_contact_shadows=True;b=f.render('contact_ambient_on',m)
        assert abs(a-b).max()<.002;result['ambient_unchanged']=True
        s.sun_intensity=1;blocker.hide_render=True
        s.use_contact_shadows=False;a=f.render('contact_flat_off',m)
        s.use_contact_shadows=True;b=f.render('contact_flat_on',m)
        err=float(abs(a-b).max());assert err<.003,err;result['flat_error']=err
        blocker.hide_render=False;s.use_shadows=True
        s.use_contact_shadows=False;a=f.render('contact_map_off',m)
        s.use_contact_shadows=True;b=f.render('contact_map_on',m)
        assert (a-b).min()>-.003;result['shadow_map_combined']=True
        # Changing ambient must not change the amount of sun removed.
        s.use_shadows=False;s.hemi_intensity=0
        s.use_contact_shadows=False;a=f.render('contact_sun_only_off',m)
        s.use_contact_shadows=True;b=f.render('contact_sun_only_on',m)
        s.hemi_intensity=1
        s.use_contact_shadows=False;c=f.render('contact_fill_off',m)
        s.use_contact_shadows=True;d=f.render('contact_fill_on',m)
        err=float(abs((a-b)-(c-d)).max());assert err<.003,err
        result['sun_isolation_error']=err
        # Broad planar faces should not shadow themselves at other light directions.
        blocker.hide_render=True
        for angle in (0,1.57,3.14,4.71):
            s.sun_azimuth=angle;s.sun_elevation=.12
            s.use_contact_shadows=False;a=f.render('contact_slope_off',m)
            s.use_contact_shadows=True;b=f.render('contact_slope_on',m)
            err=float(abs(a-b).max());assert err<.003,(angle,err)
        result['grazing_flat_unchanged']=True
        blocker.hide_render=False;s.sun_elevation=.5;s.sun_azimuth=0
        transparent=m.copy();transparent.name='Contact transparent blocker'
        transparent.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value=.5
        blocker.data.materials[0]=transparent
        s.use_contact_shadows=False;a=f.render('contact_alpha_off',m)
        s.use_contact_shadows=True;b=f.render('contact_alpha_on',m)
        err=float(abs(a-b).max());assert err<.003,err
        result['transparent_blocker_ignored']=True;blocker.data.materials[0]=m
        s.supersampling='1.5'
        s.use_contact_shadows=False;a=f.render('contact_ss_off',m)
        s.use_contact_shadows=True;b=f.render('contact_ss_on',m)
        assert (a-b).min()>-.003 and ((a-b)[:,:,:3].max(axis=2)>.03).sum()>50
        result['supersampling']=True;s.supersampling='1'
        for mode in ('SOLID','RANDOM','NORMAL','DEPTH'):
            s.view_mode=mode;s.use_contact_shadows=False;a=f.render('contact_mode_off',m)
            s.use_contact_shadows=True;b=f.render('contact_mode_on',m)
            if mode in ('NORMAL','DEPTH'):assert abs(a-b).max()<.003
            else:assert ((a-b)[:,:,:3].max(axis=2)>.03).sum()>50
        result['view_modes']=True;s.view_mode='TEXTURED'
        # Baked light stays untouched even though a visible blocker is present.
        blocker.hide_render=False
        lm=bpy.data.images.new('contact baked lighting',width=4,height=4,float_buffer=True)
        lm.pixels.foreach_set([.8,.6,.4,1]*16);lm.update()
        ob.vlr_lightmap.image=lm;ob.vlr_lightmap.uv_name='UVMap';ob.update_tag(refresh={'DATA'})
        blocker.vlr_lightmap.image=lm;blocker.vlr_lightmap.uv_name='UVMap';blocker.update_tag(refresh={'DATA'})
        s.use_contact_shadows=False;a=f.render('contact_bake_off',m)
        s.use_contact_shadows=True;b=f.render('contact_bake_on',m)
        assert abs(a-b).max()<.003;result['baked_unchanged']=True
        result['pass']=True
    except Exception:result['error']=traceback.format_exc()
    (f.out/'contact.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()

if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
