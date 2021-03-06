# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
#
# Copyright (C) 2020 Michael Vigovsky

import logging
import bpy, mathutils

from . import library, morphing, rigging, fitting

logger = logging.getLogger(__name__)

class RigException(Exception):
    pass

def copy_transform(target, source):
    target.location = source.location
    target.rotation_mode = source.rotation_mode
    target.rotation_euler = source.rotation_euler
    target.rotation_quaternion = source.rotation_quaternion
    target.scale = source.scale

def add_rig(conf, rigtype, verts):
    m = morphing.morpher
    if conf.get("type") != "rigify":
        raise RigException("Rig type {} is not supported".format(conf.get("type")))
    metarig = library.import_obj(m.char.path(conf["file"]), conf["obj_name"], "ARMATURE")
    if not metarig:
        raise RigException("Rig import failed")

    # Trying to override the context leads to crash :( TODO: learn more about it, maybe even try to gdb blender
    #override = context.copy()
    #override["object"] = metarig
    #override["active_object"] = metarig
    def remove_metarig():
       old_armature = metarig.data
       bpy.data.objects.remove(metarig)
       bpy.data.armatures.remove(old_armature)

    bpy.context.view_layer.objects.active = metarig
    bpy.ops.object.mode_set(mode="EDIT")
    if not rigging.joints_to_vg(m.obj, rigging.all_joints(bpy.context), verts):
        remove_metarig()
        raise RigException("Metarig fitting failed")

    bpy.ops.object.mode_set(mode="OBJECT")

    if rigtype != "RG":
        copy_transform(metarig, m.obj)
        return

    metarig.data.rigify_generate_mode = "new"
    bpy.ops.pose.rigify_generate()
    remove_metarig()
    rig = bpy.context.object
    rig.name = m.obj.name + "_rig"
    bpy.ops.object.mode_set(mode="EDIT")
    rigging.rigify_add_deform(bpy.context, m.obj)
    bpy.ops.object.mode_set(mode="OBJECT")

    copy_transform(rig, m.obj)

    m.obj.location = (0,0,0)
    m.obj.rotation_mode = "QUATERNION"
    m.obj.rotation_quaternion = (1,0,0,0)
    m.obj.scale = (1,1,1)
    m.obj.parent = rig

    rig.data["charmorph_template"] = m.obj.data.get("charmorph_template","")

    mod = m.obj.modifiers.new("charmorph_rigify", "ARMATURE")
    mod.use_deform_preserve_volume = True
    mod.use_vertex_groups = True
    mod.object = rig
    rigging.reposition_armature_modifier(bpy.context, m.obj)

    rigging.apply_tweaks(rig, conf.get("tweaks",[]))

    if bpy.context.window_manager.charmorph_ui.fitting_armature:
        fitting.transfer_new_armature(m.obj)

