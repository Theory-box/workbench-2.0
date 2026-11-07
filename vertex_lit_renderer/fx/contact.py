"""Short-range depth-buffer sun visibility, composited before ambient effects.

The MRT contains only the live sun's contribution. No scene redraw, temporal
history, or darkening of baked/ambient light is needed. Missing depth stays lit.
"""
from .effect import ScreenEffect


def enabled(vls):
    return bool(vls and getattr(vls, 'use_contact_shadows', False)
                and getattr(vls, 'sun_intensity', 0) > 0
                and getattr(vls, 'view_mode', 'TEXTURED') not in ('NORMAL', 'DEPTH'))


class ContactShadows(ScreenEffect):
    name = 'contact_shadows'
    uses_depth = True
    frag = '''
uniform sampler2D uColor;
uniform sampler2D uDepth;
uniform sampler2D uSun;
uniform mat4 uProj;
uniform mat4 uInvProj;
uniform vec3 uLight;
uniform float uLength;
uniform float uThickness;
uniform int uSteps;
in vec2 vUV;
out vec4 fragColor;
vec3 positionAt(vec2 uv, float d) {
    vec4 p = uInvProj * vec4(uv * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
    return p.xyz / p.w;
}
void main() {
    vec4 col = texture(uColor, vUV);
    vec4 sun = texture(uSun, vUV);
    float depth = texture(uDepth, vUV).r;
    fragColor = col;
    // Only the exact clear depth is background. Perspective depth is very
    // compressed at distance; an epsilon here rejects valid far geometry.
    if (depth >= 1.0 || sun.a < 0.999 || max(sun.r, max(sun.g, sun.b)) <= 0.0) return;
    vec3 p = positionAt(vUV, depth);
    float stepSize = uLength / float(uSteps);
    float bias = max(0.0001, uThickness * 0.05);
    float occlusion = 0.0;
    for (int i = 1; i <= 64; ++i) {
        if (i > uSteps) break;
        float t = stepSize * float(i);
        vec3 q = p + normalize(uLight) * t;
        vec4 clip = uProj * vec4(q, 1.0);
        if (clip.w <= 0.0) break;
        vec3 ndc = clip.xyz / clip.w;
        vec2 uv = ndc.xy * 0.5 + 0.5;
        if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0))) || abs(ndc.z) >= 1.0) break;
        float d = texture(uDepth, uv).r;
        if (d >= 1.0) continue;
        float gap = positionAt(uv, d).z - q.z;
        if (gap > bias && gap < uThickness) {
            float border = min(min(uv.x, uv.y), min(1.0-uv.x, 1.0-uv.y));
            occlusion = (1.0 - smoothstep(0.8, 1.0, t/uLength)) * smoothstep(0.0, 0.02, border);
            break;
        }
    }
    fragColor = vec4(col.rgb - min(max(sun.rgb, vec3(0.0)), max(col.rgb, vec3(0.0))) * occlusion, col.a);
}
'''

    def enabled(self, vls):
        return enabled(vls)

    def set_uniforms(self, shader, ctx):
        shader.uniform_sampler('uSun', ctx['sun_tex'])
        shader.uniform_float('uProj', ctx['proj'])
        shader.uniform_float('uInvProj', ctx['inv_proj'])
        shader.uniform_float('uLight', ctx['contact_sun_dir'])
        shader.uniform_float('uLength', ctx['contact_length'])
        shader.uniform_float('uThickness', ctx['contact_thickness'])
        shader.uniform_int('uSteps', ctx['contact_steps'])
