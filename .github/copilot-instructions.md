# Layer Painter – AI Coding Assistant Instructions

## Project Overview

**Layer Painter** is a Blender add-on (v4.0+) that brings a Substance Painter-like texture painting workflow directly into Blender. It enables procedural layering, masking, and filtering for material texturing without leaving Blender.

**Key Principle**: Use **UIDs (unique identifiers)** instead of direct object references—Blender object references break during undo/redo/file reload, but UIDs provide persistent lookup.

## Critical Architecture Concepts

### Three Core Entity Types
1. **Material** (`data/materials/material.py`): Container with layers and channels. Each material has a UID stored in `material.lp.uid`.
2. **Layer** (`data/materials/layers/layer.py`): Compositing unit (FILL or PAINT type) containing multiple channels. Stores UID-based reference to parent material.
3. **Channel** (`data/materials/channels/channel.py`): Material output socket (e.g., Base Color, Normal). Data type is COLOR or TEXTURE.

### Cache Invalidation Pattern (Critical)
**Caches must be cleared in `handlers.py`** after events that invalidate Blender references:
- `on_load_handler()` → File load (most critical—all object refs become stale)
- `on_undo_redo_handler()` → Undo/redo (references shift in collections)
- `depsgraph_handler()` → Depsgraph update (after topology changes)

**Why This Matters**: 
- Blender object refs (e.g., `bpy.data.materials[0]`) are memory addresses that become invalid after undo/redo
- UIDs are stable strings—they survive all these events
- Cached refs speed up repeated lookups but MUST be cleared when the underlying objects may have changed

**Implementation**:
```python
@persistent
def on_undo_redo_handler(dummy):
    """clears caches after undo/redo operations to prevent inconsistent state"""
    channel.clear_caches()
    layer.clear_caches()

@persistent
def on_load_handler(dummy):
    """runs when a blender file is loaded"""
    channel.clear_caches()
    layer.clear_caches()
    set_material_uids()
```

**When Adding New State**: If you cache any Blender object references, add them to the corresponding `clear_caches()` function and call that function in `handlers.py`.

### UID → Object Lookup Pattern
```python
# Layer finds parent material by UID
mat_by_uid = next((m for m in bpy.data.materials if m.lp.uid == layer.mat_uid_ref), None)

# Channel finds input node socket by UID
inp_by_uid = next((i for n in mat.node_tree.nodes for i in n.inputs if hasattr(i, "uid") and i.uid == self.uid), None)
```

## Key File Directories

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `operators/` | User-triggered operations (create layer, paint, bake, etc.) | `layers.py`, `paint.py`, `channels.py`, `masks.py` |
| `data/materials/` | Data models: Material, Layer, Channel property groups | `material.py`, `layers/layer.py`, `channels/channel.py` |
| `data/materials/layers/` | Layer setup, types (FILL, PAINT) | `layer.py`, `layer_setup.py`, `layer_types/` |
| `ui/viewport/` | VIEW_3D panels for layers, materials, settings | `layers/panel_layers.py` |
| `ui/node_editor/` | NODE_EDITOR panels for channels | `channels/panel_channel.py` |
| `handlers.py` | Blender event handlers (load, undo, redo, depsgraph) | Cache invalidation logic |
| `constants.py` | Node and socket type mappings (NODES, SOCKETS dicts) |

## Paint Workflow

**Flow**: User → Paint Operator → Create/Reuse Image → Texture Paint Mode → Save to Disk

### Key Files
- `operators/paint.py`: `LP_OT_PaintChannel` (start), `LP_OT_StopPainting` (finish)
- `operators/utils_paint.py`: Image creation, painting mode setup, saving logic
- `data/materials/layers/layer_types/layer_fill.py`: Channel texture node setup

