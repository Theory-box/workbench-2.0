import bpy,sys,pathlib,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
import vertex_lit_renderer as addon
from vertex_lit_renderer import engine
addon.register();bpy.context.scene.render.engine='VERTEX_LIT'
bpy.context.scene.vertex_lit.use_shadows=False
original=engine._RangeDraw.draw
def fail(*args):raise RuntimeError('Injected object draw failure')
engine._RangeDraw.draw=fail
errors=[]
draw_original=engine.VertexLitEngine._draw_batches
def draw_probe(self,*args,**kwargs):
 try:return draw_original(self,*args,**kwargs)
 except RuntimeError as exc:
  errors.append(str(exc));raise
engine.VertexLitEngine._draw_batches=draw_probe
def run():
 try:
  failed=False
  try:bpy.ops.render.render()
  except RuntimeError as exc:
   assert 'Injected object draw failure' in str(exc),str(exc)
   failed=True
  assert any('Injected object draw failure' in x for x in errors),errors
  print('PASS final object draw failure propagates to render error handler')
 finally:
  engine._RangeDraw.draw=original
  bpy.ops.wm.quit_blender()
bpy.app.timers.register(run,first_interval=1)
