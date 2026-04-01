import os
import sys

import atheris

with atheris.instrument_imports():  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
    from ext4 import Volume


MIN_DATA_SIZE = 128 * 1024  # 128KB


class FuzzableStream(atheris.FuzzedDataProvider):  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType,reportUntypedBaseClass]
    SUPERBLOCK_OFFSET: int = 0x400
    SUPERBLOCK_MAGIC_OFFSET: int = SUPERBLOCK_OFFSET + 0x38  # 0x438

    def __init__(self, data: bytes) -> None:
        # Pass to parent for fuzzing
        super().__init__(data)   # pyright: ignore[reportUnknownMemberType]

        # Pad data to minimum size for reading
        if len(data) < MIN_DATA_SIZE:
            data = data + b"\x00" * (MIN_DATA_SIZE - len(data))

        self._data: bytearray = bytearray(data)

        self._view: memoryview[bytearray] = memoryview(self._data)
        self._cursor: int = 0

    def read(self, size: int) -> bytes:
        result = self.peek(size)
        self._cursor += len(result)
        return result

    def peek(self, size: int) -> bytes:
        offset = self._cursor
        end = offset + size

        # Check if read overlaps with superblock region
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
            # bg_inode_table at offset 8 (for the lo part)
            result[8:12] = (2048).to_bytes(4, "little")  # inode table at block 2
            return bytes(result)

        # Check if reading inode table (at block 2, offset 2048 for 1K blocks)
        inode_table_start = 2048  # Block 2 * 1K block size
        inode_size = 128
        num_inodes = 32
        inode_table_end = inode_table_start + (
            num_inodes * inode_size
        )  # 32 inodes * 128 bytes

        # Check if we're reading within the inode table area OR might overlap with it
        # Allow reading from offset 0 up to inode_table_end
        if offset < inode_table_end and end > 0:
            # Create valid inode data for inodes 1-32
            result = bytearray(num_inodes * inode_size)

            # Root inode (inode 2) - set as directory (IFDIR = 0x4000)
            root_inode_offset = (2 - 1) * inode_size  # inode 2 is at index 1
            result[root_inode_offset : root_inode_offset + 2] = (
                b"\x00\x40"  # i_mode = IFDIR
            )

            # Bad blocks inode (inode 6)
            bad_inode_offset = (6 - 1) * inode_size
            result[bad_inode_offset : bad_inode_offset + 2] = b"\x00\x20"  # IFBLK

            # Journal inode (inode 11)
            journal_inode_offset = (11 - 1) * inode_size
            result[journal_inode_offset : journal_inode_offset + 2] = (
                b"\x00\x40"  # IFDIR
            )

            # Boot loader inode (inode 5)
            boot_inode_offset = (5 - 1) * inode_size
            result[boot_inode_offset : boot_inode_offset + 2] = b"\x00\x20"  # IFBLK

            # Extract the portion requested
            start = offset  # Read starts at offset 128, so start at 128 in our generated table
            return bytes(result[start : start + size])

        return self._view[offset:end].tobytes()

    def seek(self, offset: int, mode: int | None = None) -> int:
        if mode is None:
            mode = os.SEEK_SET
        if mode == os.SEEK_SET:
            self._cursor = offset
        elif mode == os.SEEK_CUR:
            self._cursor += offset
        elif mode == os.SEEK_END:
            self._cursor = len(self._data) + offset
        return self._cursor

    def tell(self) -> int:
        return self._cursor


def TestOneInput(data: bytes) -> None:
    stream = FuzzableStream(data)

    vol = Volume(stream)
    _ = vol.superblock
    for bd in vol.group_descriptors:
        _ = bd.bg_block_bitmap

    root = vol.root
    for dirent, _ in root.opendir():
        _ = dirent.name_bytes

    while next(vol.inodes[2].xattrs, None) is not None:
        pass


argv = [sys.argv[0], "corpus", "-timeout=10", *sys.argv[1:]]
print("argv: ", end="")
print(argv)
_ = atheris.Setup(argv, TestOneInput)
atheris.Fuzz()
