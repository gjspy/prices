from typing import Any, Union, Callable, Sequence, Optional


Number = Union[float, int]
DSA = dict[str, Any] # most generic dict
DAA = dict[Any, Any]
DSS = dict[str, str]

# psuedonyms used for readability
Result = DSA

SDG_Key = Sequence[str | int | DAA | Callable[[Any], bool]]