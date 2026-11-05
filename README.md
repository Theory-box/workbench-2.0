# Workbench 2.0

Experimental Blender renderer with live material-node previews, shadows, and screen-space ambient occlusion.

> **Very early development — please be careful when testing.** Expect bugs, unsupported nodes, visual differences, slowdowns, and possible crashes. Save your work, back up your projects, and test on copies of .blend files. Do not rely on this renderer for production work yet.

## Status

Current version: **0.17.4**. Development and recent tests use **Blender 4.4.3**. The add-on declares Blender 4.2 as its minimum; other versions have not been verified in this testing pass.

## Install

Zip the `vertex_lit_renderer` folder, then install that ZIP through Blender Preferences > Add-ons > Install from Disk. Enable the add-on and choose **Workbench 2.0** as the render engine. Restart Blender after replacing an existing installation.

## Known limitations

- Material graphs are translated to GLSL; support is incomplete and results can differ from Cycles or Eevee.
- Partial-alpha sRGB image colors have a known mismatch against Cycles.
- High-resolution final renders currently create Python pixel lists, increasing memory use. Array/bulk transfer alternatives passed a small API test but are not implemented in this release.
- Some GPU draw failure paths may leave incomplete final renders; this is under investigation.

## Development

`main` holds published snapshots. Use a separate branch for each fix or feature, test it in a separate Blender process, and review changes before merging into `main`.

Tests under `vertex_lit_renderer/tests` are development scripts. Some need a graphical GPU context or test fixtures and are not a universal headless test suite.
