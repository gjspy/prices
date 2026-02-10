from datetime import time as dtime, datetime
from copy import deepcopy
import threading
import requests
import dotenv
import atexit
import queue
import time
import json
import os

from typing import Any, Optional

import logging
import logging.handlers
from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG # type: ignore

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
	def __init__(self, name: str, level: int | str = 0):
		super().__init__(
			filename = f"{name}.log", # FILENAME
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





class CooldownBasedLogger(logging.Handler):
	def __init__(self, level: int | str = 0):
		super().__init__(level)
		self.setFormatter(LOG_FORMATTER)

		self._cooldown = 10
		self._last_dump = 0
		
		self._msges: list[str] = []
		self._lock = threading.Lock()
		self._timer: Optional[threading.Timer] = None
	
	def get_msg_from(self, record: logging.LogRecord) -> Optional[str]:
		""" FOR SUBCLASSES! """

		return self.format(record)

	def emit(self, record: logging.LogRecord):
		if (record.levelno < self.level): return

		msg = self.get_msg_from(record)
		if (msg is None): return

		with self._lock:
			self._msges.append(msg)

			if (self._timer is None): self._schedule_dump()
	
	def close(self):
		if (self._timer): self._timer.cancel()
		self._dump()
		super().close()


	def _schedule_dump(self):
		now = time.time()
		elapsed = now - self._last_dump
		delay = max(1, self._cooldown - elapsed) # ALWAYS WAIT ATLEAST 1s

		self._timer = threading.Timer(delay, self._dump)
		self._timer.daemon = True
		self._timer.start()


	def _dump(self):
		with self._lock:
			self._last_dump = time.time()
			self._timer = None

			if (not self._msges): return

			msgs = self._msges
			self._msges = []
		
		self.dump_action(msgs)

	
	def dump_action(self, msgs: list[str]) -> None:
		raise NotImplementedError

		


# DISCORD WEBHOOK LOGGING
class CustomLogDC(CooldownBasedLogger):
	def __init__(self, level: int | str = 0):
		super().__init__(level)

		env = dotenv.dotenv_values()
		self._hook = env["DC_ONE_HOOK"]
		self._notif = env["DC_NOTIF_ROLE_ID"]

		self._cooldown = 10
	
	def get_msg_from(self, record: logging.LogRecord):
		msg = self.format(record)

		if (record.levelno >= CRITICAL):
			msg = f"{msg} <@&{self._notif}>"
		
		return msg
	
	def dump_action(self, msgs: list[str]):
		assert self._hook

		msg = msgs.pop(0)[:2000]

		for this in msgs:
			if (len(msg) + len(this) > 2000): break
			msg += "\n" + this

		requests.post(
			url = self._hook,
			data = {"content": msg}
		)


# STATS LOGGING
class CustomLogSS(CooldownBasedLogger):
	def __init__(self, stats_fp: str, level: int | str = 0, ):
		super().__init__(level)

		self._cooldown = 5

		self._fp = stats_fp

		with open(stats_fp, "r") as f:
			self._data: dict[str, Any] = json.load(f) or {}
	
	def get_msg_from(self, record: logging.LogRecord):
		if (record.levelno != STATS): return None

		return record.message

	def dump_action(self, msgs: list[str]):
		for m in msgs:
			if (self._data.get(m) is None): self._data[m] = 0
			self._data[m] += 1
		
		with open(self._fp, "w") as f:
			json.dump(self._data, f)



__has_got = False


def get_logger(name: str, stats_fp: str):
	global __has_got

	if (__has_got):
		raise Exception("You may not call log_handler more than once.")

	__has_got = True


	log_queue: queue.Queue[Any] = queue.Queue(-1)
	queued_handler = logging.handlers.QueueHandler(log_queue)


	_file_dump = CustomLogRF(name, DEBUG)
	_console = CustomLogST(0)
	_dc_hook = CustomLogDC(NOTICE)
	_stats_log = CustomLogSS(stats_fp, STATS)

	logger: CustomLogger = logging.getLogger(name) # type: ignore
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