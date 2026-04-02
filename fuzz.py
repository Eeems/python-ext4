import os
import random
import string
import subprocess
import sys
import tempfile
import warnings
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)

import atheris

warnings.filterwarnings("ignore")

EXPECTED_DATA_SIZE = 145


seed_file = os.path.join("corpus", "seed", "seed.bin")
if not os.path.exists(seed_file) or os.stat(seed_file).st_size != EXPECTED_DATA_SIZE:
    os.makedirs(os.path.dirname(seed_file), exist_ok=True)
    with open(seed_file, "wb") as f:
        _ = f.write(b"\x00" * EXPECTED_DATA_SIZE)

with atheris.instrument_imports():  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
    from ext4 import (
        Directory,
        File,
        SymbolicLink,
        Volume,
    )


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue, reportUnknownVariableType]

    if TYPE_CHECKING:
        fdp.ConsumeIntInRange = cast(Callable[[int, int], int], fdp.ConsumeIntInRange)
        fdp.ConsumeInt = cast(Callable[[int], int], fdp.ConsumeInt)
        fdp.PickValueInList = cast(Callable[[list[Any]], int], fdp.PickValueInList)  # pyright: ignore[reportExplicitAny]

    img_size: int = fdp.ConsumeIntInRange(32, 64)
    block_size: int = [1024, 2048, 4096][fdp.ConsumeIntInRange(0, 2)]
    inode_size: int = [128, 256][fdp.ConsumeIntInRange(0, 1)]
    num_dirs: int = fdp.ConsumeIntInRange(2, 20)
    num_files: int = fdp.ConsumeIntInRange(5, 50)
    num_symlinks: int = fdp.ConsumeIntInRange(0, 10)
    num_hardlinks: int = fdp.ConsumeIntInRange(0, 5)
    num_xattr_files: int = fdp.ConsumeIntInRange(0, 10)
    max_file_size: int = fdp.ConsumeIntInRange(1, 64)
    rng_seed: int = fdp.ConsumeInt(1024)
    rng = random.Random(rng_seed)  # noqa: S311

    FEATURES = [
        "extent",
        "dir_index",
        "flex_bg",
        "sparse_super",
        "64bit",
        "metadata_csum",
        "huge_file",
        "orphan_file",
    ]
    features = [f for f in FEATURES if fdp.PickValueInList([True, False])]

    with tempfile.TemporaryDirectory(prefix="ext4_fuzz_") as tmpdir:
        rootdir = os.path.join(tmpdir, "root")
        os.mkdir(rootdir)
        dirs: list[str] = [rootdir]
        for _ in range(num_dirs):
            parent = rng.choice(dirs)
            name = "".join(
                rng.choice(string.ascii_letters + string.digits)
                for _ in range(rng.randint(1, 32))
            )
            path = os.path.join(parent, name)
            os.mkdir(path)
            dirs.append(path)

        files: list[str] = []
        for _ in range(num_files):
            parent = rng.choice(dirs)
            name = "".join(
                rng.choice(string.ascii_letters + string.digits)
                for _ in range(rng.randint(1, 64))
            )
            path = os.path.join(parent, name)
            size = rng.randint(1, max_file_size * 1024)
            with open(path, "wb") as f:
                _ = f.write(rng.randbytes(size))

            files.append(path)

        targets = files + dirs
        for _ in range(num_symlinks):
            target = rng.choice(targets)
            parent = rng.choice(dirs)
            name = "".join(
                rng.choice(string.ascii_letters + string.digits)
                for _ in range(rng.randint(1, 32))
            )
            os.symlink(target, os.path.join(parent, name))

        for _ in range(num_hardlinks):
            if files:
                target = rng.choice(files)
                parent = rng.choice(dirs)
                name = "".join(
                    rng.choice(string.ascii_letters + string.digits)
                    for _ in range(rng.randint(1, 32))
                )
                os.link(target, os.path.join(parent, name))

        for _ in range(num_xattr_files):
            if files:
                path = rng.choice(files)
                for _ in range(rng.randint(1, 5)):
                    key = f"user.xattr_{rng.randint(1, 10)}"
                    value = rng.randbytes(rng.randint(8, 64))
                    os.setxattr(path, key, value)

        img_path = os.path.join(tmpdir, "image.img")
        cmd = [
            "mkfs.ext4",
            "-d",
            rootdir,
            "-I",
            str(inode_size),
            *(["-O", ",".join(features)] if features else []),
            "-b",
            str(block_size),
            img_path,
            f"{img_size}M",
        ]
        result = subprocess.run(cmd, check=False, capture_output=True)  # noqa: S607,S603
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        try:
            with open(img_path, "rb") as f:
                volume = Volume(
                    f,
                    ignore_checksum=True,
                    ignore_flags=True,
                    ignore_magic=True,
                    ignore_attr_name_index=True,
                )
                _ = volume.superblock
                for group_descriptor in volume.group_descriptors:
                    _ = group_descriptor.bg_block_bitmap

                root = volume.root
                htree = root.htree
                if htree is not None:
                    for _ in htree.entries:
                        pass

                for dirent, _ in root.opendir():
                    _ = dirent.name_bytes

                for inode in volume.inodes:
                    _ = inode.extents
                    _ = inode.i_size
                    if isinstance(inode, File):
                        _ = inode.open().read()

                    elif isinstance(inode, SymbolicLink):
                        _ = inode.readlink()

                    elif isinstance(inode, Directory):
                        for _ in inode.opendir():
                            pass

                    while next(inode.xattrs, None) is not None:
                        pass

                _ = volume.bad_blocks
                _ = volume.boot_loader
                _ = volume.journal

        finally:
            if os.path.exists(img_path):
                os.remove(img_path)


def custom_mutator(data: bytes, _max_size: int, _seed: int) -> bytes:
    if len(data) >= EXPECTED_DATA_SIZE:
        return data[:EXPECTED_DATA_SIZE]

    return data + b"\x00" * (EXPECTED_DATA_SIZE - len(data))


argv = [
    sys.argv[0],
    "corpus",
    "-timeout=30",
    f"-max_len={EXPECTED_DATA_SIZE}",
    *sys.argv[1:],
]
print("argv: ", end="")
print(argv)
_ = atheris.Setup(argv, TestOneInput, custom_mutator=custom_mutator)
atheris.Fuzz()
