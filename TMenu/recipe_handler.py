"""
recipe_handler.py
==================
Straight port of the RPCS3 Character Editor's RecipeHandler (Asset.cs,
AssetList.cs, Model.cs, Texture.cs, RGBBlock.cs, GraphicBlock.cs, Recipe.cs)
- same binary format, same field layout, same quirks. It exists purely to
support the EXTRA subtab's "Apply Low Poly" and "Fix Crash" mods, which
both need to parse a skater's recipe blob, tweak the model list, and
re-serialize the *entire* recipe byte-for-byte so nothing else in it gets
corrupted on write-back.

Every class below has a `.parse(data, offset) -> (obj, next_offset)`
classmethod and a `.get_bytes()` instance method, mirroring the C# type's
constructor-from-bytes and GetBytes(). The overall Recipe.parse/get_bytes
round-trip is expected to reproduce the original bytes exactly for any
field that isn't deliberately being changed - if that ever stops being
true for some recipe, treat it as a parser bug rather than "close enough".

Nothing here talks to PS3MAPI directly - callers read/write the raw bytes
themselves (see edit_skater_tab.py's Extra subtab) and just hand this
module the blob.
"""

import struct


def _read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _pack_u32(value: int) -> bytes:
    return struct.pack(">I", value)


class Texture:
    def __init__(self, channel: str, name: bytes):
        self.channel = channel
        self.name = name  # 8 bytes

    @classmethod
    def parse(cls, data: bytes, offset: int):
        chan_len = data[offset + 3]
        channel = data[offset + 4: offset + 4 + chan_len].decode("ascii", errors="replace")
        name = data[offset + 4 + chan_len: offset + 12 + chan_len]
        return cls(channel, name), offset + 12 + chan_len

    def get_bytes(self) -> bytes:
        chan_bytes = self.channel.encode("ascii")
        return _pack_u32(len(chan_bytes)) + chan_bytes + self.name


class Model:
    # Fixed 8-byte filler that always sits between ModelName and MaterialID
    # in the on-disk format. Never touched, just preserved.
    _FILLER = bytes([0, 0, 0, 1, 0, 0, 0, 1])

    def __init__(self, arena_id: bytes, model_name: bytes, material_id: bytes, textures=None):
        self.arena_id = arena_id      # 8 bytes
        self.model_name = model_name  # 8 bytes
        self.material_id = material_id  # 8 bytes
        self.textures = textures or []

    @classmethod
    def parse(cls, data: bytes, offset: int):
        # Fixed 0x25 (37) byte block: [LOD(1)][ArenaID(8)][ModelName(8)][filler(8)][MaterialID(8)][TexCount(4 BE)]
        arena_id = data[offset + 1: offset + 9]
        model_name = data[offset + 9: offset + 17]
        material_id = data[offset + 25: offset + 33]
        pos = offset + 0x25

        # Carried over from the original tool: an oddity seen on some female
        # models where this "should" be 1 but occasionally isn't - the loop
        # below re-reads extra texture-count blocks if it's greater than 1.
        texture_loops = data[pos - 0x11]
        texture_count = data[pos - 1]

        model = cls(arena_id, model_name, material_id)
        for _ in range(texture_count):
            tex, pos = Texture.parse(data, pos)
            model.textures.append(tex)

        for _ in range(texture_loops - 1):
            pos += 0x10
            extra_count = data[pos - 1]
            for _ in range(extra_count):
                url_len = data[pos + 3]
                pos += 12 + url_len

        return model, pos

    def get_bytes(self, lod_index: int) -> bytes:
        out = bytes([lod_index]) + self.arena_id + self.model_name + self._FILLER + self.material_id
        out += _pack_u32(len(self.textures))
        for tex in self.textures:
            out += tex.get_bytes()
        return out


class Asset:
    def __init__(self, asset_id: bytes, models=None):
        self.asset_id = asset_id  # 8 bytes
        self.models = models or []

    @classmethod
    def parse(cls, data: bytes, offset: int):
        asset_id = data[offset: offset + 8]
        model_count = _read_u32(data, offset + 8)
        pos = offset + 0x0C
        asset = cls(asset_id)
        for _ in range(model_count):
            model, pos = Model.parse(data, pos)
            asset.models.append(model)
        return asset, pos

    def get_bytes(self) -> bytes:
        out = self.asset_id + _pack_u32(len(self.models))
        for i, model in enumerate(self.models):
            lod_index = 0 if i == 0 else 2
            out += model.get_bytes(lod_index)
        return out


class AssetList:
    def __init__(self, folder_name: str, assets=None):
        self.folder_name = folder_name
        self.assets = assets or []

    @classmethod
    def parse(cls, data: bytes, offset: int):
        name_len = data[offset + 3]
        folder_name = data[offset + 4: offset + 4 + name_len].decode("ascii", errors="replace")
        header_len = 8 + name_len
        asset_count = data[offset + header_len - 1]
        pos = offset + header_len

        asset_list = cls(folder_name)
        for _ in range(asset_count):
            asset, pos = Asset.parse(data, pos)
            asset_list.assets.append(asset)
        return asset_list, pos

    def get_bytes(self) -> bytes:
        name_bytes = self.folder_name.encode("ascii")
        out = _pack_u32(len(name_bytes)) + name_bytes + bytes([0, 0, 0, len(self.assets)])
        for asset in self.assets:
            out += asset.get_bytes()
        return out


