try:
    from typing import override

except ImportError:
    from typing import Callable
    from typing import Any

    def override(fn: Callable[..., Any]):
        return fn


__all__ = ["override"]
