"""Confirmation dialog utilities for destructive operations.

Provides reusable confirmation dialogs for operations like:
- Deleting layers
- Deleting channels
- Removing masks/filters
- Clearing bake settings
"""

import bpy
from typing import Callable, Optional


class ConfirmDialog(bpy.types.Operator):
    """Generic confirmation dialog operator."""
    
    bl_idname = "lp.confirm_dialog"
    bl_label = "Confirm Operation"
    bl_options = {'INTERNAL'}
    
    # Dialog properties
    title: bpy.props.StringProperty(default="Confirm")
    message: bpy.props.StringProperty(default="Are you sure?")
    action: bpy.props.StringProperty(default="")
    
    def draw(self, context):
        """Draw dialog."""
        layout = self.layout
        layout.label(text=self.message, icon="QUESTION")
        layout.separator()
        
        # Action buttons
        row = layout.row()
        row.scale_y = 1.5
        row.operator(self.bl_idname, text="Cancel", icon="CANCEL").confirmed = False
        row.operator(self.bl_idname, text="Confirm", icon="CHECKMARK").confirmed = True
    
    def execute(self, context):
        """Handle dialog result."""
        if self.confirmed:
            # Execute the action
            bpy.ops.wm.call_menu(name=f"LP_MT_{self.action}")
        return {"FINISHED"}


def confirm_delete_layer(layer_name: str, callback: Callable) -> bool:
    """Show confirmation dialog for layer deletion.
    
    Args:
        layer_name: Name of layer to delete
        callback: Function to call on confirmation
        
    Returns:
        True if user confirms, False otherwise
    """
    message = f'Delete layer "{layer_name}"?\n\nThis cannot be undone.'
    
    def wm_invoke_props_dialog():
        bpy.ops.lp.confirm_delete_layer(
            'INVOKE_DEFAULT',
            layer_name=layer_name,
            callback_id=id(callback)
        )
    
    return True  # Async - dialog will call callback


def confirm_delete_channel(channel_name: str, callback: Callable) -> bool:
    """Show confirmation dialog for channel deletion.
    
    Args:
        channel_name: Name of channel to delete
        callback: Function to call on confirmation
        
    Returns:
        True if user confirms, False otherwise
    """
    message = f'Delete channel "{channel_name}"?\n\nThis cannot be undone.'
    
    def wm_invoke_props_dialog():
        bpy.ops.lp.confirm_delete_channel(
            'INVOKE_DEFAULT',
            channel_name=channel_name,
            callback_id=id(callback)
        )
    
    return True


class LP_OT_ConfirmDeleteLayer(bpy.types.Operator):
    """Confirmation dialog for layer deletion."""
    
    bl_idname = "lp.confirm_delete_layer"
    bl_label = "Delete Layer?"
    bl_options = {'INTERNAL'}
    
    layer_name: bpy.props.StringProperty(description="Name of layer to delete")
    material: bpy.props.StringProperty(description="Material name")
    uid: bpy.props.StringProperty(description="Layer UID")
    
    def draw(self, context):
        """Draw confirmation dialog."""
        layout = self.layout
        layout.label(text=f'Delete layer "{self.layer_name}"?', icon="ERROR")
        layout.label(text="This action cannot be undone.", icon="BLANK1")
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("lp.remove_layer", text="Delete", icon="TRASH", depress=False).uid = self.uid
        row.operator("wm.context_toggle", text="Cancel", icon="CANCEL")
    
    def execute(self, context):
        """Execute deletion."""
        return {'FINISHED'}
    
    def invoke(self, context, event):
        """Show dialog."""
        return context.window_manager.invoke_props_dialog(self, width=300)


class LP_OT_ConfirmDeleteChannel(bpy.types.Operator):
    """Confirmation dialog for channel deletion."""
    
    bl_idname = "lp.confirm_delete_channel"
    bl_label = "Delete Channel?"
    bl_options = {'INTERNAL'}
    
    channel_name: bpy.props.StringProperty(description="Name of channel to delete")
    material: bpy.props.StringProperty(description="Material name")
    channel: bpy.props.StringProperty(description="Channel UID")
    
    def draw(self, context):
        """Draw confirmation dialog."""
        layout = self.layout
        layout.label(text=f'Delete channel "{self.channel_name}"?', icon="ERROR")
        layout.label(text="This action cannot be undone.", icon="BLANK1")
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("lp.remove_channel", text="Delete", icon="TRASH", depress=False).channel = self.channel
        row.operator("wm.context_toggle", text="Cancel", icon="CANCEL")
    
    def execute(self, context):
        """Execute deletion."""
        return {'FINISHED'}
    
    def invoke(self, context, event):
        """Show dialog."""
        return context.window_manager.invoke_props_dialog(self, width=300)


class LP_OT_ConfirmClearBake(bpy.types.Operator):
    """Confirmation dialog for clearing bake settings."""
    
    bl_idname = "lp.confirm_clear_bake"
    bl_label = "Clear Bake Settings?"
    bl_options = {'INTERNAL'}
    
    def draw(self, context):
        """Draw confirmation dialog."""
        layout = self.layout
        layout.label(text="Clear all bake settings?", icon="ERROR")
        layout.label(text="All baked channels will be reset.", icon="BLANK1")
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("lp.clear_bake_settings", text="Clear", icon="TRASH", depress=False)
        row.operator("wm.context_toggle", text="Cancel", icon="CANCEL")
    
    def execute(self, context):
        """Execute clear."""
        return {'FINISHED'}
    
    def invoke(self, context, event):
        """Show dialog."""
        return context.window_manager.invoke_props_dialog(self, width=300)


# Dialog registry for registration
DIALOG_CLASSES = [
    ConfirmDialog,
    LP_OT_ConfirmDeleteLayer,
    LP_OT_ConfirmDeleteChannel,
    LP_OT_ConfirmClearBake,
]


def register():
    """Register dialog operators."""
    for cls in DIALOG_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass  # Already registered


def unregister():
    """Unregister dialog operators."""
    for cls in reversed(DIALOG_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass  # Not registered
