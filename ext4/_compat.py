import os
from typing import Protocol
from typing import runtime_checkable
from typing import TypeVar

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


T = TypeVar("T")
# Added in python 3.11
try:
    from typing import assert_type as _assert_type

except ImportError:

    def _assert_type(obj: T, T: Any, /) -> T:  # pyright: ignore[reportExplicitAny, reportAny]
        assert isinstance(obj, T), f"Object is: {type(obj)} not {T}"
        return obj


def assert_type(obj: T, T: Any, /) -> T:  # pyright: ignore[reportExplicitAny, reportAny]
    return _assert_type(obj, T)


__all__ = ["override", "ReadableStream", "PeekableStream", "assert_type"]
