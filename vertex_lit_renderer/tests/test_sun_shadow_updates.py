"""Warm viewport updates must match a fresh engine; run in a windowed Blender process."""
import bpy,sys,pathlib,json,traceback
import gpu,numpy as np
from mathutils import Vector
repo=pathlib.Path(__file__).resolve().parents[2]
root=repo.parent/'work';variant='combined'
(root/'sun-audit-results').mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(repo));sys.stdout.reconfigure(line_buffering=True)
import vertex_lit_renderer as addon
addon.register()
from vertex_lit_renderer import engine as en
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.render.engine='VERTEX_LIT'
s=sc.vertex_lit;s.use_shadows=True;s.use_ao=False;s.use_cavity=False;s.use_outline=False;s.aa_method='OFF';s.supersampling='1'
objs=[];mats=[]
for i in range(3):
    bpy.ops.mesh.primitive_cube_add(size=1,location=(i*1.7-1.7,0,0));o=bpy.context.object;objs.append(o)
    m=bpy.data.materials.new('AuditMat'+str(i));m.diffuse_color=(.6,.1,.05,1)
    m.use_nodes=i!=1
    if m.use_nodes:m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.1,.2,.7,1)
    o.data.materials.append(m);mats.append(m)
bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,-.6))
mod=objs[0].modifiers.new('DifferentRenderGeometry','SUBSURF');mod.levels=0;mod.render_levels=2
bpy.ops.object.camera_add(location=(6,-10,6));cam=bpy.context.object
cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam
sc.render.resolution_x=320;sc.render.resolution_y=240;sc.render.resolution_percentage=100
stage=-1;phase='warm';frames=0;pending=False;done=False;warm=None;results={}
labels=['assign_material', 'remove_material', 'replace_mesh', 'hide_object', 'unhide_object', 'object_color', 'toggle_nodes', 'collection_instance_add', 'collection_instance_move', 'collection_instance_hide', 'collection_instance_unhide', 'collection_instance_delete', 'sun_angle', 'sun_height', 'sun_off', 'sun_on', 'resolution', 'distance', 'bias', 'softness', 'shadows_off', 'shadows_on', 'camera_move', 'camera_ortho', 'light_add', 'light_move', 'light_energy', 'light_delete', 'negative_scale', 'restore_scale', 'mesh_deform', 'object_delete']
original=en.VertexLitEngine.view_draw
def areas():return [a for a in bpy.context.screen.areas if a.type=='VIEW_3D']
def draw(self,context,dg):
    global frames,pending,warm
    original(self,context,dg)
    if pending or done:return
    if getattr(self,'_geo_pending',False) or getattr(self,'_mat_pending',False):return
    frames+=1
    if frames<10:return
    w,h=context.region.width,context.region.height
    buf=gpu.state.active_framebuffer_get().read_color(0,0,w,h,4,0,'UBYTE');buf.dimensions=w*h*4
    arr=np.asarray(buf,dtype=np.uint8).reshape(h,w,4).copy()
    pending=True
    if stage<0:bpy.app.timers.register(next_stage,first_interval=.1);return
    if phase=='warm':
        warm=arr
        bpy.app.timers.register(reset_cold,first_interval=.1)
    else:
        delta=np.abs(warm.astype(np.int16)-arr.astype(np.int16))
        results[labels[stage]]={'pass':bool(delta.max()==0),'max_error':int(delta.max()),'changed_pixels':int(np.any(delta>0,axis=2).sum())}
        print('UPDATE_RESULT',labels[stage],results[labels[stage]],flush=True)
        bpy.app.timers.register(next_stage,first_interval=.1)
en.VertexLitEngine.view_draw=draw
def activate():
    global pending,frames
    for a in areas():a.spaces.active.shading.type='RENDERED'
    pending=False;frames=0
def reset_cold():
    global phase
    phase='cold'
    for a in areas():a.spaces.active.shading.type='SOLID'
    bpy.app.timers.register(clear,first_interval=.2)
