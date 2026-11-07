"""Native F12: virtual depth agrees with geometry and overlaps a real cube."""
import bpy, pathlib, importlib.util, json, traceback, numpy as np
spec=importlib.util.spec_from_file_location('fixture',pathlib.Path(__file__).with_name('test_parallax_render.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from vertex_lit_renderer import material_shader

def setup():
    ob,m,n,_,_=f.setup();ob.scale=(40,40,1)
    t=m.node_tree;p=t.nodes.get('Principled BSDF')
    for link in list(p.inputs['Base Color'].links):t.links.remove(link)
    p.inputs['Base Color'].default_value=(.08,.6,.04,1)
    n.depth=.4;n.midlevel=0;n.self_shadow=False;n.self_ao=False;n.steps=128
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,.5));cube=bpy.context.object
    cm=bpy.data.materials.new('Red cube');cm.use_nodes=True
    cm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.7,.04,.02,1)
    cube.data.materials.append(cm)
    sc=bpy.context.scene;sc.camera.location=(2,-3,2.3)
    sc.camera.rotation_euler=(-sc.camera.location).to_track_quat('-Z','Y').to_euler()
    sc.camera.data.ortho_scale=3.5
    return ob,m,n,cube

def save_png(name):
    sc=bpy.context.scene;im=bpy.data.images.load(str(f.out/(name+'.exr')),check_existing=False)
    sc.render.image_settings.file_format='PNG';im.save_render(str(f.out/(name+'.png')),scene=sc)
    sc.render.image_settings.file_format='OPEN_EXR';bpy.data.images.remove(im)

def run():
    result={}
    try:
        ob,m,n,cube=setup();sc=bpy.context.scene;s=sc.vertex_lit
        for camera in ('ORTHO','PERSP'):
            sc.camera.data.type=camera
            for height in (.4,-.2):
                n.depth=.4;n.midlevel=0 if height>0 else .5
                n.inputs['Height'].default_value=1 if height>0 else 0
                n.depth_intersections=False;a=f.render('depth_flat',m)
                shader=material_shader.get_program(m)['shader']
                n.depth_intersections=True;b=f.render('depth_virtual',m)
                assert shader is material_shader.get_program(m)['shader']
                n.depth=0;ob.location.z=height;c=f.render('depth_physical',m)
                # Exclude the outer silhouette: depth writing cannot expand coverage.
                err=float(abs(b[40:216,40:216]-c[40:216,40:216]).max())
                assert err<.003,(camera,height,err)
                if height>0:
                    changed=int(((a[:,:,0]>.2)&(a[:,:,0]>a[:,:,1]*2)&(b[:,:,1]>b[:,:,0]*2)).sum())
                    assert changed>100,(camera,changed)
                    result[camera+'_cube_overlap_pixels']=changed
                result[camera+'_'+str(height)+'_geometry_error']=err
                ob.location.z=0
        # Actual patterned heightmap, with UV color following the same hit.
        ob.scale=(4,4,1)
        n.depth=.4;n.midlevel=0
        t=m.node_tree;tex=t.nodes.new('ShaderNodeTexImage')
        im=bpy.data.images.new('Grass height',width=128,height=128,float_buffer=True);im.colorspace_settings.name='Non-Color'
        y,x=np.mgrid[:128,:128];h=(.5+.5*np.sin(x*.9)*np.sin(y*.8)).astype(np.float32)
        im.pixels.foreach_set(np.stack([h,h,h,np.ones_like(h)],axis=-1).ravel());im.update();tex.image=im
        t.links.new(t.nodes.get('UV Map').outputs[0],tex.inputs[0]);t.links.new(tex.outputs[0],n.inputs['Height'])
        n.depth_intersections=False;a=f.render('depth_grass_off',m)
        n.depth_intersections=True;b=f.render('depth_grass_on',m)
        count=int(((a[:,:,0]>a[:,:,1]*2)&(b[:,:,1]>b[:,:,0]*2)).sum());assert count>100,count
        result['heightmap_cube_overlap_pixels']=count
        save_png('depth_grass_off');save_png('depth_grass_on')
        # Depth consumers must see the relief even with local height AO/self-shadow off.
        s.use_ao=True;s.ao_strength=1
        ao=f.render('depth_grass_ao',m);assert abs(ao-b).max()>.01
        result['screen_ao_responds']=True;s.use_ao=False
        s.sun_intensity=1;s.sun_elevation=.5;s.sun_azimuth=0
        s.contact_length=.6;s.contact_thickness=.1;s.contact_steps=64
        s.use_contact_shadows=False;a=f.render('depth_grass_contact_off',m)
        s.use_contact_shadows=True;b=f.render('depth_grass_contact_on',m)
        assert ((a-b)[:,:,:3].max(axis=2)>.01).sum()>20
        result['contact_responds']=True;save_png('depth_grass_contact_on')
        cube.hide_render=True;s.use_contact_shadows=False;s.sun_intensity=0
        # Isolate the virtual height from real cube occlusion and height AO.
        differences=[]
        for enabled in (False,True):
            n.depth_intersections=enabled;s.use_ao=False;a=f.render('depth_ao_base',m)
            s.use_ao=True;b=f.render('depth_ao_effect',m);differences.append(a-b)
        count=int((abs(differences[1]-differences[0])[:,:,:3].max(axis=2)>.01).sum())
        assert count>100,count;result['relief_screen_ao_pixels']=count;s.use_ao=False
        s.sun_intensity=1;differences=[]
        for enabled in (False,True):
            n.depth_intersections=enabled;s.use_contact_shadows=False;a=f.render('depth_contact_base',m)
            s.use_contact_shadows=True;b=f.render('depth_contact_effect',m);differences.append(a-b)
        count=int((abs(differences[1]-differences[0])[:,:,:3].max(axis=2)>.01).sum())
        assert count>100,count;result['relief_contact_pixels']=count;cube.hide_render=False
        # Zero depth retains default depth, including when height data exists.
        s.use_contact_shadows=False;n.depth=0
        n.depth_intersections=False;a=f.render('depth_zero_off',m)
        n.depth_intersections=True;b=f.render('depth_zero_on',m)
        assert abs(a-b).max()<1e-5
        result['zero_depth_unchanged']=True;result['pass']=True
    except Exception:result['error']=traceback.format_exc()
    (f.out/'depth.json').write_text(json.dumps(result,indent=2));print(result);bpy.ops.wm.quit_blender()

if __name__=='__main__':bpy.app.timers.register(run,first_interval=.5)
