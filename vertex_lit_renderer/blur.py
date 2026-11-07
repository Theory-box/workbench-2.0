"""UV-domain graph blur. GPU-only filtering; bounded, dependency-keyed texture cache."""
import hashlib
import os
from collections import OrderedDict
import bpy
import gpu
import numpy as np
from bpy.props import FloatProperty, EnumProperty
from bpy.app.handlers import persistent
from gpu_extras.batch import batch_for_shader

NODE_ID = 'VLRShaderNodeBlur'
_cache = OrderedDict()
_image_keys = {}
_image_seen = {}
_bounds_cache = OrderedDict()
_domain_object = None
_domain_depsgraph = None
_coverage = {}
_periodic_frame = {}
_filter_shader = None
_warnings = {}
_MAX_BYTES = 64 * 1024 * 1024
stats = {'builds': 0, 'hits': 0, 'bytes': 0}


def changed(self, context):
    self.id_data.update_tag()
    from . import material_shader
    # Group instances can belong to multiple materials.
    for name, mode in list(material_shader._prog_cache): material_shader.mark_dirty(name)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()


class VLRShaderNodeBlur(bpy.types.ShaderNodeCustomGroup):
    bl_idname = NODE_ID
    bl_label = 'Workbench 2.0 Blur'
    bl_description = 'Blur a color or value graph across the object UV range; cached on the GPU'
    radius: FloatProperty(name='Radius', default=4, min=0, max=64,
                          description='Gaussian support radius at the requested pixels-per-UV resolution', update=changed)
    strength: FloatProperty(name='Strength', default=1, min=0, max=1, update=changed)
    resolution: EnumProperty(name='Resolution', items=[(str(n), str(n), '') for n in (128,256,512,1024,2048)], default='512', description='Requested pixels per UV unit; large UV ranges are capped by Max Cache Edge', update=changed)
    coverage_limit: EnumProperty(name='Max Cache Edge', items=[(str(n),str(n),'') for n in (512,1024,2048,4096)], default='2048', description='Limit cache dimensions for extended UV ranges; total cache memory is also bounded', update=changed)
    cache_space: EnumProperty(name='UV Cache', items=[('AUTO','Auto','Share repeating textures; expand nonperiodic graphs'),('TILE','Repeat Tile','Use the original shared 0-1 tile cache'),('OBJECT','Object UV Range','Cache the actual mesh UV range')], default='AUTO', update=changed)
    extension: EnumProperty(name='Edges', items=[('REPEAT','Repeat','Wrap the cached UV tile'),('EXTEND','Extend','Clamp to the edge of the cached UV tile')], default='REPEAT', update=changed)

    def init(self, context):
        tree = bpy.data.node_groups.get('.Workbench 2.0 Blur Fallback')
        if tree is None:
            tree = bpy.data.node_groups.new('.Workbench 2.0 Blur Fallback','ShaderNodeTree')
            sock = tree.interface.new_socket(name='Color',in_out='INPUT',socket_type='NodeSocketColor')
            sock.default_value = (0.5,0.5,0.5,1)
            tree.interface.new_socket(name='Color',in_out='OUTPUT',socket_type='NodeSocketColor')
            inp=tree.nodes.new('NodeGroupInput');out=tree.nodes.new('NodeGroupOutput')
            tree.links.new(inp.outputs['Color'],out.inputs['Color'])
        self.node_tree=tree; self.width=210

    def draw_buttons(self, context, layout):
        layout.prop(self,'radius');layout.prop(self,'strength')
        layout.prop(self,'resolution');layout.prop(self,'extension')
        layout.prop(self,'cache_space')
        layout.label(text='Auto UV coverage; color / value')
        coverage=_coverage.get((self.id_data.name,self.name))
        if coverage:
            layout.prop(self,'coverage_limit')
            layout.label(text=str(coverage[0])+' x '+str(coverage[1])+' cache pixels')
        warning = _warnings.get((self.id_data.name,self.name))
        if warning:
            row=layout.row();row.alert=True;row.label(text=warning,icon='ERROR')


