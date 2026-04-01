import os
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

# Added in python 3.12
try:
    from typing import override  # pyright: ignore[reportAssignmentType]

except ImportError:
    from collections.abc import Callable

    def override(fn: Callable[..., Any]):  # pyright: ignore[reportExplicitAny]  # noqa: ANN202
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


def assert_cast(obj: Any, t: type[T], /) -> T:  # pyright: ignore[reportExplicitAny, reportAny]
    assert isinstance(obj, t), f"Object is: {type(obj)} not {t}"  # pyright: ignore[reportAny]
    return obj


__all__ = ["override", "ReadableStream", "PeekableStream", "assert_cast"]
