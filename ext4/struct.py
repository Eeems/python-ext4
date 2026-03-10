# pyright: reportImportCycles=false
import warnings
import ctypes

from ctypes import LittleEndianStructure
from ctypes import memmove
from ctypes import addressof
from ctypes import sizeof
from crcmod import mkCrcFun  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from typing import cast
from typing import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .volume import Volume

SimpleCData = (
    ctypes.py_object
    | ctypes.c_short
    | ctypes.c_ushort
    | ctypes.c_long
    | ctypes.c_ulong
    | ctypes.c_int
    | ctypes.c_uint
    | ctypes.c_float
    | ctypes.c_double
    | ctypes.c_longdouble
    | ctypes.c_longlong
    | ctypes.c_ulonglong
    | ctypes.c_ubyte
    | ctypes.c_byte
    | ctypes.c_char
    | ctypes.c_char_p
    | ctypes.c_void_p
    | ctypes.c_bool
    | ctypes.c_wchar_p
    | ctypes.c_wchar
    | ctypes.c_uint
    | ctypes.c_uint8
    | ctypes.c_uint16
    | ctypes.c_uint32
    | ctypes.c_uint64
    | ctypes.c_int
    | ctypes.c_int8
    | ctypes.c_int16
    | ctypes.c_int32
    | ctypes.c_int64
)
crc32c = cast(Callable[..., int], mkCrcFun(0x11EDC6F41))


class MagicError(Exception):
    pass


class ChecksumError(Exception):
    pass


def to_hex(data: int | list[int] | bytes | None) -> str:
    if data is None:
        return "None"

    if isinstance(data, int):
        return f"0x{data:02X}"

    return "0x" + "".join([f"{x:02X}" for x in data])


class Ext4Struct(LittleEndianStructure):
    def __init__(self, volume: "Volume", offset: int):
        super().__init__()
        self.volume: "Volume" = volume
        self.offset: int = offset
        self.read_from_volume()
        self.verify()

    @classmethod
    def field_type(cls, name: str) -> SimpleCData | None:
        assert isinstance(cls._fields_, list)
        assert not [x for x in cls._fields_ if not isinstance(x, tuple)]
        for _name, _type in cast(list[tuple[str, SimpleCData]], cls._fields_):
            if _name == name:
                return _type

        return None

    def read_from_volume(self):
        _ = self.volume.seek(self.offset)
        data = self.volume.read(sizeof(self))
        _ = memmove(addressof(self), data, sizeof(self))

    @property
    def size(self):
        return sizeof(self)

    @property
    def magic(self):
        return None

    @property
    def expected_magic(self) -> None:
        return None

    @property
    def checksum(self):
        return None

    @property
    def expected_checksum(self):
        return None

    @property
    def ignore_magic(self):
        return self.volume.ignore_magic

    def verify(self):
        """
        Verify magic numbers
        """
        if self.magic == self.expected_magic:
            return

        message = (
            f"{self} magic bytes do not match! "
            f"expected={to_hex(self.expected_magic)}, "
            f"actual={to_hex(self.magic)}"
        )
        if not self.ignore_magic:
            raise MagicError(message)

        warnings.warn(message, RuntimeWarning)

    def validate(self):
        """
        Validate data checksums
        """
        if self.checksum == self.expected_checksum:
            return

        message = (
            f"{self} checksum does not match! "
            f"expected={self.expected_checksum}, "
            f"actual={self.checksum}"
        )
        if not self.volume.ignore_checksum:
            raise ChecksumError(message)

        warnings.warn(message, RuntimeWarning)
