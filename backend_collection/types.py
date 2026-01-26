from typing import Any, Union, Callable, Sequence, Optional


type Number = Union[float, int]
type DSA = dict[str, Any] # most generic dict
type DAA = dict[Any, Any]
type DSS = dict[str, str]
type DSI = dict[str, int]

# psuedonyms used for readability
type Result = DSA

type SDG_Key = Sequence[str | int | DAA | Callable[[Any], bool]]