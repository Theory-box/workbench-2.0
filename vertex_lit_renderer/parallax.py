"""Explicit, material-local height relief. No geometry or lightmap UV mutation."""
import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty, BoolProperty

NODE_ID = 'VLRShaderNodeParallax'


def changed(self, context):
    tree = self.id_data
    tree.update_tag()
    from . import material_shader
    for mat in bpy.data.materials:
        if mat.node_tree == tree:
            material_shader.mark_dirty(mat.name)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()


class VLRShaderNodeParallax(bpy.types.ShaderNodeCustomGroup):
    bl_idname = NODE_ID
    bl_label = 'Workbench 2.0 Parallax'
    bl_description = 'Height relief for Workbench 2.0; connect to Material Output Displacement'
    depth: FloatProperty(name='Depth', default=0.05, min=0.0, soft_max=0.5,
                         description='Relief depth in world units', update=changed)
    midlevel: FloatProperty(name='Midlevel', default=0.5, min=0.0, max=1.0, update=changed)
    steps: IntProperty(name='Quality', default=32, min=8, max=128,
                       description='Maximum ray steps; higher values cost more GPU time', update=changed)
    self_shadow: BoolProperty(name='Sun Self-Shadow', default=True, update=changed)
    self_ao: BoolProperty(name='Height AO', default=True, description='Include height relief in Cavity World AO; uses the scene AO controls', update=changed)
    shadow_steps: IntProperty(name='Shadow Quality', default=24, min=8, max=128, update=changed)
    shadow_height: FloatProperty(name='Shadow Height', default=1.0, min=0.0, max=20.0, soft_max=4.0,
        description='Sun self-shadow height multiplier only; 1 preserves normal shadows, 0 disables them. Does not change visible relief or AO', update=changed)
    uv_map: StringProperty(name='UV Map', description='Blank uses render-active UV; match the height texture UV map', update=changed)

    def init(self, context):
        # A zero-displacement group supplies a harmless fallback in other engines.
        tree = bpy.data.node_groups.get('.Workbench 2.0 Parallax Fallback')
        if tree is None:
            tree = bpy.data.node_groups.new('.Workbench 2.0 Parallax Fallback', 'ShaderNodeTree')
            height = tree.interface.new_socket(name='Height', in_out='INPUT', socket_type='NodeSocketFloat')
            height.default_value = 0.5
            height.min_value = 0.0; height.max_value = 1.0
            tree.interface.new_socket(name='Displacement', in_out='OUTPUT', socket_type='NodeSocketVector')
            tree.nodes.new('NodeGroupOutput')
        self.node_tree = tree
        self.width = 225

    def draw_buttons(self, context, layout):
        layout.prop(self, 'depth'); layout.prop(self, 'midlevel'); layout.prop(self, 'steps')
        layout.prop(self, 'self_shadow')
        if self.self_shadow:
            layout.prop(self, 'shadow_height')
            layout.prop(self, 'shadow_steps')
        layout.prop(self, 'self_ao')
        obj = context.object
        if obj is not None and obj.type == 'MESH':
            layout.prop_search(self, 'uv_map', obj.data, 'uv_layers')
        else:
            layout.prop(self, 'uv_map')
        layout.label(text='Connect to Output Displacement')
        layout.label(text='UV relief; silhouette stays flat')


def menu(self, context):
    if context.space_data.tree_type == 'ShaderNodeTree':
        op = self.layout.operator('node.add_node', text='Workbench 2.0 Parallax')
        op.type = NODE_ID; op.use_transform = True


def active_node(mat):
    tree = getattr(mat, 'node_tree', None)
    if tree is None: return None
    out = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
    if out is None: return None
    socket = out.inputs.get('Displacement')
    seen = set()
    while socket is not None and socket.is_linked:
        node = socket.links[0].from_node
        if node.as_pointer() in seen: return None
        seen.add(node.as_pointer())
        if node.bl_idname == NODE_ID:
            return None if node.mute else node
        if node.type != 'REROUTE': return None
        socket = node.inputs[0]
    return None


