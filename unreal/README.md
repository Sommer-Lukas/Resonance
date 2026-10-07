# Unreal collaboration

The current editor project is `ResonanceVR/ResonanceVR.uproject`, associated
with **Unreal Engine 5.6**. It contains VR template and MetaHuman assets.
It is an editor starting point; Audio2Face integration, headset performance
and facial behavior have not been validated.

## Open a clone

Install Git, Git LFS and Unreal Engine 5.6. Set up LFS before cloning:

```sh
git lfs install
git clone git@github.com:Sommer-Lukas/Resonance.git
cd Resonance
git lfs pull
```

For an existing clone, run `git lfs install`, `git pull` and `git lfs pull`.
Open `unreal/ResonanceVR/ResonanceVR.uproject` in Unreal Engine 5.6.
The enabled OpenXR and MetaHuman plugins are listed in the project descriptor.
Allow the first launch to regenerate caches and compile shaders.
Opening the project requires actual LFS assets, not a ZIP containing pointer files.

## Share changes

Use an issue branch and pull request. Pull the latest changes before opening
the editor, and save assets before committing. Coordinate ownership of maps
and assets: `.uasset` and `.umap` files cannot be merged as text. Git LFS stores
these files and imported `.fbx` meshes; it does not automatically prevent
simultaneous edits. GitHub LFS storage and download usage apply.

Commit the `.uproject`, project `Config`, shared `Content`, and any future
`Source`, source plugins and required `Build` resources. The repository ignores
`Binaries`, `DerivedDataCache`, `Intermediate`, `Saved`, generated IDE files,
local developer content and per-user editor settings. These files are generated
locally; they are not needed in a clone of this project. Binary-only third-party
plugins would need a separately documented installation path.

Keep machine credentials local. The Android file-server `SecurityToken` is
empty in shared configuration; configure a private token locally before using
authenticated file-server access.

Epic/MetaHuman and other vendor assets retain their own license terms; the
repository MIT license does not relicense them. Project scope remains the
face experiment described in the root README.