def menu(self, context):
    if context.space_data.tree_type=='ShaderNodeTree':
        op=self.layout.operator('node.add_node',text='Workbench 2.0 Blur')
        op.type=NODE_ID;op.use_transform=True


class Source:
    is_blur_source = True

    def __init__(self, parent, node):
        from . import node_transpiler as nt, shaders, glsl_lib
        self.material = parent.owner_name
        self.tree = node.id_data.name
        self.node = node.name
        self.group_path = tuple(g.name for g,_ in parent._group_stack)
        self.key = (self.material,self.group_path,self.tree,self.node)
        self.name = 'Blur:' + repr(self.key)
        self.domain = (0.0,0.0,1.0,1.0)
        self.runtime_key = self.key
        if node.as_pointer() in parent.blur_stack or len(parent.blur_stack)>16:
            raise ValueError('Recursive blur graph')
        t=nt._Transpiler();t.named_uvs=True;t.owner_name=parent.owner_name
        t._group_stack=list(parent._group_stack)
        t.blur_stack=parent.blur_stack+(node.as_pointer(),)
        value=t.input_expr(node,node.inputs['Color'],'vec4')
        body='\n'.join(t.lines)+'\nreturn '+value+';'
        if t.notes or any(word in body for word in ('vGenerated','vObjPos','vWpos','vNrm','vColor')):
            raise ValueError('Use supported UV-based inputs')
        if len(t.uv_roots)>1:
            raise ValueError('Use one UV map upstream')
        self.uv_name=next(iter(t.uv_roots),'')
        aliases=''.join('#define '+v+' vUV\n' for v in t.uv_maps.values())
        decl=''.join('uniform sampler2D '+s.uniform+';\n' for s in t.samplers)+'\n'.join(t.param_decls)
        function='vec4 computeBaseColor(vec2 vUV){\n'+body+'\n}'
        self.fragment=(shaders.BAKE_FRAG_HEAD+aliases+decl+glsl_lib.collect(function)+function+
                       '\nuniform vec4 uBlurDomain;\nvoid main(){vec4 c=computeBaseColor(vUV*uBlurDomain.zw+uBlurDomain.xy);fragColor=vec4(c.rgb*c.a,c.a);}')
        if any(not getattr(s.image,'is_blur_source',False) and s.image.source in {'TILED','MOVIE','SEQUENCE'} for s in t.samplers):
            raise ValueError('Still images only in UV cache')
        self.params=t.params;self.samplers=t.samplers

    def get_node(self):
        mat=bpy.data.materials.get(self.material)
        root=mat.node_tree if mat else None
        tree=root if not self.group_path else bpy.data.node_groups.get(self.tree)
        node=tree.nodes.get(self.node) if tree else None
        if node is None or node.bl_idname!=NODE_ID:raise ValueError('Blur node no longer exists')
        return node,root


def emit(t,node):
    from .node_transpiler import Sampler
    if node.mute or node.radius<=0 or node.strength<=0:return t.input_expr(node,node.inputs['Color'],'vec4')
    try:
        source=Source(t,node)
        _warnings.pop((node.id_data.name,node.name),None)
    except ValueError as exc:
        _warnings[node.id_data.name,node.name]=str(exc)
        t.notes.append('Blur bypassed: '+str(exc))
        return t.input_expr(node,node.inputs['Color'],'vec4')
    if source.uv_name and t.named_uvs:
        coord=t.uv_maps.setdefault(source.uv_name,'vNamedUV'+str(len(t.uv_maps)))
    else:coord='vUV'
    coord=t._uv_expr(source.uv_name,coord)
    sampler='uTx_'+str(len(t.samplers));t.samplers.append(Sampler(sampler,source))
    # Shader wrapping is explicit; Blender image sampler state is not changed.
    uv=t._new_var('blur_uv');var=t._new_var('blur')
    domain=sampler+'Domain'
    t.param_decls.append('uniform vec4 '+domain+';')
    t._line('vec2 '+uv+' = ('+coord+' - '+domain+'.xy) / '+domain+'.zw;')
    if node.extension=='REPEAT':uv='fract('+uv+')'
    else:uv='clamp('+uv+', vec2(0.5)/vec2(textureSize('+sampler+',0)), vec2(1.0)-vec2(0.5)/vec2(textureSize('+sampler+',0)))'
    t._line('vec4 '+var+' = texture('+sampler+', '+uv+');')
    return var


