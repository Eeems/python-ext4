import errno
import os
import sys
import warnings
from typing import final

import atheris

warnings.filterwarnings("ignore")

MIN_DATA_SIZE = 128 * 1024  # 128KB

seed_file = os.path.join("corpus", "seed", "seed.bin")
if not os.path.exists(seed_file) or os.path.getsize(seed_file) != MIN_DATA_SIZE:
    os.makedirs(os.path.dirname(seed_file), exist_ok=True)
    with open(seed_file, "wb") as f:
        _ = f.write(b"\x00" * MIN_DATA_SIZE)

with atheris.instrument_imports():  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
    from ext4 import (
        EXT4_INO,
        Directory,
        File,
        InodeError,
        SymbolicLink,
        Volume,
    )
    from ext4._compat import (
        PeekableStream,
        override,
    )


@final
class FuzzableStream(PeekableStream):
    SUPERBLOCK_OFFSET: int = 0x400
    SUPERBLOCK_MAGIC_OFFSET: int = SUPERBLOCK_OFFSET + 0x38  # 0x438

    def __init__(self, data: bytes) -> None:
        self._view: memoryview[bytearray] = memoryview(data)
        self._cursor: int = 0

        # Decision bytes (contiguous)
        self._enable_extents = data[0] & 0x80
        self._enable_htree = data[1] & 0x80
        self._num_groups = (data[2] % 8) + 1
        self._log_block_size = data[3] % 4
        self._feature_incompat = int.from_bytes(data[4:8], "little")
        self._extent_depth = data[5] % 2
        self._htree_complexity = data[6] % 2

        # Content bytes for structures (contiguous after decisions)
        self._extent_num_extents = (data[7] % 5) + 1
        self._extent_block = int.from_bytes(data[8:12], "little") & 0xFFFF
        self._htree_num_entries = (data[12] % 8) + 1
        self._htree_hash_version = data[13] % 4

        # Block group content (16 bytes, 2 groups worth)
        self._bg_data = data[14:30]

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
        block_size = 1024 << self._log_block_size  # 1K, 2K, 4K, or 8K
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
            result[0x18:0x1C] = self._log_block_size.to_bytes(4, "little")

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
            result[0x68:0x6C] = self._feature_incompat.to_bytes(4, "little")

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

        # Check if reading block group descriptor table
        bgdt_start = block_size * 3  # Block 3
        bgdt_size = 32  # 32 bytes per block descriptor
        bgdt_end = bgdt_start + (bgdt_size * self._num_groups)

        if offset < bgdt_end and end >= bgdt_start:
            # Generate block descriptors based on data bytes
            result = bytearray(bgdt_size * self._num_groups)
            for i in range(self._num_groups):
                base = i * bgdt_size
                bb_offset = 2 + (i * 2)
                ib_offset = 4 + (i * 2)
                result[base + 0 : base + 2] = bytes(
                    [self._bg_data[bb_offset % 16], self._bg_data[(bb_offset + 1) % 16]]
                )
                result[base + 4 : base + 6] = bytes(
                    [self._bg_data[ib_offset % 16], self._bg_data[(ib_offset + 1) % 16]]
                )
                result[base + 8 : base + 12] = (2 + i * 4).to_bytes(4, "little")

            start = max(0, offset - bgdt_start)
            end_pos = min(bgdt_end, end)
            return bytes(result[start : end_pos - bgdt_start])

        # Check if reading inode table (at block 2, offset 2048 for 1K blocks)
        inode_table_start = block_size * 2  # Block 2
        inode_size = 128
        num_inodes = 32
        inode_table_end = inode_table_start + (
            num_inodes * inode_size
        )  # 32 inodes * 128 bytes

        # Only serve generated inode table for reads in the exact inode table region
        if offset >= inode_table_start and offset < inode_table_end:
            # Create valid inode data for inodes 1-32
            result = bytearray(num_inodes * inode_size)

            # Determine which inodes get special flags based on data bytes
            extents_inodes: set[int] = {1, 10} if self._enable_extents else set()
            htree_inodes: set[int] = {2, 9, 11} if self._enable_htree else set()
            dir_inodes = {2, 9, 11}

            for i in range(1, num_inodes + 1):
                inode_offset = (i - 1) * inode_size
                file_type = 0x40 if i in dir_inodes else 0x80
                if i in htree_inodes:
                    file_type = 0x40  # Directory

                result[inode_offset : inode_offset + 2] = file_type.to_bytes(
                    2, "little"
                )

                # Set i_flags for EXTENTS and INDEX
                flags = 0
                if i in extents_inodes:
                    flags |= 0x80000  # EXTENTS
                if i in htree_inodes:
                    flags |= 0x1000  # INDEX

                if flags:
                    result[inode_offset + 0x14 : inode_offset + 0x18] = flags.to_bytes(
                        4, "little"
                    )

                # Generate extent tree in i_block[] for EXTENTS inodes
                if i in extents_inodes:
                    extent_offset = inode_offset + 0x28  # i_block offset

                    if self._extent_depth == 0:
                        # Depth 0: ExtentHeader + Extent entries
                        eh_magic = 0xF30A
                        result[extent_offset : extent_offset + 2] = eh_magic.to_bytes(
                            2, "little"
                        )
                        result[extent_offset + 2 : extent_offset + 4] = (
                            self._extent_num_extents.to_bytes(2, "little")
                        )
                        result[extent_offset + 4 : extent_offset + 6] = (
                            self._extent_num_extents
                        ).to_bytes(2, "little")
                        result[extent_offset + 6 : extent_offset + 8] = (
                            b"\x00\x00"  # eh_depth = 0
                        )
                        result[extent_offset + 8 : extent_offset + 12] = (
                            b"\x00\x00\x00\x00"
                        )

                        # Extent entries (ee_block, ee_len, ee_start_hi, ee_start_lo)
                        for j in range(self._extent_num_extents):
                            ee_offset = extent_offset + 12 + (j * 12)
                            block_num = (self._extent_block + j) & 0xFFFF
                            result[ee_offset : ee_offset + 4] = (
                                j * block_size
                            ).to_bytes(4, "little")
                            result[ee_offset + 4 : ee_offset + 6] = (
                                b"\x01\x00"  # ee_len = 1
                            )
                            result[ee_offset + 6 : ee_offset + 8] = b"\x00\x00"
                            result[ee_offset + 8 : ee_offset + 12] = block_num.to_bytes(
                                4, "little"
                            )
                    else:
                        # Depth 1: ExtentHeader with index + ExtentIndex entries
                        result[extent_offset : extent_offset + 2] = (
                            b"\x0a\xf3"  # eh_magic
                        )
                        result[extent_offset + 2 : extent_offset + 4] = (
                            b"\x01\x00"  # eh_entries = 1
                        )
                        result[extent_offset + 4 : extent_offset + 6] = (
                            b"\x01\x00"  # eh_max = 1
                        )
                        result[extent_offset + 6 : extent_offset + 8] = (
                            b"\x01\x00"  # eh_depth = 1
                        )
                        result[extent_offset + 8 : extent_offset + 12] = (
                            b"\x00\x00\x00\x00"
                        )

                        # ExtentIndex entry pointing to leaf block
                        ei_offset = extent_offset + 12
                        result[ei_offset : ei_offset + 4] = (
                            b"\x00\x00\x00\x00"  # ei_block = 0
                        )
                        leaf_block = (self._extent_block & 0xFF) + 10
                        result[ei_offset + 4 : ei_offset + 8] = leaf_block.to_bytes(
                            4, "little"
                        )
                        result[ei_offset + 8 : ei_offset + 10] = b"\x00\x00"
                        result[ei_offset + 10 : ei_offset + 12] = b"\x00\x00"

                # For htree directories, set i_block[0] to point to htree data block
                if i in htree_inodes:
                    htree_block = 20 + i
                    result[inode_offset + 0x28 : inode_offset + 0x2C] = (
                        htree_block.to_bytes(4, "little")
                    )

            # Extract the portion requested relative to inode table start
            start = offset - inode_table_start
            return bytes(result[start : start + size])

        # Check for htree data blocks (block 20+ based on inode)
        htree_start = block_size * 20
        htree_end = htree_start + (block_size * 4)
        if offset < htree_end and end >= htree_start and self._enable_htree:
            block_idx = (offset - htree_start) // block_size
            if block_idx < 4:
                result = bytearray(block_size)
                if block_idx == 0:
                    result[0:4] = b"\x01\x00\x00\x00"  # inode: 1 (.)
                    result[4:6] = b"\x10\x00"  # rec_len: 16
                    result[6:7] = b"\x01"  # name_len: 1
                    result[7:8] = bytes([0x02])  # file_type: DIR
                    result[8:12] = b".\x00\x00\x00"
                    result[12:16] = b"\x02\x00\x00\x00"  # inode: 2 (..)
                    result[16:18] = b"\x10\x00"  # rec_len: 16
                    result[18:19] = b"\x02"  # name_len: 2
                    result[19:20] = bytes([0x02])  # file_type: DIR
                    result[20:24] = b"..\x00\x00"
                    result[24:28] = b"\x00\x00\x00\x00"  # dx_root_info.reserved_zero
                    result[28:29] = bytes([self._htree_hash_version])  # hash_version
                    result[29:30] = b"\x08"  # info_length: 8
                    result[30:31] = bytes([self._htree_complexity])  # indirect_levels
                    result[31:32] = b"\x00"  # unused_flags
                    result[32:34] = (12 + self._htree_num_entries * 8).to_bytes(
                        2, "little"
                    )  # limit
                    result[34:36] = self._htree_num_entries.to_bytes(
                        2, "little"
                    )  # count
                    result[36:40] = b"\x00\x00\x00\x00"  # block

                    dx_entry_offset = 40
                    for j in range(self._htree_num_entries):
                        hash_val = (j * 0x1234567) & 0xFFFFFFFF
                        result[dx_entry_offset : dx_entry_offset + 4] = (
                            hash_val.to_bytes(4, "little")
                        )
                        result[dx_entry_offset + 4 : dx_entry_offset + 8] = (
                            20 + j
                        ).to_bytes(4, "little")
                        dx_entry_offset += 8

                start = (offset - htree_start) % block_size
                end_pos = min(block_size, start + size)
                return bytes(result[start:end_pos])

        # Check for extent leaf blocks (block 10+)
        extent_leaf_start = block_size * 10
        extent_leaf_end = extent_leaf_start + (block_size * 4)
        if (
            offset < extent_leaf_end
            and end >= extent_leaf_start
            and self._enable_extents
        ):
            block_idx = (offset - extent_leaf_start) // block_size
            if block_idx < self._extent_num_extents:
                result = bytearray(block_size)
                result[0:4] = (block_idx * block_size).to_bytes(4, "little")
                result[4:6] = b"\x01\x00"
                result[6:8] = b"\x00\x00"
                result[8:12] = ((self._extent_block + block_idx) & 0xFFFF).to_bytes(
                    4, "little"
                )
                start = (offset - extent_leaf_start) % block_size
                end_pos = min(block_size, start + size)
                return bytes(result[start:end_pos])

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


def TestOneInput(data: bytes) -> None:  # noqa: PLR0912
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

    try:
        if not isinstance(vol.inodes[EXT4_INO.ROOT], Directory):
            return

    except InodeError:
        return

    except OSError as e:
        if e.errno == errno.EINVAL:
            return

        if "Short read for" in str(e):
            return

        raise

    _ = vol.superblock
    for bd in vol.group_descriptors:
        _ = bd.bg_block_bitmap

    root = vol.root
    htree = root.htree
    if htree is not None:
        for _ in htree.entries:
            pass

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
