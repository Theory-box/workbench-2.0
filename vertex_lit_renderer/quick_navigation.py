"""Per-viewport temporary parallax bypass; never changes scene/material settings."""
import bpy
import time

IDLE_DELAY = 0.2 / 3.0


def note_updates(engine, updates):
    if any(isinstance(u.id, bpy.types.Object) and
           (u.is_updated_transform or (u.is_updated_geometry and u.id.mode == 'EDIT'))
           for u in updates):
        engine._quick_motion_pending = True


def update(engine, context, settings):
    rv = context.region_data
    signature = tuple(v for matrix in (rv.view_matrix, rv.window_matrix) for row in matrix for v in row)
    previous = getattr(engine, '_quick_view', None)
    engine._quick_view = signature
    changed = getattr(engine, '_quick_motion_pending', False)
    engine._quick_motion_pending = False
    playing = getattr(context.screen, 'is_animation_playing', False)
    parallax = bool(settings and settings.use_parallax and settings.quick_navigation)
    supersampling = bool(settings and settings.quick_supersampling and settings.supersampling != '1')
    enabled = parallax or supersampling
    if enabled and ((previous is not None and previous != signature)
                    or getattr(rv, 'is_navigating', False) or playing):
        changed = True
    now = time.monotonic()
    if enabled and changed:
        engine._quick_changed = now
    active = enabled and now - getattr(engine, '_quick_changed', -1000.0) < IDLE_DELAY
    engine._quick_parallax = active and parallax
    engine._quick_supersampling = active and supersampling
    if active and not getattr(engine, '_quick_timer', False):
        engine._quick_timer = True
        area = context.area
        def redraw():
            try:
                engine._quick_timer = False
                area.tag_redraw()
            except (ReferenceError, RuntimeError):
                pass
        bpy.app.timers.register(redraw, first_interval=max(0.001, IDLE_DELAY - (now - engine._quick_changed)))
    return active
