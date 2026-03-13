from __future__ import annotations

import os
import sys
import ext4

from io import BufferedReader
from typing import cast
from typing import Callable
from typing import Any

FAILED = False


def test_path_tuple(path: str | bytes, expected: tuple[bytes, ...]):
    global FAILED
    print(f"check Volume.path_tuple({path}): ", end="")
    try:
        t = ext4.Volume.path_tuple(path)
        if t != expected:
            raise ValueError(f"Result is unexpected {t}")

        print("pass")

    except Exception as e:
        FAILED = True  # pyright: ignore[reportConstantRedefinition]
        print("fail")
        print("  ", end="")
        print(e)


def _assert(source: str, debug: Callable[[], Any] | None = None):  # pyright: ignore[reportExplicitAny]
    global FAILED
    print(f"check {source}: ", end="")
    if eval(source):
        print("pass")
        return

    FAILED = True  # pyright: ignore[reportConstantRedefinition]
    print("fail")
    if debug is not None:
        print(f"  {debug()}")


def test_magic_error(f: BufferedReader):
    global FAILED
    try:
        print("check MagicError: ", end="")
        _ = ext4.Volume(f, offset=0)
        FAILED = True  # pyright: ignore[reportConstantRedefinition]
        print("fail")
        print("  MagicError not raised")
    except ext4.struct.MagicError:
        print("pass")

    except Exception as e:
        FAILED = True  # pyright: ignore[reportConstantRedefinition]
        print("fail")
        print("  ", end="")
        print(e)


def test_root_inode(volume: ext4.Volume):
    global FAILED
    try:
        print("Validate root inode: ", end="")
        volume.root.validate()
        print("pass")

    except ext4.struct.ChecksumError as e:
        FAILED = True  # pyright: ignore[reportConstantRedefinition]
        print("fail")
        print("  ", end="")
        print(e)


print("check ext4.Volume stream validation: ", end="")
try:
    _ = ext4.Volume(1)  # pyright: ignore[reportArgumentType]
    FAILED = True  # pyright: ignore[reportConstantRedefinition]
    print("fail")

except ext4.InvalidStreamException:
    print("pass")

except Exception as e:
    FAILED = True  # pyright: ignore[reportConstantRedefinition]
    print("fail")
    print("  ", end="")
    print(e)

test_path_tuple("/", tuple())
test_path_tuple(b"/", tuple())
test_path_tuple("/test", (b"test",))
test_path_tuple(b"/test", (b"test",))
test_path_tuple("/test/test", (b"test", b"test"))
test_path_tuple(b"/test/test", (b"test", b"test"))

for img_file in ("test32.ext4", "test64.ext4"):
    print(f"Testing image: {img_file}")
    offset = os.path.getsize(img_file) - os.path.getsize(f"{img_file}.tmp")
    _assert("offset > 0", lambda: offset)
    if offset < 0:
        continue

    with open(img_file, "rb") as f:
        test_magic_error(f)

        volume = ext4.Volume(f, offset=offset)
        test_root_inode(volume)

        inode = cast(ext4.File, volume.inode_at("/test.txt"))
        _assert("isinstance(inode, ext4.File)")
        b = inode.open()
        _assert("isinstance(b, ext4.BlockIO)")
        _assert("b.readable()")
        _assert("not b.peek(0)")
        size = volume.block_size + 1
        _assert(f"len(b.peek({size})) == {size}")
        _assert("b.seekable()")
        _assert("b.seek(1) == 1")
        _assert("b.seek(0) == 0")
        _assert("b.seek(10) == 10")
        for i in range(1, 101):
            inode = volume.inode_at(f"/test{i}.txt")
            attrs = {k: v for k, v in inode.xattrs}
            for j in range(1, 21):
                _assert(f'attrs["user.name{j}"] == b"value{i}_{j}"')

            data = inode.open().read()
            _assert(f'data == b"hello world{i}\\n"')

        inode = cast(ext4.File, volume.inode_at("/test1.txt"))
        b = inode.open()
        data = b"hello world1\n"
        for x in range(1, 15):
            _ = b.seek(0)
            _assert(f"b.read({x}) == {data[:x]}", lambda: b.seek(0) == 0 and b.read(x))

img_file = "test_htree.ext4"
print(f"Testing image: {img_file}")
with open(img_file, "rb") as f:
    volume = ext4.Volume(f)
    _assert("volume.root.is_htree")
    test_root_inode(volume)

if FAILED:
    sys.exit(1)
