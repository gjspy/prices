from threading import Thread
from typing import Any
from logging import Logger

from asyncio import Future, AbstractEventLoop
import asyncio

import time

import dbmanager.engine as engine
import dbmanager.misc as misc

from dbmanager.types import DSA

AVG_WORK_SPEED = 1 # SECONDS
FAST_WORK_SPEED = 0.1 # SECONDS
RECONNECTION_WAIT = 5

MAX_TIME_IDLE = 30

class DBThread(Thread):
	"""## Subclassed threading.Thread only for DB process. ##"""

	def __init__(
			self, logger: Logger, engine_: engine.Database,
			event_loop: AbstractEventLoop | None):
		"""
		Args
		--------
		logger: logging.Logger
			Output stream for DBThread to use.
		
		engine_: DBManager.engine.Database
			Database for using .execute()
		
		event_loop: asyncio.AbstractEventLoop
			Optional, only required if expect to receive results of queries.
		"""
		super().__init__(
			name = "DBThread",
			daemon = True
		)

		self._logger: Logger
		self._staged_queue: misc.Queue
		self._engine: engine.Database
		self._active: bool
		self._event_loop = AbstractEventLoop | None
		
		self._logger = logger
		self._staged_queue = misc.Queue()
		self._engine = engine_
		self._active = False
		self._event_loop = event_loop

	

	@property
	def logger(self): return self._logger

	@logger.setter
	def set_logger(self, new: Logger): self._logger = new


	@property
	def event_loop(self): return self._event_loop

	@event_loop.setter
	def set_event_loop(self, new: AbstractEventLoop):
		self._event_loop = new
	


	def _get_debug_str(self,  payload_done: DSA) -> str:
		debug_params: tuple[str, list[str] | str] | None = \
			payload_done.get("debug")
		
		if (not debug_params): return ""

		query_type: str
		params: list[str] | str
		query_type, params = debug_params

		counts_str: str = ""

		if (type(params) == str): counts_str = params
		else:
			counts: dict[str, int] = { v: params.count(v) for v in set(params) }
			counts_parts: list[str] = [ f"{c}x {k}" for k,c in counts.items() ]
			counts_str: str = ", ".join(counts_parts)

		return f"{query_type} {counts_str}"
	
	def get_debug_str(self, payload_done: DSA) -> str:
		"""
		Returns string describing query/request made to DB.

		Example:
		--------
		"update 1x User"\n
		"insert 2x Order, 1x User"\n
		"select from Users"
		"""

		try:
			return self._get_debug_str(payload_done)
		
		except Exception as err:
			return f"couldn't get debug str {err}"


	def execute_item(self, next_data: DSA) -> tuple[bool, str, list[Any]]:
		payload: DSA | None = next_data.get("payload")
		if (not payload):
			return (False, "no payload", [])

		result: list[Any] = []

		try: result = self._engine.execute_payload(payload)
		except:
			# HAS ALREADY BEEN CAUGHT, LOGGED & RETHROWN
			# NO NEED TO LOG AGAIN.
			return (False, "error occurred", [])
		
		debug_str = self.get_debug_str(payload)
		
		return (True, debug_str, result)
		





	def _main_process(self) -> bool:
		""" Main process of DB thread. gets next db task, executes, logs success."""

		# DEBUGGING
		ql: int = self._staged_queue.get_length()
		active: bool = self._active

		if ((ql != 0 and not active) or (ql == 0 and active)):
			self._logger.info(f"db queue {ql}, worked last cycle = {active}")

		next_item: DSA | None = self._staged_queue.get_next()
		if (not next_item):
			return False # IS NOT ACTIVE
		
		data: DSA | None = next_item.get("data")
		if (not data):
			self._logger.warning(
				f"db queue ignoring task {next_item.get("id")}, no data.")
			self._staged_queue.remove_first()

			return False
		
		future: Future[Any] | None = data.get("future")

		success: bool
		message: str
		result: list[Any]
		success, message, result = self.execute_item(data)

		success_str: str = ""
		if (success): success_str = f" {len(result)} results returned."

		if (future):
			asyncio.run_coroutine_threadsafe(
				future.set_result(result), self.event_loop) # type: ignore
			
		self._staged_queue.remove_first()

		self._logger.info(
			f"db completed task {next_item.get("id")} ({message}) "
			f"with {ql - 1} left. success: {success}{success_str}")
		
		return True





		

	def stage(self, payload: DSA, future: asyncio.Future[Any] | None = None):
		""" Add SQL payloads to queue. """

		self._staged_queue.append({
			"payload": payload,
			"future": future
		})
	
	

	# METHOD CALLED AFTER t.start()!
	def run(self):
		assert self._engine

		self._logger.debug("DBThread starting.")

		# EXTERIOR LOOP TO ENSURE DBTHREAD STAYS ACTIVE
		while True:
			time.sleep(FAST_WORK_SPEED if self._active else AVG_WORK_SPEED) # PREVENT RAPID-FIRE

			try:
				if (not self._engine.is_connected):
					success: bool | None = self._engine.connect()
				
					if (not success):
						self._logger.warning("Attempted reconnection in DBThread failed, passing..")
						time.sleep(RECONNECTION_WAIT)
						continue

				self._active = self._main_process() # LAUNCH MAIN PROCESS
			
			except:
				self._logger.exception("main_process THREW EXCEPTION")
				time.sleep(RECONNECTION_WAIT)