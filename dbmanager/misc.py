from copy import deepcopy
import random

from dbmanager.types import Any, Iterable, DSA

ASCENDING_SQL = "ASC"
DESCENDING_SQL = "DESC"
CHARS_URLSAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890"
NUMS = "1234567890"

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
	
	def debug_values(self):
		"""
		Returns a deep copy of all queue items.
		Does not include futures.
		"""
		d: list[DSA] = []

		for v in self._queue:
			vv: dict[str, dict[str, str]] = (v.get("data") or {})

			d.append({
				"id": v["id"],
				"debug": vv.get("debug")
			})

		return d








def flatten(ls: Iterable[list[Any]]) -> list[Any]:
	return [vv for v in ls for vv in v]


def uid(l: int = 12):
	id_ = ""

	while (id_ == "" or id_[0] in NUMS):
		id_ = "".join(random.choice(CHARS_URLSAFE) for _ in range(l))
	
	return id_