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
    bl_description = 'Blur a color or value graph in its 0-1 UV tile; cached on the GPU'
    radius: FloatProperty(name='Radius', default=4, min=0, max=64,
                          description='Gaussian support radius in cache pixels', update=changed)
    strength: FloatProperty(name='Strength', default=1, min=0, max=1, update=changed)
    resolution: EnumProperty(name='Resolution', items=[(str(n), str(n), '') for n in (128,256,512,1024,2048)], default='512', update=changed)
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
        layout.label(text='UV tile 0-1; color / value')
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
                       '\nvoid main(){vec4 c=computeBaseColor(vUV);fragColor=vec4(c.rgb*c.a,c.a);}')
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
    t._line('vec2 '+uv+' = '+coord+';')
    if node.extension=='REPEAT':uv='fract('+uv+')'
    else:uv='clamp('+uv+', vec2(0.5)/vec2(textureSize('+sampler+',0)), vec2(1.0)-vec2(0.5)/vec2(textureSize('+sampler+',0)))'
    t._line('vec4 '+var+' = texture('+sampler+', '+uv+');')
    return var


def begin_frame():
    _image_keys.clear()


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
    values=tuple((p.uniform,p.value(tree)) for p in source.params)
    textures=[];dependencies=[]
    # Refresh all children before acquiring image handles (a child can refresh a
    # shared image also used directly by this graph).
    children={}
    for sampler in source.samplers:
        image=sampler.image
        if getattr(image,'is_blur_source',False) and image.key not in children:
            tex=engine._get_gpu_tex(image)
            children[image.key]=(tex,_cache[image.key]['signature'])
    for sampler in source.samplers:
        image=sampler.image
        if getattr(image,'is_blur_source',False):
            tex,dependency=children[image.key]
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
    signature=(source.fragment,values,tuple(dependencies),res,float(node.radius),float(node.strength),node.extension)
    entry=_cache.get(source.key)
    if entry is not None and entry['signature']==signature:
        _cache.move_to_end(source.key);stats['hits']+=1
        return entry['texture']
    old_view=gpu.state.viewport_get();old_blend=gpu.state.blend_get()
    old_depth=gpu.state.depth_test_get();old_mask=gpu.state.depth_mask_get()
    try:
        gpu.state.blend_set('NONE');gpu.state.depth_test_set('NONE');gpu.state.depth_mask_set(False)
        shader=entry["shader"] if entry is not None and entry["fragment"]==source.fragment else gpu.types.GPUShader(shaders.PLANE_BAKE_VERT,source.fragment)
        original=gpu.types.GPUTexture((res,res),format='RGBA16F')
        scratch=gpu.types.GPUTexture((res,res),format='RGBA16F')
        result=gpu.types.GPUTexture((res,res),format='RGBA16F')
        _draw(shader,original,textures,values)
        if _filter_shader is None:_filter_shader=gpu.types.GPUShader(shaders.PLANE_BAKE_VERT,_FILTER)
        settings=[('radius',float(node.radius)),('strength',float(node.strength)),('repeatEdges',int(node.extension=='REPEAT'))]
        _draw(_filter_shader,scratch,[('source',original),('original',original)],settings+[('direction',(1/res,0)),('vertical',0)])
        _draw(_filter_shader,result,[('source',scratch),('original',original)],settings+[('direction',(0,1/res)),('vertical',1)])
    finally:
        gpu.state.viewport_set(*old_view);gpu.state.blend_set(old_blend)
        gpu.state.depth_test_set(old_depth);gpu.state.depth_mask_set(old_mask)
    _cache[source.key]={'signature':signature,'texture':result,'bytes':res*res*8,'shader':shader,'fragment':source.fragment}
    _cache.move_to_end(source.key);stats['builds']+=1
    while sum(v['bytes'] for v in _cache.values())>_MAX_BYTES and len(_cache)>1:_cache.popitem(last=False)
    stats['bytes']=sum(v['bytes'] for v in _cache.values())
    return result


@persistent
def clear(*args):
    global _filter_shader
    _cache.clear();_image_keys.clear();_image_seen.clear();_warnings.clear();_filter_shader=None
    stats['bytes']=0


def resolve_samplers(samplers):
    from .engine import _get_gpu_tex
    prepared={};shared={}
    for name,image in samplers:
        if getattr(image,'is_blur_source',False):
            if image.key not in shared:shared[image.key]=_get_gpu_tex(image)
            prepared[name]=shared[image.key]
    return [(name,prepared[name] if name in prepared else _get_gpu_tex(image)) for name,image in samplers]


@persistent
def undo_reset(*args):
    from . import material_shader, engine
    material_shader.invalidate()
    engine._tex_cache.clear()


def register():
    bpy.utils.register_class(VLRShaderNodeBlur);bpy.types.NODE_MT_add.append(menu)
    if clear not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(clear)
    for handlers in (bpy.app.handlers.undo_post,bpy.app.handlers.redo_post):
        if undo_reset not in handlers:handlers.append(undo_reset)


def unregister():
    clear()
    if clear in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(clear)
    for handlers in (bpy.app.handlers.undo_post,bpy.app.handlers.redo_post):
        if undo_reset in handlers:handlers.remove(undo_reset)
    bpy.types.NODE_MT_add.remove(menu);bpy.utils.unregister_class(VLRShaderNodeBlur)
