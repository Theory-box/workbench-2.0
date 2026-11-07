# vertex_lit_renderer/material_shader.py
"""
Per-material shader builder + cache (structure- and mode-aware).

Wraps node_transpiler: turns a material's node graph into a fragment that
computes base colour live, pairs it with the mode-appropriate vertex shader
(Gouraud passes vLight; Phong passes world pos/normal and lights per-fragment),
compiles, and caches per (material, shading_mode).

Recompile policy: keyed by node_transpiler.topo_signature(mat) AND shading mode.
Value edits (Mapping scale, mix factor, colours…) are uniforms -> no recompile.
Structure edits or a mode switch -> recompile. Compile happens at draw time; on
failure the engine falls back to the legacy texture path for that material.
"""

from __future__ import annotations
import gpu

from . import shaders as _sh
from . import node_transpiler as _nt
from . import instancing as _instancing

# (mat.name, mode) -> {shader, samplers, params, failed, notes, sig, frag, error}
_prog_cache = {}
_dirty_mats = set()
_shader_cache = {}  # identical GLSL shares a GPU program; material bindings stay separate


def _prune_shaders():
    used = {id(e['shader']) for e in _prog_cache.values() if e.get('shader') is not None}
    for key in list(_shader_cache):
        if id(_shader_cache[key]) not in used:
            del _shader_cache[key]


def _heads(mode):
    if mode == "WORKBENCH":
        return (_sh.PHONG_VERT, _sh.MAT_FRAG_HEAD_WORKBENCH,
                _sh.MAT_FRAG_MAIN_WORKBENCH, "")
    # PIXEL (default): per-fragment scene lighting
    return _sh.PHONG_VERT, _sh.MAT_FRAG_HEAD_PIXEL, _sh.MAT_FRAG_MAIN_PIXEL, _sh.LIGHT_CHUNK


def build_material_frag(mat, mode="PIXEL"):
    """Return (vertex_src, frag_src, transpile_result). No GPU needed."""
    res = _nt.transpile_material(mat, parallax_enabled=True)
    vert, head, main, light = _heads(mode)
    if "vlrParallaxOffset" in res.glsl:
        if "in vec3 vWpos;" not in head:
            head += "in vec3 vWpos;\n"
        # Resolve the visible height intersection before evaluating its lighting.
        lines = main.splitlines(True)
        base = next(line for line in lines if 'computeBaseColor(vUV)' in line)
        main = ''.join(line for line in lines if line != base)
        main = main.replace('\n', '\n' + base, 1)
        main = main.replace('normalize(vNrm)', 'vlrReliefNormal')
    for i, varying in enumerate(res.uv_maps.values()):
        vert = 'in vec2 namedUV%d;\nout vec2 %s;\n' % (i, varying) + vert
        vert = vert.replace('void main() {', 'void main() {\n    %s = namedUV%d;' % (varying, i))
        head += 'in vec2 %s;\n' % varying
    sampler_decls = "".join("uniform sampler2D {};\n".format(s.uniform) for s in res.samplers)
    param_decls = "".join(d + "\n" for d in res.param_decls)
    frag = (head + sampler_decls + param_decls + light + res.helpers + "\n"
            + res.glsl + "\n" + main)
    return vert, frag, res


def build_bake_frag(mat):
    """Return (BAKE_VERT, bake_frag, transpile_result) that outputs computeBaseColor (albedo,
    unlit) — for baking the live material graph to a UV texture."""
    res = _nt.transpile_material(mat)
    sampler_decls = "".join("uniform sampler2D {};\n".format(s.uniform) for s in res.samplers)
    param_decls = "".join(d + "\n" for d in res.param_decls)
    aliases = ''.join('#define %s vUV\n' % v for v in res.uv_maps.values())
    frag = (_sh.BAKE_FRAG_HEAD + aliases + sampler_decls + param_decls + res.helpers + "\n"
            + res.glsl + "\n" + _sh.BAKE_FRAG_MAIN)
    return _sh.BAKE_VERT, frag, res


def mark_dirty(name):
    _dirty_mats.add(name)