def clear():
    en._release_gpu_caches()
    activate()
def change_0(stage):
    if stage==0:objs[0].data.materials[0]=mats[1]
    elif stage==1:objs[1].data.materials.clear()
    elif stage==2:objs[2].data=objs[0].data.copy()
    elif stage==3:objs[0].hide_set(True)
    elif stage==4:objs[0].hide_set(False)
    elif stage==5:objs[1].color=(.1,.8,.1,1)
    elif stage==6:mats[1].use_nodes=True
    elif stage==7:
        col=bpy.data.collections.new('InstanceSource')
        ob=objs[2].copy();ob.location=(0,0,1.8);col.objects.link(ob)
        inst=bpy.data.objects.new('TestInstance',None);inst.instance_type='COLLECTION';inst.instance_collection=col
        sc.collection.objects.link(inst)
    elif stage==8:bpy.data.objects['TestInstance'].location.x=2
    elif stage==9:bpy.data.objects['TestInstance'].hide_set(True)
    elif stage==10:bpy.data.objects['TestInstance'].hide_set(False)
    elif stage==11:bpy.data.objects.remove(bpy.data.objects['TestInstance'],do_unlink=True)


def change_1(stage):
    if stage==0:s.sun_azimuth=2.1
    elif stage==1:s.sun_elevation=.2
    elif stage==2:s.sun_intensity=0
    elif stage==3:s.sun_intensity=2
    elif stage==4:s.shadow_resolution='4096'
    elif stage==5:s.shadow_distance=100
    elif stage==6:s.shadow_bias=0
    elif stage==7:s.shadow_softness=8
    elif stage==8:s.use_shadows=False
    elif stage==9:s.use_shadows=True
    elif stage==10:
        for a in areas():a.spaces.active.region_3d.view_location=(1,0,1)
    elif stage==11:
        for a in areas():a.spaces.active.region_3d.view_perspective='ORTHO'


def change_2(stage):
    if stage==0:
        light=bpy.data.lights.new('AuditLight','POINT');light.energy=100
        obj=bpy.data.objects.new('AuditLight',light);sc.collection.objects.link(obj);obj.location=(1,-2,2)
    elif stage==1:bpy.data.objects['AuditLight'].location.x=-2
    elif stage==2:bpy.data.lights['AuditLight'].energy=200
    elif stage==3:bpy.data.objects.remove(bpy.data.objects['AuditLight'],do_unlink=True)
    elif stage==4:objs[0].scale.x=-1
    elif stage==5:objs[0].scale.x=1
    elif stage==6:
        objs[0].data.vertices[0].co.z+=2;objs[0].data.update()
    elif stage==7:bpy.data.objects.remove(objs[0],do_unlink=True)


def next_stage():
    global stage,phase,pending,frames,done
    try:
        stage+=1;phase='warm';frames=0
        if stage<12:change_0(stage)
        elif stage<24:change_1(stage-12)
        elif stage<32:change_2(stage-24)
        else:
            done=True;(root/'sun-audit-results'/f'{variant}-shadow-updates.json').write_text(json.dumps(results,indent=2))
            bpy.ops.wm.quit_blender();return
        pending=False
    except Exception:
        (root/'sun-audit-results'/f'{variant}-shadow-updates-error.txt').write_text(traceback.format_exc());bpy.ops.wm.quit_blender()
def begin():
    for a in areas():
        sp=a.spaces.active;sp.overlay.show_overlays=False
        sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion();sp.region_3d.view_location=(0,0,0);sp.region_3d.view_distance=9
        sp.shading.type='RENDERED'
    bpy.app.timers.register(pump,first_interval=.04)
def pump():
    if done:return
    for a in areas():
        r=a.spaces.active.region_3d;r.view_rotation=r.view_rotation.copy();a.tag_redraw()
    return .04
bpy.app.timers.register(begin,first_interval=1)
bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender() and None,first_interval=180)
