bl_info = {
    "name": "Assign Existing Material with Random Hue Shift (Multi-Base + Children Mode)",
    "author": "MakerScape",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > N-panel > Hue Assign",
    "description": "Assign a picked material and random per-object hue_adjust by name patterns OR only to the children of a picked parent object.",
    "category": "Object",
}

import bpy
import random
import re

# ------------------------------
# Optional node setup for selected material
# ------------------------------

def build_hue_nodes_on_material(mat: bpy.types.Material, color_attr_name: str = "Col"):
    """
    Node graph:
      [Color Attribute (layer=...)] -> [Hue/Saturation/Value] -> [Principled BSDF] -> [Output]
      [Attribute (Geometry, name='hue_adjust') Fac] ---------> [HSV.Hue]
    """
    if mat is None:
        raise ValueError("No material provided.")
    if not mat.use_nodes:
        mat.use_nodes = True

    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial"); out.location = (800, 0)
    principled = nodes.new("ShaderNodeBsdfPrincipled"); principled.location = (550, 0)
    hsv = nodes.new("ShaderNodeHueSaturation"); hsv.location = (300, 50)

    color_attr_node = None
    if "ShaderNodeVertexColor" in bpy.types.__dir__():
        color_attr_node = nodes.new("ShaderNodeVertexColor")
        # In many builds the property is layer_name; falling back is harmless as a no-op.
        try:
            color_attr_node.layer_name = color_attr_name
        except Exception:
            try:
                color_attr_node.attribute_name = color_attr_name
            except Exception:
                pass
    else:
        color_attr_node = nodes.new("ShaderNodeAttribute")
        color_attr_node.attribute_name = color_attr_name
    color_attr_node.location = (0, -40)

    attr_hue = nodes.new("ShaderNodeAttribute")
    attr_hue.location = (0, 180)
    attr_hue.attribute_name = "hue_adjust"

    links.new(color_attr_node.outputs.get("Color"), hsv.inputs["Color"])
    links.new(attr_hue.outputs.get("Fac"), hsv.inputs["Hue"])
    links.new(hsv.outputs["Color"], principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], out.inputs["Surface"])

# ------------------------------
# Mesh helpers
# ------------------------------

def ensure_color_attribute(mesh: bpy.types.Mesh, color_attr_name: str = "Col"):
    col_attr = mesh.color_attributes.get(color_attr_name)
    if col_attr is None:
        col_attr = mesh.color_attributes.new(
            name=color_attr_name, domain='CORNER', type='BYTE_COLOR'
        )
        for i in range(len(col_attr.data)):
            c = col_attr.data[i].color
            c[0], c[1], c[2], c[3] = 1.0, 1.0, 1.0, 1.0
    return col_attr

def write_uniform_float_attribute(mesh: bpy.types.Mesh, attr_name: str, value: float):
    attr = mesh.attributes.get(attr_name)
    if attr is None or attr.data_type != 'FLOAT' or attr.domain != 'POINT':
        if attr is not None:
            mesh.attributes.remove(attr)
        attr = mesh.attributes.new(name=attr_name, type='FLOAT', domain='POINT')
    for i in range(len(attr.data)):
        attr.data[i].value = value

# ------------------------------
# List item + properties
# ------------------------------

class HueAssignBaseNameItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Base",
        description="Base object name prefix (matches 'Base' or 'Base 1', 'Base 2', ...)"
    )

