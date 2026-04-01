# pyright: reportImportCycles=false
import warnings
from collections.abc import Generator
from ctypes import (
    LittleEndianStructure,
    addressof,
    c_char,
    c_uint8,
    c_uint16,
    c_uint32,
    memmove,
    sizeof,
)
from typing import (
    TYPE_CHECKING,
    final,
)

from ._compat import (
    assert_cast,
    override,
)
from .enum import DX_HASH
from .struct import (
    Ext4Struct,
    MagicError,
)

if TYPE_CHECKING:
    from .inode import Directory
    from .volume import Volume


class LittleEndianStructureWithVolume(LittleEndianStructure):
    def __init__(self) -> None:
        super().__init__()
        self._volume: Volume | None = None

    @property
    def volume(self) -> "Volume":
        assert self._volume is not None
        return self._volume

    @volume.setter
    def volume(self, volume: "Volume") -> None:
        self._volume = volume


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
        name = assert_cast(self.name, bytes)  # pyright: ignore[reportAny]
        if name in (b".", b".."):
            return

        message = f"{self} dot or dotdot entry name invalid! actual={name}"
        assert self.volume is not None
        if not self.volume.ignore_magic:
            raise MagicError(message)

        warnings.warn(
            message,
            RuntimeWarning,
            stacklevel=2,
        )


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
    def __init__(self, directory: "Directory", offset: int) -> None:
        self.directory: Directory = directory
        super().__init__(directory.volume, offset)

    @override
    def read_from_volume(self) -> None:
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

    def __init__(self, parent: "DXEntriesBase", index: int) -> None:
        self.index: int = index
        self.parent: DXEntriesBase = parent
        super().__init__(
            parent.directory,
            parent.offset + parent.size + index * parent.info_length,
        )


class DXEntriesBase(DXBase):
    @override
    def read_from_volume(self) -> None:
        super().read_from_volume()

    @property
    def entries(self) -> Generator[DXEntry, None, None]:
        count = assert_cast(self.count, int)  # pyright: ignore[reportAny]
        for i in range(0, count - 1):
            yield DXEntry(self, i)

    @property
    def info_length(self) -> int:
        parent = self
        while not isinstance(parent, DXRoot):
            parent = assert_cast(parent.parent, DXEntriesBase)  # pyright: ignore[reportAny]

        dx_root_info = assert_cast(parent.dx_root_info, DXRootInfo)  # pyright: ignore[reportAny]
        return assert_cast(dx_root_info.info_length, int)  # pyright: ignore[reportAny]


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

    def __init__(self, inode: "Directory") -> None:
        super().__init__(inode, 0)


@final
class DXFake(LittleEndianStructure):
    _pack_ = 1
    # _anonymous_ = ("")
    _fields_ = [
        ("inode", c_uint32),  # 0
        ("rec_len", c_uint16),
    ]

    @property
    def expected_magic(self) -> int:
        return 0

    @property
    def magic(self) -> int:
        inode = assert_cast(self.inode, int)  # pyright: ignore[reportAny]
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

    def __init__(self, directory: "Directory", offset: int) -> None:
        super().__init__(directory, offset)


@final
class DXTail(DXBase):
    _pack_ = 1
    # _anonymous_ = ("dt_reserved")
    _fields_ = [
        ("dt_reserved", c_uint32),
        ("dt_checksum", c_uint16),
    ]

    def __init__(self, parent: DXNode) -> None:
        self.parent = parent
        count = assert_cast(parent.count, int)  # pyright: ignore[reportAny]
        super().__init__(
            parent.directory,
            parent.offset + parent.size + (count + 1) * parent.info_length,
        )