def begin_frame():
    _image_keys.clear()
    _periodic_frame.clear()
    set_object()


def set_object(obj=None, depsgraph=None):
    global _domain_object, _domain_depsgraph
    _domain_object, _domain_depsgraph = obj, depsgraph


def _linked_output(socket, stack, seen):
    if socket is None or not socket.is_linked:return None
    link=socket.links[0];node,out=link.from_node,link.from_socket
    key=(node.as_pointer(),out.identifier,tuple(n.as_pointer() for n in stack))
    if key in seen:return None
    seen=seen|{key}
    if node.mute:
        bypass=next((l.from_socket for l in node.internal_links if l.to_socket==out),None)
        return _linked_output(bypass,stack,seen)
    if node.type=='REROUTE':return _linked_output(node.inputs[0],stack,seen)
    if node.type=='GROUP_INPUT' and stack:
        group=stack[-1]
        inp=next((s for s in group.inputs if s.identifier==out.identifier),None)
        return _linked_output(inp,stack[:-1],seen)
    if node.type=='GROUP':
        tree=node.node_tree
        gout=next((n for n in tree.nodes if n.type=='GROUP_OUTPUT' and n.is_active_output),None) if tree else None
        inp=next((s for s in gout.inputs if s.identifier==out.identifier),None) if gout else None
        return _linked_output(inp,stack+(node,),seen)
    return node,out,stack,seen


def _uv_linear(socket, stack, seen):
    item=_linked_output(socket,stack,seen)
    if item is None:return None
    node,out,stack,seen=item
    if node.type=='UVMAP' or node.type=='TEX_COORD' and out.name=='UV':
        return np.array(((1.,0.),(0.,1.),(0.,0.)))
    if node.type=='MAPPING' and node.vector_type in {'POINT','VECTOR'}:
        if any(node.inputs[k].is_linked for k in ('Location','Rotation','Scale')):return None
        a=_uv_linear(node.inputs['Vector'],stack,seen)
        if a is None:return None
        from mathutils import Euler
        rot=np.array(Euler(node.inputs['Rotation'].default_value).to_matrix())
        return rot @ (np.array(node.inputs['Scale'].default_value)[:,None]*a)
    if node.type=='VECT_MATH':
        a=_uv_linear(node.inputs[0],stack,seen)
        if a is None:return None
        if node.operation=='SCALE' and not node.inputs['Scale'].is_linked:
            return a*node.inputs['Scale'].default_value
        if not node.inputs[1].is_linked:
            if node.operation in {'ADD','SUBTRACT'}:return a
            if node.operation=='MULTIPLY':return a*np.array(node.inputs[1].default_value)[:,None]
    return None


def periodic_input(socket, stack=(), seen=frozenset()):
    if socket is None or not socket.is_linked:return True
    item=_linked_output(socket,stack,seen)
    if item is None:return False
    node,out,stack,seen=item
    if node.bl_idname==NODE_ID:return periodic_input(node.inputs['Color'],stack,seen)
    if node.type=='TEX_IMAGE':
        if node.extension!='REPEAT' or node.projection!='FLAT':return False
        vector=node.inputs['Vector']
        if not vector.is_linked:return True
        a=_uv_linear(vector,stack,seen)
        return a is not None and np.isfinite(a).all() and np.allclose(a[:2],np.round(a[:2]),atol=1e-6,rtol=0)
    if node.type in {'UVMAP','TEX_COORD','ATTRIBUTE','NEW_GEOMETRY','OBJECT_INFO'}:return False
    # Restrict proof to deterministic pointwise operations supported by the compiler.
    if node.type not in {'RGB','VALUE','MATH','VECT_MATH','MIX','MIX_RGB','VALTORGB',
                         'HUE_SAT','GAMMA','INVERT','BRIGHTCONTRAST','CURVE_RGB',
                         'CURVE_FLOAT','RGBTOBW','SEPXYZ','COMBXYZ','SEPRGB','COMBRGB',
                         'SEPARATE_COLOR','COMBINE_COLOR','CLAMP','MAP_RANGE'}:return False
    return all(periodic_input(inp,stack,seen) for inp in node.inputs if inp.is_linked)