def compile_height(t, node):
    """Use the same graph compiler/uniform pool, with a parameterized UV root."""
    selected = node.uv_map
    source = t.uv_maps.setdefault(selected, 'vNamedUV' + str(len(t.uv_maps))) if selected else 'vUV'
    t.parallax_shift = '(vlrUV - ' + source + ')'
    height = t.input_expr(node, node.inputs['Height'], 'float')
    body = '\n'.join(t.lines)
    # Capture texture gradients once before divergent ray traversal.
    import re
    gradients = []
    def sample(match):
        sampler, coords = match.groups()
        index = str(len(gradients))
        dx, dy = 'vlrHDx'+index, 'vlrHDy'+index
        gradients.append('vec2 '+dx+', '+dy+';')
        return ('if (setup) { '+dx+' = dFdx('+coords+'); '+dy+' = dFdy('+coords+'); }\n'
                + match.group(0).replace('texture('+sampler+', '+coords+')',
                    'textureGrad('+sampler+', '+coords+', '+dx+', '+dy+')'))
    # Match whole sampling declarations, leaving any UV extension/clamp handling intact.
    body = re.sub(r'vec4 n_\w+ = texture\((uTx_\d+), ([^;]+)\);', sample, body)
    function = ('\n'.join(gradients) + '\nfloat vlrHeight(vec2 vlrUV, bool setup) {\n' + body
                + '\nreturn clamp(' + height + ', 0.0, 1.0);\n}\n')
    for prop in ('depth', 'midlevel', 'steps', 'self_shadow', 'shadow_steps', 'shadow_height', 'self_ao'):
        name = 'uParallax_' + prop
        from .node_transpiler import Param
        t.params.append(Param(name, 'float', node.name, 'property', prop))
        t.param_decls.append('uniform float ' + name + ';')
    t.lines = []; t._sock_var = {}
    t.parallax_shift = 'vlrOffset'
    return source, function + TRACE


