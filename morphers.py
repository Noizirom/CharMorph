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

from . import morphing

def get_combo_prop_value(arr, idx):
    return sum(0 if sk is None else sk.value * ((arr_idx >> idx & 1)*2-1) for arr_idx, sk in enumerate(arr))

def get_combo_prop_values(arr, dims):
    return [get_combo_prop_value(arr, i) for i in range(dims)]

def get_combo_item_value(arr_idx, values):
    return sum(val*((arr_idx >> val_idx & 1)*2-1) for val_idx, val in enumerate(values))

class ShapeKeysMorpher(morphing.Morpher):
    def update_L1(self):
        for name, sk in self.morphs_l1.items():
            sk.value = 1 if name == self.L1 else 0

        # clear old L2 shape keys
        if not self.obj.data.shape_keys:
             return
        for sk in self.obj.data.shape_keys.key_blocks:
             if sk.name.startswith("L2_") and not sk.name.startswith("L2__") and not sk.name.startswith("L2_{}_".format(self.L1)):
                 sk.value = 0

    # scan object shape keys and convert them to dictionary
    def get_L1(self):
        self.morphs_l1 = {}
        if not self.obj.data.shape_keys:
            return ""
        maxkey = ""
        maxval = 0
        for sk in self.obj.data.shape_keys.key_blocks:
            if len(sk.name) < 4 or not sk.name.startswith("L1_"):
                continue
            name = sk.name[3:]
            if sk.value > maxval:
                maxkey = name
                maxval = sk.value
            self.morphs_l1[name] = sk

        return maxkey

    def has_morphs(self):
        if self.morphs_l1:
            return True
        if not self.obj.data.shape_keys or not self.obj.data.shape_keys.key_blocks:
            return False
        for sk in self.obj.data.shape_keys.key_blocks:
             if sk.name.startswith("L2_"):
                return True
        return False

    def get_morphs_L2(self):
        self.morphs_l2.clear()
        if not self.obj.data.shape_keys:
            return

        def load_shape_keys_by_prefix(prefix):
            for sk in self.obj.data.shape_keys.key_blocks:
                if sk.name.startswith(prefix):
                    self.add_morph_l2(sk.name[len(prefix):], sk)

        load_shape_keys_by_prefix("L2__")

        if len(self.L1) > 0:
            load_shape_keys_by_prefix("L2_%s_" % self.L1)

    # create simple prop that drives one min and one max shapekey
    def morph_prop_simple(self, name, skmin, skmax, soft_min=-1.0):
        def setter(cm, value):
            self.version += 1
            if value < 0:
                if skmax != None: skmax.value = 0
                if skmin != None: skmin.value = -value
            else:
                if skmin != None: skmin.value = 0
                if skmax != None: skmax.value = value
            self.update()
        return self.morph_prop(name,
            lambda self: (0 if skmax==None else skmax.value) - (0 if skmin==None else skmin.value),
            setter, soft_min)

    # create a bunch of props from combo shape keys
    def morph_props_combo(self, name, arr):
        nameParts = name.split("_")
        names = nameParts[1].split("-")
        dims = len(names)
        coeff = 2 / len(arr)

        values = get_combo_prop_values(arr, dims)

        def getterfunc(idx):
            def getter(self):
                val = get_combo_prop_value(arr, idx)
                values[idx] = val
                return val

            return getter

        def setterfunc(idx):
            def setter(cm, value):
                if self.clamp:
                    value = max(min(value, 1), -1)
                self.version += 1
                values[idx] = value
                for arr_idx, sk in enumerate(arr):
                    sk.value = get_combo_item_value(arr_idx, values) * coeff
                self.update()
            return setter

        return [(name, self.morph_prop(name, getterfunc(i), setterfunc(i))) for i, name in ((i, nameParts[0]+"_"+name) for i, name in enumerate(names))]

    def morph_props(self, name, data):
        if len(data) == 1:
            return [(name, self.morph_prop_simple(name, None, data[0], 0.0))]
        elif len(data) == 2:
            return [(name, self.morph_prop_simple(name, data[0], data[1]))]
        else:
            return self.morph_props_combo(name, data)

