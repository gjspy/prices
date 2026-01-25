from datetime import datetime
from typing import Any, Iterable
import random

from dbmanager.types import DSA

ASCENDING_SQL = "ASC"
DESCENDING_SQL = "DESC"
CHARS_URLSAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890"
NUMS = "1234567890"

class Errors():
	PKMissing = "You must define the primary key structure."
	PKNoPy = "PK is missing a python property."
	TBNMissing = "You must define the table name."
	InvalidSortOrder = "sort_order must be {ASCENDING_SQL} or {DESCENDING_SQL} only."
	NotAI = "Must be an autoincrement value."

class Queue():
	def __init__(self):
		self._queue: list[Any]
		self._id_counter: int

		self._queue = []
		self._id_counter = 0

	
	def get_next(self) -> Any:
		if (len(self._queue) == 0): return None

		return self._queue[0]
	
	def get_length(self) -> int:
		return len(self._queue)
	
	def append(self, item: Any) -> int:
		this_id = self._id_counter

		self._queue.append({
			"id": this_id,
			"data": item
		})

		self._id_counter += 1

		return this_id
	
	def remove_first(self) -> Any:
		try: self._queue.pop(0)
		except: return None


class ExecutionException(Exception):
	def __init__(self, original: Exception, is_fatal: bool):
		self.original = original
		self.is_fatal = is_fatal


def get_placeholder(field_type: type) -> Any:
	"""
	## Gets placeholder value of type. ##

	First attempts running field_type().\n
	Works for str -> ""\n
	Works for int -> 0

	If datetime, returns .fromtimestamp(0)
	"""
	try: return field_type()
	except: pass

	if (field_type == datetime):
		return datetime.fromtimestamp(0)
	
	raise TypeError(f"get_placeholder: What is this? {field_type}")


def get_k_from_v(d: DSA, value: Any):
	for k,v in d.items():
		if (v == value): return k


def flatten(ls: Iterable[list[Any]]) -> list[Any]:
	return [vv for v in ls for vv in v]


def uid(l: int = 12):
	id_ = ""

	while (id_ == "" or id_[0] in NUMS):
		id_ = "".join(random.choice(CHARS_URLSAFE) for _ in range(l))
	
	return id_