TRACE = '''
uniform mat4 uViewProj;
vec3 vlrReliefNormal;
vec3 vlrReliefU, vlrReliefV, vlrReliefN;
vec2 vlrReliefHit;
float vlrReliefDepth = 0.0;
uniform vec4 uReliefAO; // strength, world radius, world bias, sample budget
uniform float uReliefAORidge;
// Eight world-space horizon directions, with a fixed physical reach at every quality.
// Unlike screen AO this sees the virtual height field, including off-screen texels.
float vlrReliefAOFactor() {
    if (uParallax_self_ao < 0.5 || vlrReliefDepth <= 0.0 ||
        (uReliefAO.x <= 0.0 && uReliefAORidge <= 0.0)) return 1.0;
    vec3 N = vlrReliefN;
    vec3 axis = abs(N.z) < 0.9 ? vec3(0,0,1) : vec3(0,1,0);
    vec3 T = normalize(cross(axis,N)), B = cross(N,T);
    float radius = max(uReliefAO.y, 0.00001);
    float height = vlrHeight(vlrReliefHit, false);
    int steps = int(clamp(uReliefAO.w / 8.0, 2.0, 8.0));
    float occ = 0.0, ridge = 0.0;
    for (int d=0; d<8; ++d) {
        float angle = float(d) * 0.785398163;
        vec3 D = cos(angle)*T + sin(angle)*B;
        vec2 duv = vec2(dot(D,vlrReliefU),dot(D,vlrReliefV));
        float horizon = 0.0, exposed = 0.0;
        // Subtract the local tangent: a uniformly tilted height plane is not a crevice.
        float tangent = -dot(vlrReliefNormal,D) / max(dot(vlrReliefNormal,N),0.05);
        for (int i=1; i<=8; ++i) {
            if (i>steps) break;
            float t = float(i) / float(steps);
            float r = radius * t*t;
            float dz = (vlrHeight(vlrReliefHit + duv*r, false)-height)*vlrReliefDepth;
            float above = max(dz - tangent*r - uReliefAO.z, 0.0);
            float below = max(tangent*r - dz - uReliefAO.z, 0.0);
            float falloff = 1.0 - 0.5*t*t;
            horizon = max(horizon, above*above / (r*r + above*above) * falloff);
            exposed = max(exposed, below*below / (r*r + below*below) * falloff);
        }
        occ += horizon; ridge += exposed;
    }
    return clamp(1.0 - occ*uReliefAO.x/8.0,0.0,1.0) * (1.0 + ridge*uReliefAORidge/8.0);
}
// Direction-independent height-field visibility; only sunlight consumes it for now.
float vlrReliefVisibility(vec3 L) {
    float shadowDepth = vlrReliefDepth * uParallax_shadow_height;
    if (uParallax_self_shadow < 0.5 || shadowDepth <= 0.0) return 1.0;
    float facing = dot(L, vlrReliefN);
    if (facing <= 0.001) return 0.0;
    float h = vlrHeight(vlrReliefHit, false);
    float travel = 1.0 - h;
    if (travel < 0.0001) return 1.0;
    vec2 slope = vec2(dot(L,vlrReliefU),dot(L,vlrReliefV)) * shadowDepth / facing;
    int count = int(clamp(uParallax_shadow_steps,8.0,128.0));
    for (int i=1; i<=128; ++i) {
        if (i>count) break;
        float dz = travel * float(i) / float(count);
        if (vlrHeight(vlrReliefHit + slope*dz, false) > h + dz + 0.002) return 0.0;
    }
    return 1.0;
}
vec2 vlrFinishRelief(vec2 uv, vec2 offset, vec3 px, vec3 py, vec2 ux, vec2 uy, vec3 N, float det, float fade) {
    vec2 hit = uv + offset;
    vlrReliefHit = hit;
    vlrReliefN = N;
    vlrReliefU = (ux.x*cross(py,N) + uy.x*cross(N,px))/det;
    vlrReliefV = (ux.y*cross(py,N) + uy.y*cross(N,px))/det;
    vlrReliefDepth = uParallax_depth * fade;
    float hx = vlrHeight(hit + ux * 0.5, false) - vlrHeight(hit - ux * 0.5, false);
    float hy = vlrHeight(hit + uy * 0.5, false) - vlrHeight(hit - uy * 0.5, false);
    vec3 gradient = (cross(py,N)*hx + cross(N,px)*hy) / det;
    vlrReliefNormal = normalize(normalize(vNrm) - gradient * uParallax_depth * fade);
    return offset;
}
vec2 vlrParallaxOffset(vec2 uv) {
    vlrReliefDepth = 0.0;
    vlrReliefNormal = normalize(vNrm);
    float initialHeight = vlrHeight(uv, true);
    vec3 px = dFdx(vWpos), py = dFdy(vWpos);
    vec2 ux = dFdx(uv), uy = dFdy(uv);
    vec3 crossP = cross(px, py);
    if (dot(crossP, crossP) < 1e-24 || uParallax_depth <= 0.0) return vec2(0.0);
    vec4 clip = uViewProj * vec4(vWpos, 1.0);
    mat4 invVP = inverse(uViewProj);
    vec4 nearP = invVP * vec4(clip.xy / clip.w, -1.0, 1.0);
    vec4 farP = invVP * vec4(clip.xy / clip.w, 0.9, 1.0);
    vec3 V = normalize(nearP.xyz / nearP.w - farP.xyz / farP.w);
    vec3 N = normalize(crossP);
    if (dot(N,V) < 0.0) N = -N;
    float facing = dot(N,V);
    // Fade extreme grazing rays instead of allowing unbounded UV travel.
    float fade = smoothstep(0.03, 0.15, facing);
    float det = dot(px, cross(py,N));
    if (abs(det) < 1e-16) return vec2(0.0);
    vec2 ray = (ux * dot(V,cross(py,N)) + uy * dot(V,cross(N,px))) / det;
    ray *= uParallax_depth * fade / max(facing, 0.03);
    int steps = int(clamp(uParallax_steps, 8.0, 128.0));
    float layer = 1.0;
    vec2 offset = ray * (layer - uParallax_midlevel);
    float prev = layer - vlrHeight(uv + offset, false);
    if (prev <= 0.0) return vlrFinishRelief(uv, offset, px, py, ux, uy, N, det, fade);
    float upper = layer;
    for (int i=0; i<128; ++i) {
        if (i >= steps) break;
        upper = layer;
        layer -= 1.0 / float(steps);
        offset = ray * (layer - uParallax_midlevel);
        if (layer - vlrHeight(uv + offset, false) <= 0.0) break;
    }
    // Refine the first intersection for stable relief at moderate step counts.
    for (int i=0; i<5; ++i) {
        float middle = (upper + layer) * 0.5;
        if (middle > vlrHeight(uv + ray * (middle-uParallax_midlevel), false)) upper = middle;
        else layer = middle;
    }
    offset = ray * ((upper + layer) * 0.5 - uParallax_midlevel);
    return vlrFinishRelief(uv, offset, px, py, ux, uy, N, det, fade);
}
'''


def register():
    bpy.utils.register_class(VLRShaderNodeParallax)
    bpy.types.NODE_MT_add.append(menu)


def unregister():
    bpy.types.NODE_MT_add.remove(menu)
    bpy.utils.unregister_class(VLRShaderNodeParallax)


def bind_uvs(shader, prog, depsgraph, object_name):
    """Default and explicitly named references to the same mesh UV move together."""
    obj = bpy.data.objects.get(object_name)
    mesh = obj.evaluated_get(depsgraph).data if obj is not None else None
    layers = getattr(mesh, 'uv_layers', ())
    active = next((uv.name for uv in layers if uv.active_render), '')
    selected = prog['parallax_uv_map'] or active
    for name, uniform in prog['parallax_uv_matches'].items():
        try: shader.uniform_float(uniform, float((name or active) == selected))
        except ValueError: pass  # unused coordinate root optimized away