class OpFinalize(bpy.types.Operator):
    bl_idname = "charmorph.finalize"
    bl_label = "Finalize"
    bl_description = "Finalize character (add rig, modifiers, cleanup)"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode=="OBJECT" and morphing.morpher

    def execute(self, context):
        ui = context.window_manager.charmorph_ui
        m = morphing.morpher
        if not m.char.config:
            self.report({'ERROR'}, "Character config is not found")
            return {"CANCELLED"}

        unused_l1 = set()

        keys = m.obj.data.shape_keys
        fin_sk = None
        if keys and keys.key_blocks:
            if ui.fin_morph != "NO" or ui.fin_rig != "NO":
                fin_sk = m.obj.data.shape_keys.key_blocks["charmorph_final"]
                if not fin_sk:
                    fin_sk = m.obj.shape_key_add(name="charmorph_final", from_mix=True)
                fin_sk.value = 1

            unknown_keys = False

            for key in keys.key_blocks:
                if key.name.startswith("L1_") and key.value<0.01:
                    unused_l1.add(key.name[3:])
                if ui.fin_morph != "NO" and key != keys.reference_key and key != fin_sk:
                    if key.name.startswith("L1_")  or key.name.startswith("L2_"):
                        m.obj.shape_key_remove(key)
                    else:
                        unknown_keys = True

            if ui.fin_morph == "AL":
                if unknown_keys:
                    self.report({"WARNING"}, "Unknown shape keys found. Keeping original basis anyway")
                else:
                    m.obj.shape_key_remove(keys.reference_key)
                    m.obj.shape_key_remove(fin_sk)
                    fin_sk = None

        if ui.fin_morph != "NO" and "cm_morpher" in m.obj.data:
            del m.obj.data["cm_morpher"]
            for k in [k for k in m.obj.data.keys() if k.startswith("cmorph_")]:
                del m.obj.data[k]

        # Make sure we won't delete any vertex groups used by hair particle systems
        for psys in m.obj.particle_systems:
            for attr in dir(psys):
                if attr.startswith("vertex_group_"):
                    vg = getattr(psys, attr)
                    if vg.startswith("hair_"):
                        unused_l1.difference_update([vg[5:]])

        def do_rig():
            if ui.fin_rig == "NO":
                return True
            if isinstance(m.obj.parent, bpy.types.Object) and m.obj.parent.type == "ARMATURE":
                self.report({"WARNING"}, "Character is already attached to an armature, skipping rig")
                return True
            rigs = m.char.armature
            if not rigs or len(rigs) == 0:
                self.report({"ERROR"}, "Rig is not found")
                return False
            if len(rigs) > 1:
                self.report({"ERROR"}, "Multiple rigs aren't supported yet")
                return False
            rig_type = ui.fin_rig
            if rig_type == "RG" and not hasattr(bpy.ops.pose, "rigify_generate"):
                self.report({"ERROR"}, "Rigify is not found! Generating metarig only")
                rig_type = "MR"
            try:
                add_rig(rigs[0], rig_type, fin_sk.data if fin_sk else None)
            except RigException as e:
                self.report({"ERROR"}, str(e))
                return False
            return True

        ok = do_rig()

        if fin_sk and ui.fin_morph == "NO":
            # Remove temporary mix shape key
            m.obj.shape_key_remove(fin_sk)

        if not ok:
            return {"CANCELLED"}

        def add_modifiers(obj):
            def add_modifier(typ):
                for mod in obj.modifiers:
                    if mod.type == typ:
                        return mod
                return obj.modifiers.new("charmorph_" + typ.lower(), typ)

            if ui.fin_csmooth != "NO":
                mod = add_modifier("CORRECTIVE_SMOOTH")
                mod.smooth_type = ui.fin_csmooth

            if ui.fin_subdivision != "NO":
                mod = add_modifier("SUBSURF")
                mod.show_viewport = ui.fin_subdivision == "RV"

        add_modifiers(m.obj)

        if (ui.fin_subdivision != "NO" and ui.fin_subdiv_assets) or (ui.fin_csmooth != "NO" and ui.fin_cmooth_assets):
            for asset in fitting.get_assets(m.obj):
                add_modifiers(asset)


        if ui.fin_vg_cleanup:
            for vg in m.obj.vertex_groups:
                if vg.name.startswith("joint_") or (
                        vg.name.startswith("hair_") and vg.name[5:] in unused_l1):
                    m.obj.vertex_groups.remove(vg)

        if ui.fin_morph != "NO":
            morphing.del_charmorphs()

        return {"FINISHED"}


class CHARMORPH_PT_Finalize(bpy.types.Panel):
    bl_label = "Finalization"
    bl_parent_id = "VIEW3D_PT_CharMorph"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 9

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and morphing.morpher

    def draw(self, context):
        ui = context.window_manager.charmorph_ui
        self.layout.prop(ui, "fin_morph")
        self.layout.prop(ui, "fin_rig")
        self.layout.prop(ui, "fin_subdivision")
        self.layout.prop(ui, "fin_csmooth")
        self.layout.prop(ui, "fin_vg_cleanup")
        self.layout.prop(ui, "fin_subdiv_assets")
        self.layout.prop(ui, "fin_cmooth_assets")
        self.layout.operator("charmorph.finalize")

classes = [OpFinalize, CHARMORPH_PT_Finalize]