def domain_for(source):
    node,root=source.get_node()
    if node.cache_space=='TILE':return (0.0,0.0,1.0,1.0)
    if node.cache_space=='AUTO':
        if source.key not in _periodic_frame:
            stack=[];tree=root
            for name in source.group_path:
                group=tree.nodes.get(name) if tree else None
                if group is None:break
                stack.append(group);tree=group.node_tree
            _periodic_frame[source.key]=periodic_input(node.inputs['Color'],tuple(stack))
        if _periodic_frame[source.key]:return (0.0,0.0,1.0,1.0)
    obj = _domain_object
    if obj is None or obj.type != 'MESH': return (0.0,0.0,1.0,1.0)
    key = (obj.as_pointer(),obj.data.as_pointer(),source.uv_name)
    if key in _bounds_cache:
        _bounds_cache.move_to_end(key)
        return _bounds_cache[key]
    evaluated = obj.evaluated_get(_domain_depsgraph) if _domain_depsgraph else obj
    editing = obj.data.is_editmode and _domain_depsgraph is not None
    mesh = evaluated.to_mesh() if editing else evaluated.data
    domain = (0.0,0.0,1.0,1.0)
    try:
        uv = mesh.uv_layers.get(source.uv_name) if source.uv_name else next(
            (layer for layer in mesh.uv_layers if layer.active_render),mesh.uv_layers.active)
        if uv is not None and len(uv.data):
            a=np.empty(len(uv.data)*2,dtype=np.float32);uv.data.foreach_get('uv',a);a=a.reshape(-1,2)
            a=a[np.isfinite(a).all(axis=1)]
            if len(a):
                lo=a.min(axis=0);hi=a.max(axis=0)
                if (lo < -1e-5).any() or (hi > 1.00001).any():
                    # One extra UV tile protects filtered edges and ordinary parallax travel.
                    lo=np.floor(lo)-1;hi=np.ceil(hi)+1
                    domain=tuple(float(x) for x in (*lo,*(hi-lo)))
    finally:
        if editing:evaluated.to_mesh_clear()
    _bounds_cache[key]=domain
    while len(_bounds_cache)>256:_bounds_cache.popitem(last=False)
    return domain


@persistent
def geometry_changed(scene, depsgraph):
    if any(isinstance(u.id,bpy.types.Mesh) or
           isinstance(u.id,bpy.types.Object) and u.is_updated_geometry
           for u in depsgraph.updates):
        _bounds_cache.clear()


def domain_values(samplers):
    result=[]
    for sampler in samplers:
        name,image = (sampler.uniform,sampler.image) if hasattr(sampler,'uniform') else sampler
        if getattr(image,'is_blur_source',False):result.append((name+'Domain',image.domain))
    return result


def bind_domains(shader,samplers):
    for name,value in domain_values(samplers):
        try:shader.uniform_float(name,value)
        except ValueError:pass


def image_key(image):
    key=image.as_pointer()
    if key in _image_keys:return _image_keys[key]
    path=bpy.path.abspath(image.filepath)
    try:
        st=os.stat(path);stamp=(st.st_mtime_ns,st.st_size)
    except OSError:stamp=None
    # Blender exposes no reliable pixel revision counter. Dirty/generated images
    # require a content check, shared across every blur using them in this draw.
    digest=None
    if image.is_dirty or image.source=='GENERATED':
        pixels=np.empty(len(image.pixels),dtype=np.float32)
        image.pixels.foreach_get(pixels)
        digest=hashlib.blake2b(memoryview(pixels),digest_size=16).digest()
    result=(key,tuple(image.size),image.colorspace_settings.name,image.alpha_mode,
            image.source,path,stamp,digest)
    _image_keys[key]=result
    return result


