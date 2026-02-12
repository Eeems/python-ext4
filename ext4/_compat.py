import os
from typing import Protocol
from typing import runtime_checkable

# Added in python 3.12
try:
    from typing import override  # pyright: ignore[reportAssignmentType]

except ImportError:
    from typing import Callable
    from typing import Any

    def override(fn: Callable[..., Any]):  # pyright: ignore[reportExplicitAny]
        return fn


@runtime_checkable
class ReadableStream(Protocol):
    def read(self, size: int | None = -1, /) -> bytes: ...

    def tell(self) -> int: ...

    def seek(self, offset: int, whence: int = os.SEEK_SET, /) -> int: ...


@runtime_checkable
class PeekableStream(ReadableStream, Protocol):
    def peek(self, size: int = 0, /) -> bytes: ...


__all__ = ["override", "ReadableStream"]
