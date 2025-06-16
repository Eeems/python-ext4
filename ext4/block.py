import io
import errno

from ._compat import override


class BlockIOBlocks(object):
    def __init__(self, blockio):
        self.blockio = blockio

    @property
    def block_size(self):
        return self.blockio.block_size

    @property
    def volume(self):
        return self.blockio.inode.volume

    @property
    def ee_start(self):
        return self.blockio.ee_start

    @property
    def ee_block(self):
        return self.blockio.ee_block

    @property
    def ee_len(self):
        return self.blockio.ee_len

    def __contains__(self, ee_block):
        for extent in self.blockio.extents:
            if ee_block in extent.blocks:
                return True

        return False

    def __getitem__(self, ee_block):
        for extent in self.blockio.extents:
            if ee_block in extent.blocks:
                return extent.blocks[ee_block]

        return bytearray(self.block_size)


class BlockIO(io.RawIOBase):
    def __init__(self, inode):
        super().__init__()
        self.inode = inode
        self.cursor: int = 0
        self.blocks: BlockIOBlocks = BlockIOBlocks(self)

    def __len__(self):
        return self.inode.i_size

    @property
    def extents(self):
        return self.inode.extents

    @property
    def block_size(self) -> int:
        return self.inode.volume.block_size

    @override
    def readable(self) -> bool:
        return True

    @override
    def seekable(self) -> bool:
        return True

    @override
    def seek(self, offset: int, mode: int = io.SEEK_SET) -> int:
        if mode == io.SEEK_CUR:
            offset += self.cursor

        elif mode == io.SEEK_END:
            offset += len(self)

        elif mode != io.SEEK_SET:
            raise NotImplementedError()

        if offset < 0:
            raise OSError(errno.EINVAL, "Invalid argument")

        self.cursor = offset
        return offset

    @override
    def tell(self) -> int:
        return self.cursor

    @override
    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self) - self.cursor

        data = self.peek(size)
        self.cursor += len(data)
        if size < len(data):
            raise OSError(errno.EIO, "Unexpected EOF")

        return data

    def peek(self, size: int = 0) -> bytes:
        if self.cursor >= len(self):
            return b""

        start_index = self.cursor // self.block_size
        end_index = (self.cursor + size - 1) // self.block_size
        start_offset = self.cursor % self.block_size
        data = b""
        for i in range(start_index, end_index + 1):
            block = self.blocks[i]
            if block is None:
                block = bytearray(self.block_size)

            if i == start_index:
                block = block[start_offset:]

            data += block

        data = data[:size]
        return data
