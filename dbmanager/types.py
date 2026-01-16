from typing import Any, TypeVar, ParamSpec

# TypeVar DEFINES PLACEHOLDER TYPES
# EG def foo(bar: X) -> X: DEFINES A FUNC WHICH RETURNS SAME TYPE AS PARAM
O = TypeVar("O") # O FOR OUTPUT

# ParamSpec DEFINES TYPES FOR *args AND **kwargs
P = ParamSpec("P") # P FOR PARAMS

T = TypeVar("T")

QP = tuple[Any, ...] # QP FOR QUERY PARAMS
DSA = dict[str, Any] # DSA FOR DICT: STRING, ANY
DST = dict[str, type]
DSS = dict[str, str]