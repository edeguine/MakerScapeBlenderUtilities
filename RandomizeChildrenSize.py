bl_info = {
    "name": "Randomize Children Scale",
    "author": "MakerScape",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar (N) > Random Tools",
    "description": "Randomly varies the scale of the children of a chosen parent object",
    "category": "Object",
}

import bpy
import random
from bpy.props import PointerProperty, FloatProperty, EnumProperty
from bpy.types import Operator, Panel

# -------------------- Properties on Scene --------------------

def register_props():
    bpy.types.Scene.rcs_parent_object = PointerProperty(
        name="Parent Object",
        description="Children of this object will be randomly scaled",
        type=bpy.types.Object,
    )
    bpy.types.Scene.rcs_min_scale = FloatProperty(
        name="Min",
        description="Minimum random value",
        default=0.8,
        min=0.0,
        soft_min=0.0
    )
    bpy.types.Scene.rcs_max_scale = FloatProperty(
        name="Max",
        description="Maximum random value",
        default=1.2,
        min=0.0,
        soft_min=0.0
    )
    bpy.types.Scene.rcs_scale_mode = EnumProperty(
        name="Mode",
        description="How to apply the random number to scale",
        items=[
            ("MULTIPLY", "Multiplicative", "Multiply current scale by the random factor"),
            ("ABSOLUTE", "Scale Value", "Set X=Y=Z to the random value"),
        ],
        default="MULTIPLY",
    )

def unregister_props():
    for attr in ("rcs_parent_object", "rcs_min_scale", "rcs_max_scale", "rcs_scale_mode"):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

# -------------------- Operator --------------------

class RCS_OT_randomize_children_scale(Operator):
    """Apply a random uniform scale to each DIRECT child of the chosen parent object."""
    bl_idname = "rcs.randomize_children_scale"
    bl_label = "Randomize Children Scale"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        parent = scene.rcs_parent_object or context.view_layer.objects.active

        if parent is None:
            self.report({"ERROR"}, "No parent object chosen or active.")
            return {"CANCELLED"}

        min_s = scene.rcs_min_scale
        max_s = scene.rcs_max_scale
        if min_s > max_s:
            min_s, max_s = max_s, min_s  # swap if inverted

        children = [ch for ch in parent.children]
        if not children:
            self.report({"WARNING"}, f"'{parent.name}' has no direct children.")
            return {"CANCELLED"}

        mode = scene.rcs_scale_mode

        for ch in children:
            try:
                f = random.uniform(min_s, max_s)
                if mode == "MULTIPLY":
                    ch.scale = (ch.scale.x * f, ch.scale.y * f, ch.scale.z * f)
                else:  # ABSOLUTE
                    ch.scale = (f, f, f)
            except Exception as e:
                print(f"[RCS] Skipped {ch.name}: {e}")

        mode_label = "multiplicative" if mode == "MULTIPLY" else "absolute"
        self.report({"INFO"}, f"Scaled {len(children)} child object(s) ({mode_label}).")
        return {"FINISHED"}

# -------------------- UI Panel --------------------

class RCS_PT_panel(Panel):
    bl_label = "Random Tools"
    bl_idname = "RCS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Random Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.prop(scene, "rcs_parent_object", text="Parent")
        if scene.rcs_parent_object is None and context.view_layer.objects.active:
            row = col.row()
            row.enabled = False
            row.label(text=f"(Active: {context.view_layer.objects.active.name})")

        col.separator()
        col.prop(scene, "rcs_scale_mode", text="Mode")
        col.prop(scene, "rcs_min_scale")
        col.prop(scene, "rcs_max_scale")

        layout.separator()
        layout.operator(RCS_OT_randomize_children_scale.bl_idname, icon="FULLSCREEN_ENTER")

# -------------------- Registration --------------------

classes = (
    RCS_OT_randomize_children_scale,
    RCS_PT_panel,
)

def register():
    register_props()
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_props()

if __name__ == "__main__":
    register()
