"""Run with Blender --background --factory-startup --python <this file>."""
import json
import pathlib
import sys
from mathutils import Matrix, Vector, Euler
repo = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo))
from vertex_lit_renderer.engine import _build_light_space_fit

near, far = .1, 100.0
count = 0
max_xy = 0.0
for rotation, translation in [((0, 0, 0), (0, 0, 0)), ((.3, -.4, .7), (50, -20, 10))]:
    camera = Euler(rotation).to_matrix().to_4x4()
    camera.translation = translation
    for half_width, half_height in [(20, .1), (5, 5)]:
        projection = Matrix(((1/half_width, 0, 0, 0), (0, 1/half_height, 0, 0),
                             (0, 0, -2/(far-near), -(far+near)/(far-near)), (0, 0, 0, 1)))
        for distance in (1, 25, 1000):
            for resolution in (1024, 2048, 4096):
                for light in ((12.7, 0, 20), (0, 0, 1), (0, 1, 0), (-1, 0, 0)):
                    light = camera.to_3x3() @ Vector(light).normalized()
                    fit, texel = _build_light_space_fit(light, projection @ camera.inverted(),
                                                        camera.translation, distance, resolution, 100)
                    assert texel > 0
                    for x in (-half_width, half_width):
                        for y in (-half_height, half_height):
                            for z in (-near, -min(far, distance)):
                                p = fit @ (camera @ Vector((x, y, z, 1)))
                                extent = max(abs(p.x/p.w), abs(p.y/p.w))
                                max_xy = max(max_xy, extent)
                                assert extent <= 1.00001, (rotation, distance, resolution, light, tuple(p))
                                assert -1.00001 <= p.z/p.w <= 1.00001
                                count += 1
report = {'pass': True, 'corners_checked': count, 'max_xy': max_xy}
out = repo.parent/'work'/'sun-audit-results';out.mkdir(parents=True, exist_ok=True)
(out/'frustum-coverage.json').write_text(json.dumps(report, indent=2))
print(report)
