# pyright: reportImportCycles=false
from ctypes import c_uint32
from ctypes import c_uint16
from ctypes import c_uint8
from ctypes import c_char
from ctypes import sizeof
from ctypes import addressof
from ctypes import memmove
from ctypes import LittleEndianStructure

from typing import final
from typing import cast
from typing import TYPE_CHECKING

from collections.abc import Generator

from .struct import Ext4Struct
from .struct import MagicError
from .enum import DX_HASH
from ._compat import override
from ._compat import assert_type

if TYPE_CHECKING:
    from .inode import Directory
    from .volume import Volume


class LittleEndianStructureWithVolume(LittleEndianStructure):
    volume: "Volume | None" = None


@final
class DotDirectoryEntry2(LittleEndianStructureWithVolume):
    _pack_ = 1
    # _anonymous_ = ()
    _fields_ = [
        ("inode", c_uint32),
        ("rec_len", c_uint16),
        ("name_len", c_uint8),
        ("file_type", c_uint8),
        ("name", c_char * 4),  # b".\0\0\0" or b"..\0\0"
    ]

    def verify(self) -> None:
        name = assert_type(self.name, str)  # pyright: ignore[reportAny]
        if name in (b".\0\0\0", b".\0\0\0"):
            return

        message = f"{self} dot or dotdot entry name invalid! actual={name}"
        assert self.volume is not None
        if not self.volume.ignore_magic:
            raise MagicError(message)


@final
class DXRootInfo(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("reserved_zero")
    _fields_ = [
        ("reserved_zero", c_uint32),
        ("hash_version", DX_HASH),
        ("info_length", c_uint8),
        ("indirect_levels", c_uint8),
        ("unused_flags", c_uint8),
    ]


class DXBase(Ext4Struct):
    def __init__(self, directory: "Directory", offset: int):
        self.directory: "Directory" = directory
        super().__init__(directory.volume, offset)

    @override
    def read_from_volume(self):
        reader = self.directory._open()  # pyright: ignore[reportPrivateUsage]
        _ = reader.seek(self.offset)
        data = reader.read(sizeof(self))
        _ = memmove(addressof(self), data, sizeof(self))


@final
class DXEntry(DXBase):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("hash", c_uint32),
        ("block", c_uint32),
    ]

    def __init__(self, parent: "DXEntriesBase", index: int):
        self.index: int = index
        self.parent: DXEntriesBase = parent
        dx_root_info: DXRootInfo = assert_type(parent.dx_root_info, DXRootInfo)  # pyright: ignore[reportAny]
        info_length: int = assert_type(dx_root_info.info_length, int)  # pyright: ignore[reportAny]
        super().__init__(
            parent.directory,
            parent.offset + parent.size + index * info_length,
        )


class DXEntriesBase(DXBase):
    @override
    def read_from_volume(self):
        super().read_from_volume()

    @property
    def entries(self) -> Generator[DXEntry, None, None]:
        count: int = assert_type(self.count, int)  # pyright: ignore[reportAny]
        for i in range(0, count - 1):
            yield DXEntry(self, i)


@final
class DXRoot(DXEntriesBase):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("dot", DotDirectoryEntry2),
        ("dotdot", DotDirectoryEntry2),
        ("dx_root_info", DXRootInfo),
        ("limit", c_uint16),
        ("count", c_uint16),
        ("block", c_uint32),
        # ("entries", DXEntry * self.count),
    ]

    def __init__(self, inode: "Directory"):
        super().__init__(inode, 0)
        cast(DotDirectoryEntry2, self.dot).volume = inode.volume
        cast(DotDirectoryEntry2, self.dotdot).volume = inode.volume


@final
class DXFake(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("inode", c_uint32),  # 0
        ("rec_len", c_uint16),
    ]

    @property
    def expected_magic(self):
        return 0

    @property
    def magic(self) -> int:
        inode: int = assert_type(self.inode, int)  # pyright: ignore[reportAny]
        return inode


@final
class DXNode(DXEntriesBase):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("fake", DXFake),
        ("name_len", c_uint8),
        ("file_type", c_uint8),
        ("limit", c_uint16),
        ("count", c_uint16),
        ("block", c_uint32),
        # ("entries", DXEntry * self.count),
    ]

    def __init__(self, directory: "Directory", offset: int):
        super().__init__(directory, offset)


@final
class DXTail(DXBase):
    _pack_ = 1
    # _anonymous_ = ("dt_reserved")
    _fields_ = [
        ("dt_reserved", c_uint32),
        ("dt_checksum", c_uint16),
    ]

    def __init__(self, parent: DXNode):
        self.parent = parent
        count: int = assert_type(parent.count, int)  # pyright: ignore[reportAny]
        dx_root_info: DXRootInfo = assert_type(parent.dx_root_info, DXRootInfo)  # pyright: ignore[reportAny]
        info_length: int = assert_type(dx_root_info.info_length, int)  # pyright: ignore[reportAny]
        super().__init__(
            parent.directory, parent.offset + parent.size + (count + 1) * info_length
        )
