from typing import Generic, TypeVar, Type, Any, Optional, Literal, Union, overload, Self, Callable

T = TypeVar("T")

DSA = dict[str, Any]
DSS = dict[str, str]
QueryParams = tuple[Any, ...]