_FILTER = '''
in vec2 vUV;
out vec4 fragColor;
uniform sampler2D source;
uniform sampler2D original;
uniform vec2 direction;
uniform float radius;
uniform float strength;
uniform int vertical;
uniform int repeatEdges;
vec2 coord(vec2 uv){
    if(repeatEdges!=0)return fract(uv);
    vec2 halfPixel=0.5/vec2(textureSize(source,0));
    return clamp(uv,halfPixel,1.0-halfPixel);
}
void main(){
    vec4 sum=vec4(0.0);float weight=0.0;
    float sigma=max(radius/3.0,0.333333);
    for(int i=-64;i<=64;i++){
        if(abs(float(i))>ceil(radius))continue;
        float w=exp(-0.5*float(i*i)/(sigma*sigma));
        sum+=texture(source,coord(vUV+direction*float(i)))*w;weight+=w;
    }
    vec4 c=sum/max(weight,1e-8);
    if(vertical!=0){
        c=mix(texture(original,coord(vUV)),c,strength);
        c.rgb=c.a>1e-8?c.rgb/c.a:vec3(0.0);
    }
    fragColor=c;
}
'''


def _draw(shader,target,textures,params):
    # Two windings make this work under any caller face-culling state, without
    # touching that state (Blender has no face-culling getter).
    from .shaders import PLANE_BAKE_VERT
    batch=batch_for_shader(shader,'TRIS',{'pos':[(-1,-1),(3,-1),(-1,3),(-1,-1),(-1,3),(3,-1)]})
    with gpu.types.GPUFrameBuffer(color_slots=(target,)).bind():
        gpu.state.viewport_set(0,0,target.width,target.height)
        shader.bind()
        for name,tex in textures:shader.uniform_sampler(name,tex)
        for name,value in params:
            try:
                if isinstance(value,int):shader.uniform_int(name,value)
                else:shader.uniform_float(name,value)
            except ValueError:pass # optimized-out parameter
        batch.draw(shader)


