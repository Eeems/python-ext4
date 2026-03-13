from __future__ import annotations

import os
import sys
import traceback
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


def _eval_or_False(source: str) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
    try:
        return eval(source)  # pyright: ignore[reportAny]

    except Exception:
        traceback.print_exc()
        return False


def _assert(source: str, debug: Callable[[], Any] | None = None):  # pyright: ignore[reportExplicitAny]
    global FAILED
    print(f"check {source}: ", end="")
    if _eval_or_False(source):
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
    test_root_inode(volume)

    _assert("volume.root.is_htree == True")
    _assert("volume.root.htree is not None")

    htree = volume.root.htree
    _assert("htree is not None")
    if htree is not None:
        _assert("isinstance(htree.dot, ext4.DotDirectoryEntry2)", lambda: htree.dot)  # pyright: ignore[reportOptionalMemberAccess, reportAny]
        _assert(
            "isinstance(htree.dotdot, ext4.DotDirectoryEntry2)",
            lambda: htree.dotdot,  # pyright: ignore[reportOptionalMemberAccess, reportAny]
        )
        _assert("htree.limit > 0")
        _assert("htree.count > 0")
        _assert("htree.count <= htree.limit")
        _assert("htree.block >= 0")
        _assert("htree.dx_root_info is not None")

        _assert("htree.dot.verify() is None")
        _assert("htree.dotdot.verify() is None")

        _assert("htree.dot.name == b'.'", lambda: htree.dot.name)  # pyright: ignore[reportAny, reportOptionalMemberAccess]
        _assert("htree.dotdot.name == b'..'", lambda: htree.dotdot.name)  # pyright: ignore[reportAny, reportOptionalMemberAccess]

        dx_root_info = htree.dx_root_info  # pyright: ignore[reportAny]
        _assert("isinstance(dx_root_info.hash_version, ext4.DX_HASH)")
        _assert("dx_root_info.info_length == 8")
        _assert("dx_root_info.indirect_levels == 1")

        entries = list(htree.entries)
        _assert("len(entries) > 0")
        _assert("len(entries) == htree.count - 1")
        for entry in entries:
            _assert("isinstance(entry.hash, int)")
            _assert("isinstance(entry.block, int)")

        first_entry = entries[0]
        _assert("first_entry.hash >= 0")
        _assert("first_entry.block > 0")

        block_io = ext4.BlockIO(volume.root)
        block = block_io.blocks[first_entry.block]  # pyright: ignore[reportAny]
        _assert("len(block) > 0")
        _assert(f"len(block) == {volume.block_size}")

        dirent = ext4.DirectoryEntry2(volume.root, 0)
        _assert("dirent.rec_len > 0")

    non_htree_dir = cast(ext4.Directory, volume.inode_at("/empty"))
    _assert("not non_htree_dir.is_htree")

if FAILED:
    sys.exit(1)