import os, numpy

class NumpyMorpher(morphing.Morpher):
    def __init__(self, obj):
        super().__init__(obj)
        self.basis = None

    def has_morphs(self):
        return bool(self.char.name)

    def update_L1(self):
        file = self.morphs_l1.get(self.L1, "")
        if os.path.isfile(file):
            self.basis = numpy.load(file).astype(dtype=numpy.float64, casting="same_kind")
            self.obj.data["cmorph_L1"] = self.L1
        else:
            verts = self.obj.data.vertices
            arr = numpy.empty(len(verts) * 3)
            verts.foreach_get("co", arr)
            self.basis = arr.reshape((len(verts),3))

    def get_L1(self):
        self.morphs_l1 = {}
        dir = self.char.path("morphs/L1")
        if not os.path.isdir(dir):
            return ""
        for file in os.listdir(dir):
            if file[-4:] != ".npy":
                continue
            self.morphs_l1[file[:-4]] = os.path.join(dir, file)
        L1 = self.obj.data.get("cmorph_L1","")
        if L1 not in self.morphs_l1:
            L1 == ""
        return L1

    def get_morphs_L2(self):
        self.morphs_l2.clear()
        def load_dir(dir):
            dir = self.char.path(dir)
            if not os.path.isdir(dir):
                return
            for file in os.listdir(dir):
                if file[-4:] != ".npz":
                    continue
                self.add_morph_l2(file[:-4], os.path.join(dir, file))
        load_dir("morphs/L2")
        if self.L1:
            load_dir("morphs/L2/"+self.L1)

    @staticmethod
    def enum_combo_names(name):
        nameParts = name.split("_")
        return (nameParts[0]+"_"+name for name in nameParts[1].split("-"))

    def do_update(self):
        if self.basis is None:
            self.update_L1()
        morph_data = None
        def do_morph(data, idx, value):
            nonlocal morph_data
            if value < 0.001:
                return
            if self.clamp:
                value = min(value, 1)
            item = data[idx]
            if item is None:
                return
            if isinstance(item, str):
                npz = numpy.load(item)
                item = (npz["idx"], npz["delta"].astype(dtype=numpy.float64, casting="same_kind"))
                data[idx] = item
            if morph_data is None:
                morph_data = self.basis.copy()
            morph_data[item[0]] += item[1] * value

        for name, data in self.morphs_l2.items():
            if len(data)<=2:
                val = self.obj.data.get("cmorph_L2_"+name)
                if val:
                    if len(data) == 1:
                        do_morph(data, 0, val)
                    elif len(data) == 2:
                        do_morph(data, 0, -val)
                        do_morph(data, 1, val)
            else:
                values = [ self.obj.data.get("cmorph_L2_"+n, 0.0) for n in  self.enum_combo_names(name) ]
                coeff = 2 / len(data)
                for i in range(len(data)):
                    do_morph(data, i, get_combo_item_value(i, values) * coeff)

        if morph_data is None:
            morph_data = self.basis

        if not self.obj.data.shape_keys or not self.obj.data.shape_keys.key_blocks:
            self.obj.shape_key_add(name="Basis", from_mix=False)
        sk = self.obj.data.shape_keys.key_blocks.get("charmorph_final")
        if not sk:
            sk = self.obj.shape_key_add(name="charmorph_final", from_mix=False)
        sk.data.foreach_set("co", morph_data.reshape(-1))
        sk.value = 1

        super().do_update()

    def morph_prop_simple(self, name, soft_min = -1):
        pname = "cmorph_L2_"+name
        def setter(cm, value):
            if self.clamp:
                value = max(min(value, 1), -1)
            self.version += 1
            self.obj.data[pname] = value
            self.update()
        return self.morph_prop(name,
            lambda _: self.obj.data.get(pname, 0.0),
            setter, soft_min)

    def morph_props(self, name, data):
        if len(data) <= 2:
            return [(name, self.morph_prop_simple(name, 0.0 if len(data) == 1 else -1.0))]
        else:
            return [(name, self.morph_prop_simple(name)) for name in self.enum_combo_names(name)]