### Paint Operator Pattern (`LP_OT_PaintChannel`)
```python
def invoke(self, context, event):
    # 1. Set up texture nodes if needed (convert COLOR → TEXTURE)
    if not tex.image:
        return context.window_manager.invoke_props_dialog(self, width=300)  # Show resolution dialog
    return self.execute(context)

def execute(self, context):
    # 2. Create image (or reuse existing)
    img = utils_paint.create_image("image", resolution, color, is_data=channel.is_data)
    tex.image = img
    
    # 3. Save unsaved images to disk
    utils_paint.save_all_unsaved()
    
    # 4. Switch to texture paint mode
    utils_paint.paint_image(img)
```

### Image Storage Pattern
- **Unsaved images in memory**: Referenced by texture nodes, persist in .blend
- **Persistent images**: Saved to `<blend_dir>/layer_painter_textures/` with names like `Material.001_BaseColor.png`
- **Data vs Color**: Use `is_data=True` for Normal/Roughness (linear), `is_data=False` for Color/Emissive (sRGB)

---

## Baking System

**Flow**: Setup (emissive + texture node) → Render Bake → Save Image → Cleanup

### Key Files
- `operators/baking.py`: `LP_OT_BakeSetupChannel`, `LP_OT_BakeCleanupChannel`, `LP_OT_BakeFinish`
- Uses macro pattern to chain multiple bake operations across channels
- Constants: `EXPORT_OUT_NAME` (emission output), `BAKE_IMG_NODE` (temp texture), `BAKE_IMG_NAME` (temp image)

### Baking Operator Pattern
```python
# Setup: Connect channel output → emission node → output
def add_bake_setup(self, ntree):
    out = ntree.nodes.new(constants.NODES["OUT"])
    out.name = constants.EXPORT_OUT_NAME
    out.is_active_output = True
    
    emit = ntree.nodes.new(constants.NODES["EMIT"])
    emit.name = constants.EXPORT_EMIT_NAME
    ntree.links.new(emit.outputs[0], out.inputs[0])
    
    # Connect channel value to emission
    ntree.links.new(channel.inp.links[0].from_socket, emit.inputs[0])
    return emit

# Cleanup: Save image to disk, remove temp nodes
def remove_bake_setup(self, ntree):
    ntree.nodes.remove(ntree.nodes[constants.EXPORT_OUT_NAME])
    ntree.nodes.remove(ntree.nodes[constants.EXPORT_EMIT_NAME])
```

### Macro Chain Pattern
```python
# Multiple bake setups are chained in a macro
# Each bake operation is sequential: Setup → Render → Cleanup → Next Channel
# IS_BAKING flag prevents concurrent operations
# Timer-based polling checks render completion
```

---

## Node Tree Manipulation Patterns

### Key Files
- `data/utils_nodes.py`: Tree organization and traversal
- `data/utils_groups.py`: Node group creation/editing helpers
- `data/materials/layers/layer_setup.py`: Layer group initialization
- `data/materials/layers/layer_channels.py`: Channel input/output setup

### Common Patterns

#### 1. Recursive Node Cleanup
```python
# Remove node and all connected upstream nodes
def remove_connected_left(ntree, node):
    for inp in node.inputs:
        for link in inp.links:
            remove_connected_left(ntree, link.from_node)  # Recurse
    ntree.nodes.remove(node)
```

#### 2. Organize Tree Layout (Right-to-Left)
```python
# Build node columns from output node backwards
nodes = __get_node_list(ntree, start_node)  # List of node lists by horizontal distance

# Position columns with spacing
x_offset = start_node.location[0] - start_node.width - spacing
for column in nodes:
    for node in column:
        node.location = (x_offset, y_offset)
```

#### 3. Add Group Input/Output with UID
```python
# Create group socket and link
inp, group_inp = utils_groups.add_input(layer.node, SOCKETS["COLOR"], "ChannelName")
group_inp.uid = channel.uid  # Store UID for later lookup

out, group_out = utils_groups.add_output(layer.node, SOCKETS["COLOR"], "ChannelName")
group_out.uid = channel.uid  # Must match input UID
```

