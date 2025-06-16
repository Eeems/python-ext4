from __future__ import annotations

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

with open("test.ext4", "rb") as f:
    # Extract specific file
    volume = ext4.Volume(f, offset=0)
    inode = cast(ext4.File, volume.inode_at("/test.txt"))
    _assert("isinstance(inode, ext4.File)")
    b = inode.open()
    _assert("isinstance(b, ext4.BlockIO)")
    _assert("b.readable()")
    _assert("b.seekable()")
    _assert("b.seek(1) == 1")
    _assert("b.seek(0) == 0")
    _assert("b.seek(10) == 10")

if FAILED:
    sys.exit(1)
