from datetime import time as dtime
from threading import Thread
from typing import Any, Callable
import re

import logging
import logging.handlers


COLLECT_START_TIME = "02:00"










LOG_FORMAT = "%(asctime)s - %(levelname)-8s IN %(threadName)-20s :  %(message)s"
LOG_DATE_FORMAT = "%d-%m-%y %H:%M:%S"

LOG_FORMATTER = logging.Formatter(
	fmt = LOG_FORMAT,
	datefmt = LOG_DATE_FORMAT)

class CustomLogFH(logging.handlers.TimedRotatingFileHandler):
	def __init__(self):
		super().__init__(
			filename = "collection.log", # FILENAME
			when = "midnight", # SWITCH ACTION, HAVE TO SAY THIS AS WELL.
			utc = True, # TIMEZONE
			atTime = dtime(23, 55), # TIME TO SWITCH.
			backupCount = 14 # N OF LOG FILES TO KEEP BEFORE DELETING
		)

		self.setFormatter(LOG_FORMATTER)


	def namer(self, default_name: str) -> str: # type: ignore
		# EG DEFAULT_NAME: 'collection.log.2025-07-31'

		fn: str; ext: str; date: str
		fn, ext, date = default_name.split(".")

		return f"{fn}-{date}.{ext}"
	

class CustomLogSH(logging.StreamHandler): # type: ignore
	formatter = LOG_FORMATTER




def safe_deepget(
		data: dict[Any, Any], path: list[Any],
		default_value: Any = None) -> Any:
	
	for key in path:
		try: data = data[key] # NOT .get(), NEED LIST[index] TOO.
		except: return default_value
	
	if (not data): return default_value
	return data


def int_safe(value: Any) -> int | None:
	try: return int(value)
	except: return None






def convert_str_to_pence(value: str) -> int:
	if ("£" in value): return int(float(value.replace("£", "")) * 100)
	if ("p" in value): return int(value.replace("p", ""))


def split_packsize(
		value: str | None = None, size: str | None = None,
		unit: str | None = None) -> tuple[float, str]:
	"""
	Provide one of (value) or (size, unit)
	Split packsize into size and regular unit.
	Eg: 2Kg = (2, "kg")
	200ml = (0.2, "l")
	"""
	if (value):
		value = value.upper()

		match = re.match(r"([\d\.]+)([A-z]+)", value)
		if (not match): return (-1, "")

		size, unit = match.groups()
	
	if (not size or not unit): return (-1, "")

	if ("KG" in unit): return (float(size.replace("KG", "")), "kg")
	if ("ML" in unit): return (float(size.replace("ML", "")) / 1000, "l")

	if ("G" in unit): return (float(size.replace("G", "")) / 1000, "kg")
	if ("L" in unit): return (float(size.replace("L","")), "l") # ASDA: CAN BE LT (MANUAL STAFF INPUT OF DATA)

	return (-1, "")



class TaskThread(Thread):
	"""
	Subclassed threading.Thread object, used for running a routine
	asynchronously, and returning a response.
	
	Use this exactly like you would a normal Thread, just call .join()
	asynchronously!
	"""
	def __init__(self, *args: Any, **kwargs: Any):
		self._target: Callable[..., Any]
		self._args: list[Any]
		self._kwargs: dict[str, Any]

		super().__init__(*args, **kwargs)

		self.value: Any = None
		self.complete: bool = False
		self.error: Exception | None = None

	
	def run(self):
		"""
		Called after Thread().start().

		start() actually starts a thread, run() runs the code in it.
		"""

		if (self._target == None):
			self.complete = True
			return
		
		try:
			self.value = self._target(*self._args, **self._kwargs)
		
		except Exception as err:
			self.error = err
		
		self.complete = True
	
	
