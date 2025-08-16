from __future__ import annotations

import os
import sys
import ext4

from typing import cast

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
        FAILED = True
        print("fail")
        print("  ", end="")
        print(e)


def _assert(source: str):
    global FAILED
    print(f"check {source}: ", end="")
    if eval(source):
        print("pass")
        return

    FAILED = True
    print("fail")


test_path_tuple("/", tuple())
test_path_tuple(b"/", tuple())
test_path_tuple("/test", (b"test",))
test_path_tuple(b"/test", (b"test",))
test_path_tuple("/test/test", (b"test", b"test"))
test_path_tuple(b"/test/test", (b"test", b"test"))

for img_file in ("test32.ext4", "test64.ext4"):
    offset = os.path.getsize(img_file) - os.path.getsize(f"{img_file}.tmp")
    _assert("offset > 0")
    with open(img_file, "rb") as f:
        try:
            print("check MagicError: ", end="")
            _ = ext4.Volume(f, offset=0)
            FAILED = True
            print("fail")
            print("  MagicError not raised")
        except ext4.struct.MagicError:
            print("pass")

        except Exception as e:
            FAILED = True
            print("fail")
            print("  ", end="")
            print(e)

        # Extract specific file
        volume = ext4.Volume(f, offset=offset)
        inode = cast(ext4.File, volume.inode_at("/test.txt"))
        _assert("isinstance(inode, ext4.File)")
        b = inode.open()
        _assert("isinstance(b, ext4.BlockIO)")
        _assert("b.readable()")
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

if FAILED:
    sys.exit(1)
