# CharMorph

CharMorph is a character creation tool for Blender.

It uses base meshes and morphs from ManuelbastioniLAB/MB-Lab but it's designed for easy creation of new models and easy modification of existing ones.

This addon includes from-scratch reimplementaion of most of MB-Lab features but it currently doesn't contain any MB-Lab code.
It uses different database format and has more internal differences.
It uses much less hard coded features. It is planned that CharMorph won't be limited to humanoids. Animals and other creatures are welcome at CharMorph too.

It is not ready for practical use yet, but if you like MB-Lab and interested in development similar software feel free to write me :)

## Options:

* **Use local materials:**

  Make a copy of local materials instead of importing them every time.

  It is safe if you're creating scene from scratch, but it is recommended to disable this option if you already have MB-Lab characters on the scene.

## Differences from MB-Lab:

* Direct setting of skin and eyes color
* Material displacement instead of displacement modifier.
  No real displacement in EEVEE, but nice live preview with bumps is available.
  In Cycles skin material is set to "Displacement and bump" by default.
* Hairstyles
* Realtime asset fitting
* Rigify support with full face rig
* Characters are created at 3D cursor location, not always at world origin

## Downsides

* Library size is higher because shapekeys in .blend files take more space than morphs in .json files. I plan to fix it by moving morphs to separate npy/npz files.
* It is mainly targeted to Rigify so rig is added only at finalization
* Still lacking some features (Automodelling, measures) just because I don't use them in my projects. Maybe they'll come later.
