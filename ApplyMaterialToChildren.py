bl_info = {
    "name": "Apply Material to Object and Children",
    "author": "MakerScape",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar (N) > Material Tools",
    "description": "Applies the same material to an object and all of its children",
    "category": "Material",
}

import bpy
from bpy.props import PointerProperty
from bpy.types import Operator, Panel


# -------- Utilities --------

def iter_hierarchy(root_obj):
    """Yield root_obj and all its descendants (depth-first)."""
    stack = [root_obj]
    while stack:
        obj = stack.pop()
        yield obj
        # Children order doesn't matter; extend the stack
        stack.extend(obj.children)


def apply_material_to_object(obj, mat):
    """Assign material to all slots (or create one) for objects that support materials."""
    data = getattr(obj, "data", None)
    if not data:
        return

    # Objects like Mesh, Curve, Text, GPencil (strokes), etc. that have .materials
    mats = getattr(data, "materials", None)
    if mats is None:
        return

    # Ensure at least one slot exists
    if len(mats) == 0:
        mats.append(mat)
    else:
        for i in range(len(mats)):
            mats[i] = mat

    # Make it active as well
    obj.active_material = mat


# -------- Properties (stored on Scene) --------

def get_default_object(context):
    # Convenience: if no target chosen yet, show active object by default (UI only)
    return context.view_layer.objects.active if context else None


def scene_props_register():
    bpy.types.Scene.amc_target_object = PointerProperty(
        name="Target Object",
        description="Root object; material will also be applied to all its children",
        type=bpy.types.Object,
    )
    bpy.types.Scene.amc_material = PointerProperty(
        name="Material",
        description="Material to apply to the hierarchy",
        type=bpy.types.Material,
    )


def scene_props_unregister():
    for attr in ("amc_target_object", "amc_material"):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)


# -------- Operator --------

class AMC_OT_apply_material_hierarchy(Operator):
    bl_idname = "amc.apply_material_hierarchy"
    bl_label = "Apply to Object + Children"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        target = scene.amc_target_object or context.view_layer.objects.active
        mat = scene.amc_material

        if target is None:
            self.report({"ERROR"}, "No target object selected or active.")
            return {"CANCELLED"}

        if mat is None:
            self.report({"ERROR"}, "Please pick a material.")
            return {"CANCELLED"}

        count_supported = 0
        for obj in iter_hierarchy(target):
            before = getattr(getattr(obj, "data", None), "materials", None)
            try:
                apply_material_to_object(obj, mat)
                after = getattr(getattr(obj, "data", None), "materials", None)
                if after is not None:
                    count_supported += 1
            except Exception as e:
                # Skip objects that cannot accept materials
                print(f"[AMC] Skipped {obj.name}: {e}")

        self.report({"INFO"}, f"Applied material to {count_supported} object(s).")
        return {"FINISHED"}


# -------- UI Panel --------

class AMC_PT_panel(Panel):
    bl_label = "Material Tools"
    bl_idname = "AMC_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Material Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.prop(scene, "amc_target_object", text="Object")

        # Show active object name as a hint if target is empty
        if scene.amc_target_object is None and context.view_layer.objects.active:
            row = col.row()
            row.enabled = False
            row.label(text=f"(Active: {context.view_layer.objects.active.name})")

        col.prop(scene, "amc_material", text="Material")

        layout.operator(AMC_OT_apply_material_hierarchy.bl_idname, icon="MATERIAL")


# -------- Registration --------

classes = (
    AMC_OT_apply_material_hierarchy,
    AMC_PT_panel,
)

def register():
    scene_props_register()
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    scene_props_unregister()


if __name__ == "__main__":
    register()
