from datetime import time as dtime, datetime
import requests
import dotenv
import queue
import json
import os

#from backend_collection.types import Any
from typing import Any, Callable

import logging
import logging.handlers
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG

STATS_FP = os.path.join("state", "stats.json")

LOG_FORMAT = "%(asctime)s - %(levelname)-8s IN %(threadName)-20s :  %(message)s"
LOG_DATE_FORMAT = "%d-%m-%y %H:%M:%S"

# = BUILTIN

# CRITICAL = 50
# ERROR = 40
# WARNING = 30
NOTICE = 25
PROGRESS = 21
# INFO = 20
# DEBUG = 10
STATS = 5

logging.addLevelName(NOTICE, "NOTICE")
logging.addLevelName(PROGRESS, "PROGRESS")
logging.addLevelName(STATS, "STATS")


class CustomLogger(logging.Logger):

	def notice(self, msg: str, *args: Any, **kwargs: Any):
		"""
		Log 'msg % args' with severity 'NOTICE'.

		To pass exception information, use the keyword argument exc_info with
		a true value, e.g.

		logger.info("Houston, we have a %s", "problem worth discussing", exc_info=1)
		"""
		if self.isEnabledFor(NOTICE):
			self._log(NOTICE, msg, args, **kwargs)
	
	def progress(self, msg: str, *args: Any, **kwargs: Any):
		"""
		Log 'msg % args' with severity 'PROGRESS'.

		To pass exception information, use the keyword argument exc_info with
		a true value, e.g.

		logger.info("Houston, we have a %s", "problem worth discussing", exc_info=1)
		"""
		if self.isEnabledFor(PROGRESS):
			self._log(PROGRESS, msg, args, **kwargs)
	
	def add_to_stats(self, msg: str, *args: Any, **kwargs: Any):
		"""
		Log 'msg' with severity 'STATS'.
		"""
		if self.isEnabledFor(STATS):
			self._log(STATS, msg, args, **kwargs)


logging.setLoggerClass(CustomLogger)



class CustomLogFMT(logging.Formatter):
	def __init__(self):
		super().__init__(LOG_FORMAT, LOG_DATE_FORMAT, "%")
	
	@property
	def prefix_length(self): return 56


LOG_FORMATTER = CustomLogFMT()




# FILE LOGGING
class CustomLogRF(logging.handlers.TimedRotatingFileHandler):
	def __init__(self, level: int | str = 0):
		super().__init__(
			filename = "collection.log", # FILENAME
			when = "midnight", # SWITCH ACTION, HAVE TO SAY THIS AS WELL.
			utc = True, # TIMEZONE
			atTime = dtime(23, 55), # TIME TO SWITCH.
			backupCount = 5 # N OF LOG FILES TO KEEP BEFORE DELETING
		)

		self.setFormatter(LOG_FORMATTER)
		self.setLevel(level)


	def namer(self, default_name: str) -> str: # type: ignore
		# EG DEFAULT_NAME: 'collection.log.2025-07-31'

		fn: str; ext: str; date: str
		fn, ext, date = default_name.split(".")

		return f"{fn}-{date}.{ext}"
	

	def emit(self, record: logging.LogRecord):
		if (record.levelno < self.level): return

		super().emit(record)
	


# CONSOLE (STREAM) LOGGING
class CustomLogST(logging.StreamHandler[Any]):
	def __init__(self, level: int | str = 0, stream: Any = None):
		super().__init__(stream)

		self.setFormatter(LOG_FORMATTER)
		self.setLevel(level)
	
	def emit(self, record: logging.LogRecord):
		if (record.levelno < self.level): return

		super().emit(record)


# DISCORD WEBHOOK LOGGING
class CustomLogDC(logging.Handler):
	def __init__(self, level: int | str = 0) -> None:
		super().__init__(level)

		self.setFormatter(LOG_FORMATTER)

		env = dotenv.dotenv_values()
		self._hook = env["DC_ONE_HOOK"]
		self._notif = env["DC_NOTIF_ROLE_ID"]

		self._last_dump = datetime.fromtimestamp(1)
		self._cooldown = 10 # SECONDs

		self._msges: list[str] = []

	def dump(self):
		assert self._hook

		n = datetime.now()

		if ((n - self._last_dump).total_seconds() < self._cooldown): return
		self._last_dump = n

		msg = ""
		n = 0
		for this in self._msges:
			if (len(msg) + len(this) > 2000): break
			msg += this + "\n"
			n += 1
		
		self._msges = self._msges[n+1:]

		requests.post(
			url = self._hook,
			data = {"content": msg}
		)


	def emit(self, record: logging.LogRecord):
		assert self._notif
		if (record.levelno < self.level): return

		msg = self.format(record)

		if (record.levelno >= CRITICAL):
			msg = f"{msg} <@&{self._notif}>"
		
		self._msges.append(msg)
		self.dump()



# STATS LOGGING
class CustomLogSS(logging.Handler):
	formatter = LOG_FORMATTER

	def __init__(self, level: int | str = 0, stats_fp: str = "") -> None:
		assert stats_fp

		super().__init__(level)

		self._fp = stats_fp

		with open(stats_fp, "r") as f:
			self._data: dict[str, Any] = json.load(f) or {}
		
		self._last_dump = datetime.fromtimestamp(1)
		self._cooldown = 5 # SECONDs


	def dump(self):
		n = datetime.now()
		
		if ((n - self._last_dump).total_seconds() < self._cooldown): return
		self._last_dump = n

		with open(self._fp, "w") as f:
			json.dump(self._data, f)


	def emit(self, record: logging.LogRecord):
		if (record.levelno != STATS): return

		m = record.message

		if (self._data.get(m) is None): self._data[m] = 0
		self._data[m] += 1

		self.dump()



log_queue = queue.Queue(-1) # type: ignore
queued_handler = logging.handlers.QueueHandler(log_queue) # type: ignore


_file_dump = CustomLogRF(DEBUG)
_console = CustomLogST(0)
_dc_hook = CustomLogDC(NOTICE)
_stats_log = CustomLogSS(STATS, STATS_FP)


__has_got = False


def get_logger():
	global __has_got

	if (__has_got):
		raise Exception("You may not call log_handler more than once.")

	__has_got = True

	logger: CustomLogger = logging.getLogger("gather-logger") # type: ignore
	logger.setLevel(STATS)

	logger.addHandler(_console)
	logger.addHandler(_file_dump)
	logger.addHandler(queued_handler)

	# RUN LOGS ASYNCHRONOUSLY WITH QueueListener
	log_listener = logging.handlers.QueueListener(
		log_queue, #type: ignore
		_dc_hook, _stats_log,
		respect_handler_level = True
	)

	log_listener.start()

	return logger