def invalidate(name=None):
    _instancing.clear()
    if name is None:
        _prog_cache.clear(); _dirty_mats.clear()
        _shader_cache.clear()
    else:
        for k in [k for k in _prog_cache if k[0] == name]:
            _prog_cache.pop(k, None)
        _dirty_mats.discard(name)
        _prune_shaders()


def _compile(mat, mode):
    ent = {"shader": None, "samplers": [], "params": [], "failed": False,
           "notes": [], "sig": _nt.topo_signature(mat), "error": "", "mode": mode}
    try:
        vert, frag, res = build_material_frag(mat, mode)
        ent["notes"] = res.notes
        ent["uv_maps"] = res.uv_maps
        ent["parallax_uv_matches"] = getattr(res, "parallax_uv_matches", {})
        ent["parallax_uv_map"] = getattr(res, "parallax_uv_map", None)
        ent["vert"] = vert
        # Diagnostic: how much of the graph the transpiler resolved. 0 samplers on
        # a material you expect to be textured => the image isn't in the Base Color
        # path the transpiler follows (it may be flat, or wired through other inputs).
        print("[VertexLit] live '{}' ({}): {} sampler(s), {} param(s){}".format(
            mat.name, mode, len(res.samplers), len(res.params),
            "  notes=" + str(res.notes) if res.notes else ""))
        # Fall back to the base-texture path only when the surface can't be traced to
        # a base colour at all. Individual unsupported nodes now neutralise to white
        # in-graph, so a material with e.g. an AO/Geometry node still renders its
        # supported parts (brick, mixes, textures) instead of falling back wholesale.
        if res.needs_fallback:
            ent["failed"] = True
            ent["error"] = "no traceable base colour -> base-texture fallback"
            return ent
        source_key = (vert, frag)
        shader = _shader_cache.get(source_key)
        if shader is None:
            shader = _shader_cache[source_key] = gpu.types.GPUShader(vert, frag)
        ent["shader"] = shader
        ent["samplers"] = [(s.uniform, s.image) for s in res.samplers]
        ent["params"] = res.params
        ent["has_alpha"] = res.has_alpha
        ent["frag"] = frag
    except Exception as e:                      # pragma: no cover (GPU-side)
        ent["failed"] = True
        ent["error"] = str(e)
    if ent["failed"]:
        # Surfaced in the system console so a fallback/compile issue is diagnosable.
        print("[VertexLit] material '{}' ({}): {}".format(mat.name, mode, ent["error"]))
    return ent


def get_program(mat, mode="PIXEL", may_compile=True):
    if mat is None:
        return None
    name = mat.name
    key = (name, mode)
    ent = _prog_cache.get(key)
    dirty = name in _dirty_mats

    if ent is not None and not dirty:
        return ent

    # If the caller only wants a ready program (progressive/budgeted compile), don't
    # block on a GPU compile here — report "not ready yet" so it can draw the fast
    # base-texture path this frame and try again next frame.
    if not may_compile and (ent is None or dirty):
        # a value-only edit can keep the existing compiled shader
        if ent is not None and not ent["failed"] and ent["shader"] is not None:
            try:
                if ent["sig"] == _nt.topo_signature(mat):
                    _dirty_mats.discard(name)
                    return ent
            except Exception:
                pass
        return None

    # Flagged dirty (or first build for this key). Distinguish a value-only edit
    # (params are uniforms read live -> keep the compiled shader) from a structural
    # edit (must recompile) via the structure signature.
    new_sig = _nt.topo_signature(mat)
    if ent is not None and not ent["failed"] and ent["shader"] is not None \
            and ent["sig"] == new_sig:
        _dirty_mats.discard(name)      # value-only edit: nothing to recompile
        return ent

    # First build, or a STRUCTURAL change. On a structural change the OTHER mode's
    # cached program is stale too -> drop every mode for this material so each
    # recompiles with the new structure on next use.
    if dirty:
        _instancing.clear()
        for k in [k for k in _prog_cache if k[0] == name]:
            _prog_cache.pop(k, None)
        _prune_shaders()
    ent = _compile(mat, mode)
    _prog_cache[key] = ent
    _dirty_mats.discard(name)
    return ent