class HueAssignProps(bpy.types.PropertyGroup):
    # --- Mode switch ---
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("NAME", "By Base Names", "Match objects by name patterns (original behavior)"),
            ("CHILDREN", "Children of Picked Parent", "Affect only the direct children of a picked parent"),
        ],
        default="NAME",
    )

    # NAME mode properties
    base_names: bpy.props.CollectionProperty(type=HueAssignBaseNameItem)
    base_names_index: bpy.props.IntProperty(default=0)

    # CHILDREN mode properties
    parent_object: bpy.props.PointerProperty(
        name="Parent Object",
        description="Only direct children of this object will be processed",
        type=bpy.types.Object,
    )

    # Shared props
    color_attribute_name: bpy.props.StringProperty(
        name="Vertex Color",
        default="Col",
        description="Vertex color layer name read by the material"
    )
    hue_min: bpy.props.FloatProperty(
        name="Hue Min",
        default=-1.0, soft_min=-2.0, soft_max=2.0,
        description="Min hue adjustment (per object)"
    )
    hue_max: bpy.props.FloatProperty(
        name="Hue Max",
        default=1.0, soft_min=-2.0, soft_max=2.0,
        description="Max hue adjustment (per object)"
    )
    random_seed: bpy.props.IntProperty(
        name="Random Seed",
        default=0, min=0,
        description="Seed for reproducible randomization"
    )
    target_material: bpy.props.PointerProperty(
        name="Material",
        description="Pick the material you created (will be reused on all matches)",
        type=bpy.types.Material
    )

# ------------------------------
# UIList and list operators
# ------------------------------

class UI_UL_base_names(bpy.types.UIList):
    bl_idname = "UI_UL_base_names_list"
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=True, icon='OUTLINER_DATA_GREASEPENCIL')

class LIST_OT_add_base(bpy.types.Operator):
    bl_idname = "hue_assign.add_base"
    bl_label = "Add Base"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        props = context.scene.hue_assign_props
        item = props.base_names.add()
        item.name = "body instance"
        props.base_names_index = len(props.base_names) - 1
        return {'FINISHED'}

class LIST_OT_remove_base(bpy.types.Operator):
    bl_idname = "hue_assign.remove_base"
    bl_label = "Remove Base"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        props = context.scene.hue_assign_props
        if props.base_names and 0 <= props.base_names_index < len(props.base_names):
            props.base_names.remove(props.base_names_index)
            props.base_names_index = min(props.base_names_index, max(0, len(props.base_names)-1))
        return {'FINISHED'}

class LIST_OT_add_active_object_name(bpy.types.Operator):
    bl_idname = "hue_assign.add_active_object_name"
    bl_label = "From Active"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object.")
            return {'CANCELLED'}
        props = context.scene.hue_assign_props
        item = props.base_names.add()
        item.name = obj.name
        props.base_names_index = len(props.base_names) - 1
        return {'FINISHED'}

# ------------------------------
# Operators (material setup + assignment)
# ------------------------------

class OBJ_OT_setup_selected_material(bpy.types.Operator):
    bl_idname = "object.setup_selected_material_hue_nodes"
    bl_label = "Setup Selected Material"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        props = context.scene.hue_assign_props
        mat = props.target_material
        if mat is None:
            self.report({'ERROR'}, "Pick a material in the UI first.")
            return {'CANCELLED'}
        try:
            build_hue_nodes_on_material(mat, props.color_attribute_name)
        except Exception as e:
            self.report({'ERROR'}, f"Could not set up material: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Material '{mat.name}' configured.")
        return {'FINISHED'}

