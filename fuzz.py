import os
import sys

import atheris

MIN_DATA_SIZE = 128 * 1024  # 128KB

seed_file = os.path.join("corpus", "seed", "seed.bin")
if not os.path.exists(seed_file) or os.path.getsize(seed_file) != MIN_DATA_SIZE:
    os.makedirs(os.path.dirname(seed_file), exist_ok=True)
    with open(seed_file, "wb") as f:
        _ = f.write(b"\x00" * MIN_DATA_SIZE)

with atheris.instrument_imports():  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
    from ext4 import (
        File,
        InodeError,
        SymbolicLink,
        Volume,
    )
    from ext4._compat import (
        PeekableStream,
        override,
    )


class FuzzableStream(PeekableStream):
    SUPERBLOCK_OFFSET: int = 0x400
    SUPERBLOCK_MAGIC_OFFSET: int = SUPERBLOCK_OFFSET + 0x38  # 0x438

    def __init__(self, data: bytes) -> None:
        self._view: memoryview[bytearray] = memoryview(data)
        self._cursor: int = 0

    @override
    def read(self, size: int | None = None) -> bytes:
        result = self.peek(size)
        self._cursor += len(result)
        return result

    @override
    def peek(self, size: int | None = None) -> bytes:  # noqa: PLR0915
        offset = self._cursor
        if size is None:
            size = len(self._view) - offset

        end = offset + size

        sb_start = self.SUPERBLOCK_OFFSET
        sb_end = sb_start + 256  # Superblock is 256 bytes
        if offset < sb_end and end >= sb_start:
            # Build superblock data from scratch
            result = bytearray(256)

            # s_inodes_count at offset 0
            result[0x00:0x04] = b"\x20\x00\x00\x00"  # 32 inodes

            # s_blocks_count_lo at offset 0x04
            result[0x04:0x08] = b"\x00\x80\x00\x00"  # 128 blocks

            # s_free_blocks_count_lo at offset 0x0C
            result[0x0C:0x10] = b"\x00\x80\x00\x00"

            # s_free_inodes_count at offset 0x10
            result[0x10:0x14] = b"\x20\x00\x00\x00"

            # s_first_data_block at offset 0x14
            result[0x14:0x18] = b"\x01\x00\x00\x00"

            # s_log_block_size at offset 0x18
            result[0x18:0x1C] = b"\x00\x00\x00\x00"

            # s_blocks_per_group at offset 0x20
            result[0x20:0x24] = b"\x08\x00\x00\x00"

            # s_inodes_per_group at offset 0x28
            result[0x28:0x2C] = b"\x10\x00\x00\x00"

            # s_magic at offset 0x38
            result[0x38:0x3A] = b"\x53\xef"  # 0xEF53

            # s_inode_size at offset 0x58
            result[0x58:0x5A] = b"\x80\x00"  # 128

            # s_desc_size at offset 0x60
            result[0x60:0x62] = b"\x20\x00"  # 32

            # s_feature_compat at offset 0x64
            result[0x64:0x68] = b"\x00\x00\x00\x00"

            # s_feature_incompat at offset 0x68
            result[0x68:0x6C] = b"\x40\x00\x00\x00"  # IS64BIT

            # s_feature_ro_compat at offset 0x6C
            result[0x6C:0x70] = b"\x00\x00\x00\x00"

            # Extract the requested portion
            start = max(0, offset - sb_start)
            result = result[start : end - sb_start] if end > sb_start else b""

            # Add data before superblock if requested
            if offset < sb_start:
                before = self._view[offset : min(sb_start, end)].tobytes()
                result = before + result

            # Add data after superblock if requested
            if end > sb_end:
                after = self._view[sb_end:end].tobytes()
                result = bytes(result) + after

            return bytes(result)

        # Check if reading block group descriptor table (at block 3, offset 3072)
        bgdt_start = 3072  # Block 3 * 1K block size
        bgdt_size = 32  # 32 bytes per block descriptor
        bgdt_end = bgdt_start + bgdt_size

        if offset < bgdt_end and end >= bgdt_start:
            # Generate valid block descriptor
            result = bytearray(bgdt_size)
            # bg_inode_table_lo at offset 8
            # Set to block 2 = 2
            result[8:12] = (2).to_bytes(4, "little")
            return bytes(result)

        # Check if reading inode table (at block 2, offset 2048 for 1K blocks)
        inode_table_start = 2048  # Block 2 * 1K block size
        inode_size = 128
        num_inodes = 32
        inode_table_end = inode_table_start + (
            num_inodes * inode_size
        )  # 32 inodes * 128 bytes

        # Only serve generated inode table for reads in the exact inode table region (2048-4096)
        if offset >= inode_table_start and offset < inode_table_end:
            # Create valid inode data for inodes 1-32
            result = bytearray(num_inodes * inode_size)

            # Inode 1 - Regular file (IFREG = 0x8000)
            result[0:2] = b"\x00\x80"

            # Root inode (inode 2) - set as directory (IFDIR = 0x4000)
            result[128:130] = b"\x00\x40"  # IFDIR

            # Inode 3 - Symbolic link (IFLNK = 0xA000)
            result[256:258] = b"\x00\xa0"

            # Inode 4 - Socket (IFSOCK = 0xC000)
            result[384:386] = b"\x00\xc0"

            # Boot loader inode (inode 5) - Block device (IFBLK = 0x6000)
            result[512:514] = b"\x00\x60"  # IFBLK

            # Bad blocks inode (inode 6) - Block device (IFBLK = 0x6000)
            result[640:642] = b"\x00\x60"  # IFBLK

            # Inode 7 - Character device (IFCHR = 0x2000)
            result[768:770] = b"\x00\x20"

            # Inode 8 - FIFO (IFIFO = 0x1000)
            result[896:898] = b"\x00\x10"

            # Inode 9 - Another directory
            result[1024:1026] = b"\x00\x40"

            # Inode 10 - Another file
            result[1152:1154] = b"\x00\x80"

            # Journal inode (inode 11) - set as directory (IFDIR = 0x4000)
            result[1280:1282] = b"\x00\x40"

            # Inode 12-32 - Mix of files and directories
            for i in range(12, 33):
                inode_offset = (i - 1) * inode_size
                file_type = 0x40 if i % 3 == 0 else 0x80  # Alternate IFDIR and IFREG
                result[inode_offset : inode_offset + 2] = file_type.to_bytes(
                    2, "little"
                )

            # Extract the portion requested relative to inode table start
            start = offset - inode_table_start
            return bytes(result[start : start + size])

        return self._view[offset:end].tobytes()

    @override
    def seek(self, offset: int, mode: int | None = None) -> int:
        if mode is None:
            mode = os.SEEK_SET

        if mode == os.SEEK_SET:
            self._cursor = offset

        elif mode == os.SEEK_CUR:
            self._cursor += offset

        elif mode == os.SEEK_END:
            self._cursor = len(self._view) + offset

        return self._cursor

    @override
    def tell(self) -> int:
        return self._cursor


