from concurrent.futures import ThreadPoolExecutor as TPE
from asyncio import get_running_loop
from functools import partial
import random

from dbmanager.types import Any, Iterable, DSA, Callable

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
	
	def work_ahead(self, n: int):
		if (len(self._queue) <= n): return None

		return self._queue[n]

	
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

	def remove_worked_ahead(self, n: int):
		try: self._queue.pop(n)
		except: return
	
	def get_debug_from_queue_item(self, item: DSA):
		d = item.get("data")
		if (not d): return

		pl = d.get("payload")
		if (not pl): return

		return pl.get("debug")
	
	def debug_values(self):
		"""
		Returns a deep copy of all queue items.
		Does not include futures.
		"""
		d: list[DSA] = []

		for v in self._queue:
			vv = self.get_debug_from_queue_item(v)

			d.append({ "id": v["id"], "debug": vv })

		return d




def flatten(ls: Iterable[list[Any]]) -> list[Any]:
	return [vv for v in ls for vv in v]


def uid(l: int = 12):
	id_ = ""

	while (id_ == "" or id_[0] in NUMS):
		id_ = "".join(random.choice(CHARS_URLSAFE) for _ in range(l))
	
	return id_


def async_executor(func: Callable[[Any], Any], *args: Any, **kwargs: Any):
	loop = get_running_loop()

	p = partial(func, *args, **kwargs)

	return loop.run_in_executor(None, p)