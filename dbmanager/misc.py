from datetime import datetime
from typing import Any

ASCENDING_SQL = "ASC"
DESCENDING_SQL = "DESC"

class ENVStrucutre():
	host = "DB_HOST"
	port = "DB_PORT"
	user = "DB_USER"
	pswd = "DB_PASS"
	schm = "DB_SCHM"


class Errors():
	PKMissing = "You must define the primary key structure."
	TBNMissing = "You must define the table name."
	InvalidSortOrder = "sort_order must be {ASCENDING_SQL} or {DESCENDING_SQL} only."

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