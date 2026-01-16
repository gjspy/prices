from typing import Any, Union, Callable, Sequence


Number = Union[float, int]
DSA = dict[str, Any] # most generic dict
DAA = dict[Any, Any]

# psuedonyms used for readability
Result = DSA

SDG_Key = Sequence[str | int | DAA | Callable[[Any], bool]]