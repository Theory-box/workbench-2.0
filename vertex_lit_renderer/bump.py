"""Height derivatives and surface-gradient normals for Blender's Bump node."""
import re


def emit(t, node):
    normal = node.inputs.get('Normal')
    default = 'vlrReliefNormal' if t.parallax_shift is not None else 'normalize(vNrm)'
    default = '(gl_FrontFacing ? '+default+' : -('+default+'))'
    if not t.normal_context:
        t.notes.append('Bump requires a surface rendering context')
        return 'vec3(0.0,0.0,1.0)'
    base = t.input_expr(node, normal, 'vec3') if normal.is_linked else default
    if node.mute or not node.inputs['Height'].is_linked:
        return base
    strength = t.input_expr(node, node.inputs['Strength'], 'float')
    distance = t.input_expr(node, node.inputs['Distance'], 'float')
    width = t.input_expr(node, node.inputs.get('Filter Width'), 'float') if node.inputs.get('Filter Width') else '0.1'
    from .node_transpiler import Param
    invert = 'uP_' + str(len(t.params)+1)
    t.params.append(Param(invert, 'float', node.name, 'property', 'invert', t._cur_tree()))
    t.param_decls.append('uniform float '+invert+';')
    name = t._new_var('bump')
    # Compile the height branch once as a function, sampled at three coordinate
    # positions. Keep its locals separate from the color/normal-chain graph.
    lines, cache = t.lines, t._sock_var
    t.lines, t._sock_var = [], {}
    try:
        height = t.input_expr(node, node.inputs['Height'], 'float')
        body = '\n'.join(t.lines) + '\nreturn '+height+';'
    finally:
        t.lines, t._sock_var = lines, cache
    roots = {'vUV','vGenerated','vObjPos','vWpos','vColor',*t.uv_maps.values()}
    pattern = r'\b('+'|'.join(sorted(roots))+r')\b'
    body = re.sub(pattern, lambda m:'('+m[0]+' + dFdx('+m[0]+')*delta.x + dFdy('+m[0]+')*delta.y)', body)
    t.bump_functions.append('float '+name+'_height(vec2 delta, vec2 vlrOffset) {\n'+body+'\n}')
    offset = 'vlrOffset' if t.parallax_shift is not None else 'vec2(0.0)'
    t._line('float '+name+'_w = max('+width+', 0.00001);')
    t._line('float '+name+'_h = '+name+'_height(vec2(0.0),'+offset+');')
    t._line('vec2 '+name+'_dh = vec2('+name+'_height(vec2('+name+'_w,0.0),'+offset+'), '+name+'_height(vec2(0.0,'+name+'_w),'+offset+')) - '+name+'_h;')
    t._line('vec3 '+name+'_n = normalize('+base+');')
    t._line('vec3 '+name+'_x = cross(dFdy(vWpos),'+name+'_n);')
    t._line('vec3 '+name+'_y = cross('+name+'_n,dFdx(vWpos));')
    t._line('float '+name+'_det = dot(dFdx(vWpos),'+name+'_x);')
    t._line('vec3 '+name+' = '+name+'_n;')
    t._line('if (abs('+name+'_det)>1e-20) {')
    t._line('vec3 candidate = '+name+'_w*abs('+name+'_det)*'+name+'_n - '+distance+'*(1.0-2.0*'+invert+')*(gl_FrontFacing ? 1.0 : -1.0)*sign('+name+'_det)*('+name+'_dh.x*'+name+'_x + '+name+'_dh.y*'+name+'_y);')
    t._line('if (dot(candidate,candidate)>1e-30) '+name+' = normalize(mix('+name+'_n,normalize(candidate),max('+strength+',0.0)));')
    t._line('}')
    return name