class OBJ_OT_assign_hue_material(bpy.types.Operator):
    bl_idname = "object.assign_hue_material_to_instances_existing"
    bl_label = "Run"
    bl_options = {'REGISTER', 'UNDO'}

    def _targets_by_name(self, context, props):
        # Build regex patterns for all base names
        patterns = []
        for it in props.base_names:
            base = it.name.strip()
            if not base:
                continue
            base_escaped = re.escape(base)
            patterns.append(re.compile(rf"^{base_escaped}(?: \d+)?$", re.IGNORECASE))

        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
            if any(p.match(obj.name) for p in patterns):
                yield obj

    def _targets_children(self, context, props):
        parent = props.parent_object or context.view_layer.objects.active
        if parent is None:
            self.report({'ERROR'}, "Pick a Parent Object (or set an active object).")
            return None
        return (ch for ch in parent.children if ch.type == 'MESH')

    def execute(self, context):
        props = context.scene.hue_assign_props
        mat = props.target_material
        if mat is None:
            self.report({'ERROR'}, "Pick a material in the UI first.")
            return {'CANCELLED'}
        if props.hue_min > props.hue_max:
            self.report({'ERROR'}, "Hue Min cannot be greater than Hue Max.")
            return {'CANCELLED'}

        # Determine targets based on mode
        if props.mode == "NAME":
            if not props.base_names or all(not it.name.strip() for it in props.base_names):
                self.report({'ERROR'}, "Add at least one base name.")
                return {'CANCELLED'}
            gen = self._targets_by_name(context, props)
        else:  # CHILDREN
            gen = self._targets_children(context, props)
            if gen is None:
                return {'CANCELLED'}

        rnd = random.Random(props.random_seed)
        count = 0

        for obj in gen:
            me = obj.data
            ensure_color_attribute(me, props.color_attribute_name)

            if me.materials:
                me.materials[0] = mat
            else:
                me.materials.append(mat)

            hue_adj = rnd.uniform(props.hue_min, props.hue_max)
            write_uniform_float_attribute(me, "hue_adjust", hue_adj)
            me.update()
            count += 1

        mode_label = "children" if props.mode == "CHILDREN" else "name matches"
        self.report({'INFO'}, f"Assigned '{mat.name}' and hue_adjust to {count} object(s) ({mode_label}).")
        return {'FINISHED'}

# ------------------------------
# Panel
# ------------------------------

class VIEW3D_PT_hue_assign(bpy.types.Panel):
    bl_label = "Hue Assign"
    bl_idname = "VIEW3D_PT_hue_assign_existing_multibase"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hue Assign"

    def draw(self, context):
        layout = self.layout
        props = context.scene.hue_assign_props

        # Material / nodes
        col = layout.column(align=True)
        col.label(text="Material")
        col.prop(props, "target_material")
        col.prop(props, "color_attribute_name")
        col.operator(OBJ_OT_setup_selected_material.bl_idname, text="Setup Selected Material", icon='NODETREE')

        layout.separator()

        # Mode selector
        layout.prop(props, "mode", text="")

        # Mode-specific UI
        if props.mode == "NAME":
            col = layout.column(align=True)
            col.label(text="Base Names")
            row = col.row()
            row.template_list("UI_UL_base_names_list", "", props, "base_names", props, "base_names_index", rows=4)
            col2 = row.column(align=True)
            col2.operator(LIST_OT_add_base.bl_idname, text="", icon='ADD')
            col2.operator(LIST_OT_remove_base.bl_idname, text="", icon='REMOVE')
            col2.separator()
            col2.operator(LIST_OT_add_active_object_name.bl_idname, text="", icon='EYEDROPPER')
        else:
            col = layout.column(align=True)
            col.label(text="Children Mode")
            col.prop(props, "parent_object", text="Parent")
            if props.parent_object is None and context.view_layer.objects.active:
                row = col.row()
                row.enabled = False
                row.label(text=f"(Active: {context.view_layer.objects.active.name})")

        layout.separator()
        col = layout.column(align=True)
        col.prop(props, "hue_min")
        col.prop(props, "hue_max")
        col.prop(props, "random_seed")

        layout.separator()
        col.operator(OBJ_OT_assign_hue_material.bl_idname, text="Run", icon='PLAY')

# ------------------------------
# Registration
# ------------------------------

classes = (
    HueAssignBaseNameItem,
    HueAssignProps,
    UI_UL_base_names,
    LIST_OT_add_base,
    LIST_OT_remove_base,
    LIST_OT_add_active_object_name,
    OBJ_OT_setup_selected_material,
    OBJ_OT_assign_hue_material,
    VIEW3D_PT_hue_assign,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.hue_assign_props = bpy.props.PointerProperty(type=HueAssignProps)

def unregister():
    del bpy.types.Scene.hue_assign_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