#### 4. Channel Endpoint Creation
```python
# Each layer needs input/output for each channel
# Inputs receive data from channel source (COLOR or TEXTURE)
# Outputs send to layer above via stack connections
def __add_channel_endpoints(layer, channel):
    inp, group_inp = utils_groups.add_input(layer.node, channel.inp.bl_rna.identifier, channel.name)
    group_inp.uid = channel.uid  # Critical: UID matches channel.uid
    
    out, group_out = utils_groups.add_output(layer.node, channel.inp.bl_rna.identifier, channel.name)
    group_out.uid = channel.uid  # Must be same UID as input
```

---

## Common Workflows

### Adding UI
- Panels inherit from `bpy.types.Panel` with `bl_space_type` set to VIEW_3D or NODE_EDITOR.
- Always implement `poll()` classmethod using `utils_ui.base_poll(context)`.
- Call `utils.redraw()` after state changes to refresh UI.

### Adding Operators
- Inherit from `bpy.types.Operator`, set `bl_idname = "lp.<action>"`.
- Use `@classmethod` `poll()` with `utils_operator.base_poll(context)`.
- Always return `{"FINISHED"}` or `{"CANCELLED"}`.
- Pass material/layer UIDs as StringProperty parameters (not direct references).

### Caching Node/Material References
When caching is needed, use module-level globals in corresponding file:
```python
# In data/materials/layers/layer.py
cached_materials = {}
cached_nodes = {}

def clear_caches():
    global cached_materials, cached_nodes
    cached_materials = {}
    cached_nodes = {}
```

## Type System & Node Naming Conventions

### Layer Types
- **FILL**: Procedurally generated (solid colors, patterns).
- **PAINT**: Texture-based (image textures).

### Node Constants (from `constants.py`)
- `NODES["TEX"]` → `ShaderNodeTexImage`
- `NODES["GROUP"]` → `ShaderNodeGroup`
- `SOCKETS["COLOR"]` → `NodeSocketColor`

Use these constants for node creation—not string literals.

## UID Strategy

**UID Format**: 10-character hex string (e.g., `"a1b2c3d4e5"`), generated by `utils.make_uid()`.

**Where UIDs Live**:
- Material UID: `material.lp.uid`
- Layer UID: `layer.uid` (also matches its node group UID)
- Channel UID: `channel.uid`
- Stored as StringProperty to survive undo/redo.

**Why UIDs**: Blender object references (`bpy.types` instances) become invalid after undo/redo/file load. UIDs provide stable identifiers to re-lookup objects.

## Critical Gotchas & Debugging

### Stale Object References
**Problem**: After undo/redo/file load, code like `mat = bpy.data.materials["MyMat"]` may return a *different object* in memory than before the operation.
- **Solution**: Always use UIDs for lookups, never store direct references
- **Debug**: If UI doesn't update after undo, check `handlers.py` cache clearing

### Missing Layer/Channel Nodes
**Error**: `RuntimeError: Couldn't find layer node for 'X'. Delete layer to proceed.`
- **Cause**: Layer node group was deleted or orphaned during a failed operation
- **Prevention**: Always validate `layer.node` exists before accessing; use `clear_caches()` after depsgraph changes

### Circular Imports
- Avoid importing from `ui/` into `data/` or `operators/`
- Import order in `__init__.py` matters—`data` must register before `operators`

### Image Not Saving
- Check `constants.TEX_DIR_NAME` folder exists
- Verify image has correct `is_data` flag (affects colorspace)
- Call `utils_paint.save_all_unsaved()` before switching modes

---

## Development Checklist

Before submitting changes:
1. Test layer create/move/delete/undo (Ctrl+Z, Ctrl+Shift+Z).
2. Test paint workflow and texture creation.
3. Verify cache invalidation on file load.
4. Check no direct Blender object references are stored (use UIDs instead).
5. Update handlers.py if adding new undo/redo-sensitive state.
6. Verify all cached references have corresponding `clear_caches()` calls in `handlers.py`.

## Entry Point

The add-on registers via `__init__.py` `register()` function, which calls:
1. `handlers.register()`
2. `data.register()`
3. `addon.register()`
4. `operators.register()`
5. `ui.register()`
6. `keymaps.register()`

Modifying registration order can break dependencies—be careful.