def texture(source):
    global _filter_shader
    from . import shaders,engine
    node,tree=source.get_node()
    source.domain=domain_for(source)
    source.runtime_key=source.key if source.domain==(0.0,0.0,1.0,1.0) else (source.key,source.domain)
    values=tuple((p.uniform,p.value(tree)) for p in source.params)
    textures=[];dependencies=[]
    # Refresh all children before acquiring image handles (a child can refresh a
    # shared image also used directly by this graph).
    children={}
    for sampler in source.samplers:
        image=sampler.image
        if getattr(image,'is_blur_source',False) and image.key not in children:
            tex=engine._get_gpu_tex(image)
            children[image.key]=(tex,_cache[image.runtime_key]['signature'],image.domain,image.runtime_key)
    for sampler in source.samplers:
        image=sampler.image
        if getattr(image,'is_blur_source',False):
            tex,dependency,image.domain,image.runtime_key=children[image.key]
        else:
            dependency=image_key(image)
            previous=_image_seen.get(image.as_pointer())
            if previous is not None and previous!=dependency:
                engine._invalidate_tex(image.name)
            _image_seen[image.as_pointer()]=dependency
            tex=engine._get_gpu_tex(image)
        if tex is None:raise ValueError('Blur source texture unavailable')
        textures.append((sampler.uniform,tex));dependencies.append(dependency)
    res=int(node.resolution)
    span=source.domain[2:]
    density=min(float(res),float(node.coverage_limit)/max(span),(_MAX_BYTES/(8.0*span[0]*span[1]))**0.5)
    width=max(1,int(span[0]*density));height=max(1,int(span[1]*density))
    if source.domain!=(0.0,0.0,1.0,1.0):_coverage[source.tree,source.node]=(width,height)
    else:_coverage.pop((source.tree,source.node),None)
    signature=(source.fragment,values,tuple(dependencies),res,float(node.radius),float(node.strength),node.extension,width,height,source.domain)
    entry=_cache.get(source.runtime_key)
    if entry is not None and entry['signature']==signature:
        _cache.move_to_end(source.runtime_key);stats['hits']+=1
        return entry['texture']
    old_view=gpu.state.viewport_get();old_blend=gpu.state.blend_get()
    old_depth=gpu.state.depth_test_get();old_mask=gpu.state.depth_mask_get()
    try:
        gpu.state.blend_set('NONE');gpu.state.depth_test_set('NONE');gpu.state.depth_mask_set(False)
        shader=entry["shader"] if entry is not None and entry["fragment"]==source.fragment else gpu.types.GPUShader(shaders.PLANE_BAKE_VERT,source.fragment)
        original=gpu.types.GPUTexture((width,height),format='RGBA16F')
        scratch=gpu.types.GPUTexture((width,height),format='RGBA16F')
        result=gpu.types.GPUTexture((width,height),format='RGBA16F')
        _draw(shader,original,textures,list(values)+[('uBlurDomain',source.domain)]+domain_values(source.samplers))
        if _filter_shader is None:_filter_shader=gpu.types.GPUShader(shaders.PLANE_BAKE_VERT,_FILTER)
        settings=[('strength',float(node.strength)),('repeatEdges',int(node.extension=='REPEAT'))]
        _draw(_filter_shader,scratch,[('source',original),('original',original)],settings+[('radius',float(node.radius)*width/(span[0]*res)),('direction',(1/width,0)),('vertical',0)])
        _draw(_filter_shader,result,[('source',scratch),('original',original)],settings+[('radius',float(node.radius)*height/(span[1]*res)),('direction',(0,1/height)),('vertical',1)])
    finally:
        gpu.state.viewport_set(*old_view);gpu.state.blend_set(old_blend)
        gpu.state.depth_test_set(old_depth);gpu.state.depth_mask_set(old_mask)
    _cache[source.runtime_key]={'signature':signature,'texture':result,'bytes':width*height*8,'shader':shader,'fragment':source.fragment}
    _cache.move_to_end(source.runtime_key);stats['builds']+=1
    while sum(v['bytes'] for v in _cache.values())>_MAX_BYTES and len(_cache)>1:_cache.popitem(last=False)
    stats['bytes']=sum(v['bytes'] for v in _cache.values())
    return result


@persistent
def clear(*args):
    global _filter_shader
    _cache.clear();_image_keys.clear();_image_seen.clear();_warnings.clear();_bounds_cache.clear();_coverage.clear();_periodic_frame.clear();set_object();_filter_shader=None
    stats['bytes']=0


def resolve_samplers(samplers):
    from .engine import _get_gpu_tex
    prepared={};shared={}
    for name,image in samplers:
        if getattr(image,'is_blur_source',False):
            if image.key not in shared:
                tex=_get_gpu_tex(image)
                shared[image.key]=(tex,image.domain,image.runtime_key)
            tex,image.domain,image.runtime_key=shared[image.key]
            prepared[name]=tex
    return [(name,prepared[name] if name in prepared else _get_gpu_tex(image)) for name,image in samplers]


@persistent
def undo_reset(*args):
    from . import material_shader, engine
    material_shader.invalidate()
    engine._tex_cache.clear()


def register():
    bpy.utils.register_class(VLRShaderNodeBlur);bpy.types.NODE_MT_add.append(menu)
    if geometry_changed not in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.append(geometry_changed)
    if clear not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(clear)
    for handlers in (bpy.app.handlers.undo_post,bpy.app.handlers.redo_post):
        if undo_reset not in handlers:handlers.append(undo_reset)


def unregister():
    clear()
    if geometry_changed in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.remove(geometry_changed)
    if clear in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(clear)
    for handlers in (bpy.app.handlers.undo_post,bpy.app.handlers.redo_post):
        if undo_reset in handlers:handlers.remove(undo_reset)
    bpy.types.NODE_MT_add.remove(menu);bpy.utils.unregister_class(VLRShaderNodeBlur)
