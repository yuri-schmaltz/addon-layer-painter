import bpy
import os
from .utils_validation import AssetLoader, AssetValidator


def get_group(blend_path, name):
    """ imports the group with the given name from the blend file after checking if it already exists """
    
    # Validate blend file exists
    if not os.path.exists(blend_path):
        print(f"❌ Asset file not found: {blend_path}")
        return None
    
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    else:
        result = __append_group(blend_path, name)
        if not result:
            return None
            
        if name in bpy.data.node_groups:
            return bpy.data.node_groups[name]
    return None


def get_hidden_group_copy(blend_path, name):
    """ returns a unique copy of the given node group, mainly for assets that need to have nodes accessed inside them """
    
    group = get_group(blend_path, name)
    if not group:
        return None
    
    copy = group.copy()
    copy.name = "." + copy.name
    if group.users == 0:
        bpy.data.node_groups.remove(group)
    return copy
    
    
def __append_group(blend_path, name):
    """ appends the group with the given name from the given path """
    
    try:
        # Validate file
        if not os.path.exists(blend_path):
            print(f"❌ Blend file not found: {blend_path}")
            return False
        
        # Check file is readable
        if not os.access(blend_path, os.R_OK):
            print(f"❌ Permission denied reading: {blend_path}")
            return False
        
        with bpy.data.libraries.load(blend_path) as (data_from, data_to):
            if name in data_from.node_groups:
                data_to.node_groups = [name]
                return True
            else:
                print(f"⚠️  Node group '{name}' not found in {blend_path}")
                return False
    
    except Exception as e:
        print(f"❌ Failed to load asset '{name}' from {blend_path}: {str(e)}")
        return False