def TestOneInput(data: bytes) -> None:
    if len(data) < MIN_DATA_SIZE:
        return

    stream = FuzzableStream(data)

    vol = Volume(
        stream,
        ignore_checksum=True,
        ignore_flags=True,
        ignore_magic=True,
        ignore_attr_name_index=True,
    )
    _ = vol.superblock
    for bd in vol.group_descriptors:
        _ = bd.bg_block_bitmap

    try:
        root = vol.root

    except InodeError:
        return

    for dirent, _ in root.opendir():
        _ = dirent.name_bytes

    try:
        for _ in vol.inodes:
            pass

    except InodeError:
        return

    for inode in [
        vol.inodes[1],  # File
        vol.inodes[2],  # Directory (root)
        vol.inodes[3],  # SymbolicLink
        vol.inodes[4],  # Socket
        vol.inodes[5],  # BlockDevice
        vol.inodes[6],  # BlockDevice (bad blocks)
        vol.inodes[7],  # CharacterDevice
        vol.inodes[8],  # Fifo
        vol.inodes[9],  # Directory
        vol.inodes[10],  # File
        vol.inodes[11],  # Directory (journal)
    ]:
        _ = inode.extents
        _ = inode.i_size
        if isinstance(inode, File):
            _ = inode.open()

        if isinstance(inode, SymbolicLink):
            _ = inode.readlink()

    while next(vol.inodes[2].xattrs, None) is not None:
        pass

    _ = vol.bad_blocks
    _ = vol.boot_loader
    _ = vol.journal


argv = [sys.argv[0], "corpus", "-timeout=10", *sys.argv[1:]]
print("argv: ", end="")
print(argv)
_ = atheris.Setup(argv, TestOneInput)
atheris.Fuzz()