class RGBBlock:
    def __init__(self, r, g, b, asset_id: bytes, material_id: bytes):
        self.r, self.g, self.b = r, g, b
        self.asset_id = asset_id
        self.material_id = material_id

    @classmethod
    def parse(cls, data: bytes, offset: int):
        r = struct.unpack_from(">f", data, offset + 4)[0]
        g = struct.unpack_from(">f", data, offset + 8)[0]
        b = struct.unpack_from(">f", data, offset + 12)[0]
        asset_id = data[offset + 0x1C: offset + 0x24]
        material_id = data[offset + 0x24: offset + 0x2C]
        return cls(r, g, b, asset_id, material_id), offset + 0x2C

    def get_bytes(self, index: int) -> bytes:
        rgb = struct.pack(">f", self.r) + struct.pack(">f", self.g) + struct.pack(">f", self.b)
        return bytes([0, 0, 0, index]) + rgb + rgb + self.asset_id + self.material_id


class GraphicBlock:
    def __init__(self, url: str, asset_id: bytes, material_id: bytes):
        self.url = url
        self.asset_id = asset_id
        self.material_id = material_id

    @classmethod
    def parse(cls, data: bytes, offset: int):
        url_len = data[offset + 3]
        url = data[offset + 4: offset + 4 + url_len].decode("ascii", errors="replace")
        asset_id = data[offset + 4 + url_len: offset + 12 + url_len]
        material_id = data[offset + 12 + url_len: offset + 20 + url_len]
        block_len = 29 + url_len
        return cls(url, asset_id, material_id), offset + block_len

    def get_bytes(self) -> bytes:
        url_bytes = self.url.encode("ascii")
        flag = 1 if "http" in self.url else 0
        return (_pack_u32(len(url_bytes)) + url_bytes + self.asset_id + self.material_id
                + bytes(8) + bytes([flag]))


class Recipe:
    """
    Full recipe blob: header -> asset lists (with nested models/textures) ->
    gender + RGB blocks -> graphic blocks -> a trailing tail of bytes the
    original tool never fully reverse-engineered ("bytesAfter" in Recipe.cs).
    That tail is kept verbatim on write-back rather than reconstructed.
    """

    def __init__(self, name="", recipe_type=0, gender=0):
        self.name = name
        self.recipe_type = recipe_type
        self.gender = gender
        self.asset_lists = []
        self.rgb_blocks = []
        self.graphic_blocks = []
        self._only_load_model_textures = True
        self._tail = b""

    @classmethod
    def parse(cls, data: bytes):
        name_len = data[7]
        name = data[8: 8 + name_len].decode("ascii", errors="replace")
        recipe_type = data[0x0B + name_len]

        recipe = cls(name, recipe_type)
        if data[0x13 + name_len] == 2:
            recipe._only_load_model_textures = False

        pos = 0x18 + name_len
        asset_list_count = data[pos - 1]
        for _ in range(asset_list_count):
            asset_list, pos = AssetList.parse(data, pos)
            recipe.asset_lists.append(asset_list)

        if not recipe._only_load_model_textures:
            pos += 5  # skip the constant "01 00 00 00 06" block
            recipe.gender = data[pos]
            pos += 9  # jump to the first RGB block

            rgb_count = data[pos - 1]
            for _ in range(rgb_count):
                block, pos = RGBBlock.parse(data, pos)
                recipe.rgb_blocks.append(block)

            pos += 8
            graphics_count = data[pos - 1]
            for _ in range(graphics_count):
                block, pos = GraphicBlock.parse(data, pos)
                recipe.graphic_blocks.append(block)
                pos += 1  # per-block index byte, appended outside GetBytes in the original too

            recipe._tail = data[pos: pos + 500]

        return recipe

    def get_bytes(self) -> bytes:
        name_bytes = self.name.encode("ascii")
        out = bytes([0, 0, 0, 7])
        out += _pack_u32(len(name_bytes)) + name_bytes
        out += _pack_u32(self.recipe_type)
        out += bytes([0, 0, 0, 0x0F, 0, 0, 0, 2])
        out += _pack_u32(len(self.asset_lists))
        for asset_list in self.asset_lists:
            out += asset_list.get_bytes()

        out += bytes([1, 0, 0, 0, 6])
        out += bytes([self.gender])
        out += _pack_u32(len(self.rgb_blocks)) + _pack_u32(len(self.rgb_blocks))
        for i, block in enumerate(self.rgb_blocks):
            out += block.get_bytes(i)

        out += _pack_u32(5)
        out += _pack_u32(len(self.graphic_blocks))
        for i, block in enumerate(self.graphic_blocks):
            out += block.get_bytes()
            out += bytes([i])

        out += self._tail
        return out

    # -- the two Extra-subtab mods ------------------------------------------

    def apply_low_poly(self) -> int:
        """
        For every asset that has a low-LOD model (Models[1]), copy its
        ArenaID + ModelName onto Models[0] - same fields the RPCS3 tool
        swaps, nothing else (MaterialID/Textures on Models[0] are left
        alone). Both list entries stay in place. Returns how many assets
        were changed.
        """
        changed = 0
        for asset_list in self.asset_lists:
            for asset in asset_list.assets:
                if len(asset.models) > 1:
                    asset.models[0].model_name = asset.models[1].model_name
                    asset.models[0].arena_id = asset.models[1].arena_id
                    changed += 1
        return changed

    def fix_crash(self) -> int:
        """Remove the low-LOD model (Models[1]) from every asset that has one."""
        changed = 0
        for asset_list in self.asset_lists:
            for asset in asset_list.assets:
                if len(asset.models) > 1:
                    del asset.models[1]
                    changed += 1
        return changed
