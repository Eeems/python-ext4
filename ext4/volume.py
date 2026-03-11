from __future__ import annotations

import io
import os
import errno

from uuid import UUID
from pathlib import PurePosixPath

from cachetools import cached
from cachetools import LRUCache

from ._compat import PeekableStream
from ._compat import assert_cast
from .enum import EXT4_INO
from .superblock import Superblock
from .inode import Inode
from .inode import Directory
from .blockdescriptor import BlockDescriptor


class InvalidStreamException(Exception):
    pass


class Inodes(object):
    def __init__(self, volume: "Volume"):
        self.volume: Volume = volume

    @property
    def superblock(self) -> Superblock:
        return self.volume.superblock

    @property
    def block_size(self) -> int:
        return self.volume.block_size

    @cached(cache={})
    def group(self, index: int) -> tuple[int, int]:
        s_inodes_per_group: int = assert_cast(self.superblock.s_inodes_per_group, int)  # pyright: ignore[reportAny]
        group_index = (index - 1) // s_inodes_per_group
        table_entry_index = (index - 1) % s_inodes_per_group
        return group_index, table_entry_index

    @cached(cache=LRUCache(maxsize=32))  # pyright: ignore[reportUnknownArgumentType]
    def offset(self, index: int) -> int:
        group_index, table_entry_index = self.group(index)
        table_offset = (
            self.volume.group_descriptors[group_index].bg_inode_table * self.block_size
        )
        s_inode_size: int = assert_cast(self.superblock.s_inode_size, int)  # pyright: ignore[reportAny]
        return table_offset + table_entry_index * s_inode_size

    @cached(cache=LRUCache(maxsize=32))  # pyright: ignore[reportUnknownArgumentType]
    def __getitem__(self, index: int):
        offset = self.offset(index)
        return Inode(self.volume, offset, index)


class Volume(object):
    def __init__(
        self,
        stream: PeekableStream,
        offset: int = 0,
        ignore_flags: bool = False,
        ignore_magic: bool = False,
        ignore_checksum: bool = False,
        ignore_attr_name_index: bool = False,
    ):
        errors: list[str] = []
        for name in ("read", "peek", "tell", "seek"):
            if not hasattr(stream, name):
                errors.append(f"{name} method missing")

            elif not callable(getattr(stream, name)):  # pyright: ignore[reportAny]
                errors.append(f"{name} is not a method")

        if errors:
            raise InvalidStreamException(", ".join(errors))

        self.stream: PeekableStream = stream
        self.offset: int = offset
        self.cursor: int = 0
        self.ignore_flags: bool = ignore_flags
        self.ignore_magic: bool = ignore_magic
        self.ignore_checksum: bool = ignore_checksum
        self.ignore_attr_name_index: bool = ignore_attr_name_index
        self.superblock: Superblock = Superblock(self)
        self.superblock.verify()
        self.group_descriptors: list[BlockDescriptor] = []
        block_size = self.block_size
        table_offset = (self.superblock.offset // block_size + 1) * block_size
        s_inodes_count: int = assert_cast(self.superblock.s_inodes_count, int)  # pyright: ignore[reportAny]
        s_inodes_per_group: int = assert_cast(self.superblock.s_inodes_per_group, int)  # pyright: ignore[reportAny]
        for index in range(0, s_inodes_count // s_inodes_per_group):
            descriptor = BlockDescriptor(
                self,
                table_offset + (index * self.superblock.desc_size),
                index,
            )
            descriptor.verify()
            self.group_descriptors.insert(index, descriptor)

        self.inodes: Inodes = Inodes(self)

    def __len__(self):
        _ = self.stream.seek(0, io.SEEK_END)
        return self.stream.tell() - self.offset

    @property
    def bad_blocks(self):
        return self.inodes[EXT4_INO.BAD]

    @property
    def root(self):
        return self.inodes[EXT4_INO.ROOT]

    @property
    def user_quota(self):
        return self.inodes[EXT4_INO.USR_QUOTA]

    @property
    def group_quota(self):
        return self.inodes[EXT4_INO.GRP_QUOTA]

    @property
    def boot_loader(self):
        return self.inodes[EXT4_INO.BOOT_LOADER]

    @property
    def undelete_directory(self):
        return self.inodes[EXT4_INO.UNDEL_DIR]

    @property
    def journal(self):
        return self.inodes[EXT4_INO.JOURNAL]

    @property
    def has_hi(self) -> int:
        return self.superblock.has_hi

    @property
    def uuid(self):
        s_uuid: bytes = assert_cast(bytes(self.superblock.s_uuid), bytes)  # pyright: ignore[reportAny]
        return UUID(bytes=s_uuid)

    @property
    def seed(self):
        return self.superblock.seed

    @property
    def block_size(self) -> int:
        s_log_block_size: int = assert_cast(self.superblock.s_log_block_size, int)  # pyright: ignore[reportAny]
        return int(
            2
            ** (  # pyright: ignore[reportAny]
                10 + s_log_block_size
            )
        )

    def seek(self, offset: int, mode: int = io.SEEK_SET) -> int:
        if mode == io.SEEK_SET:
            seek = offset

        elif mode == io.SEEK_CUR:
            seek = self.cursor + offset

        elif mode == io.SEEK_END:
            seek = len(self) + offset

        else:
            raise NotImplementedError(f"Seek mode {mode} not implemented")

        if seek < 0 or seek > len(self):
            raise OSError(errno.EINVAL, os.strerror(errno.EINVAL))

        self.cursor = seek
        return self.cursor

    def read(self, size: int) -> bytes:
        _ = self.stream.seek(self.offset + self.cursor)
        data = self.stream.read(size)
        self.cursor += len(data)
        return data

    def peek(self, size: int) -> bytes:
        _ = self.stream.seek(self.offset + self.cursor)
        return self.stream.peek(size)

    def tell(self) -> int:
        return self.cursor

    def block_read(self, index: int, count: int = 1):
        assert index >= 0
        assert count > 0
        block_size = self.block_size  # Only calculate once
        _ = self.seek(index * block_size)
        return self.read(count * block_size)

    @staticmethod
    def path_tuple(path: str | bytes) -> tuple[bytes, ...]:
        if isinstance(path, bytes):
            path = path.decode("utf-8")

        return tuple(x.encode("utf-8") for x in PurePosixPath(path).parts[1:])

    @cached(cache=LRUCache(maxsize=32))  # pyright: ignore[reportUnknownArgumentType]
    def inode_at(self, path: str | bytes) -> Inode:
        paths = list(self.path_tuple(path))
        cwd = self.root
        if not paths:
            return cwd

        while paths:
            if not isinstance(cwd, Directory):
                raise OSError(errno.ENOTDIR, os.strerror(errno.ENOTDIR))

            name = paths.pop(0)
            inode = None
            for dirent, _ in cwd.opendir():
                if dirent.name_bytes == name:
                    inode = self.inodes[dirent.inode]
                    break

            if inode is None:
                raise FileNotFoundError(path)

            cwd = inode

        return cwd
