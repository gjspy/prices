from datetime import datetime, timedelta
from threading import Thread
from logging import Logger

from asyncio import Future, AbstractEventLoop
import asyncio

import time

import dbmanager.engine as engine
import dbmanager.misc as misc

from dbmanager.types import Any, DSA, Optional, DSI

AVG_WORK_SPEED = 1 # SECONDS
RECONNECTION_WAIT = 5

DUMP_INTERVAL = 30 # SECONDS
NOTICE_INTERVAL = 60 * 60 # SECONDS
WAIT_BEFORE_FIRST_NOTICE = 5 * 60 # SECONDS

class DBThread(Thread):
	"""## Subclassed threading.Thread only for DB process. ##"""

	def __init__(
			self, logger: Logger, engine_: engine.Database,
			event_loop: AbstractEventLoop, state_fp: str):
		"""
		Args
		--------
		logger: logging.Logger
			Output stream for DBThread to use.
		
		engine_: DBManager.engine.Database
			Database for using .execute()
		
		event_loop: asyncio.AbstractEventLoop
			Required, so you can receive results of queries.
		"""
		super().__init__(
			name = "DBThread",
			daemon = True
		)
		
		self._logger = logger
		self._staged_queue = misc.Queue()
		self._engine = engine_
		self._active: bool = False
		self._event_loop = event_loop
		
		self._state_fp = state_fp

	
	@property
	def logger(self): return self._logger

	@property
	def log_newline(self) -> str:
		return "\n" + (" " * self._logger.handlers[0].formatter.prefix_length) # type: ignore

	@logger.setter
	def set_logger(self, new: Logger): self._logger = new


	def dump(self):
		data = ""

		for i in self._staged_queue.debug_values():
			ds = self.get_debug_str(i)

			data += f"#{i.get("id")} {ds}\n"
		
		try:
			with open(self._state_fp, "w") as f:
				f.write(data)

		except Exception as e:
			self.logger.error(f"COULD NOT DUMP QUEUE STATE {e}")


	def notice(self):
		data: DSI = {}
		tot = 0
		max_id = 0

		for i in self._staged_queue.debug_values():
			tot += 1

			id_ = i.get("id") or 0
			if (id_ > max_id): max_id = id_

			s = self.get_debug_str(i)

			if (not data.get(s)): data[s] = 0
			data[s] += 1
		
		v = ",".join(f"{c}x {v}" for v,c in data.items())
		
		self.logger.notice( # type: ignore
			f"{tot} TOTAL ITEMS IN QUEUE NOW, {max_id} MAX ID.\n" + v )
		






	@property
	def event_loop(self): return self._event_loop

	@event_loop.setter
	def set_event_loop(self, new: AbstractEventLoop):
		self._event_loop = new


	def _get_debug_str(self, payload_done: DSA) -> str:		
		debug_params = payload_done.get("debug")
		if (not debug_params): return ""

		query_type: str; params: list[str] | str
		query_type, params = debug_params

		counts_str = ""

		if (type(params) == str): counts_str = params
		else:
			counts = { v: params.count(v) for v in set(params) }
			counts_parts = [ f"{c}x {k}" for k,c in counts.items() ]
			counts_str = ", ".join(counts_parts)

		return f"{query_type} {counts_str}"
	
	def get_debug_str(self, payload_done: DSA) -> str:
		"""
		Returns string describing a query or request made to DB.

		Example:
		--------
		"update 1x User"\n
		"insert 2x Order, 1x User"\n
		"select from Users"
		"""

		if (payload_done is None): # type: ignore
			return "no payload"

		try: return self._get_debug_str(payload_done)
		except Exception as err: return f"couldn't get debug str {err}"


	def __execute_item(self, next_data: DSA) -> tuple[bool, str, DSA]:
		
		payload: Optional[DSA] = next_data.get("payload")
		if (not payload): return (False, "no payload", {})

		result: DSA = {}

		try: result = self._engine.execute_payload(payload)
		except:
			# HAS ALREADY BEEN CAUGHT, LOGGED & RETHROWN
			# NO NEED TO LOG AGAIN.
			return (False, "error occurred", {})

		debug_str = self.get_debug_str(payload)
		return (True, debug_str, result)
		


	def _main_process(self) -> bool:
		"""
		Main process of DB thread.
		Gets next db task, executes, logs success.
		"""

		# DEBUGGING
		ql = self._staged_queue.get_length()
		active = self._active

		if ((ql != 0 and not active) or (ql == 0 and active)):
			d = "worked" if active else "did not work"
			self._logger.info(f"{ql} waiting, {d} last cycle")

		next_item: Optional[DSA] = self._staged_queue.get_next()
		if (not next_item): return False # SET NOT ACTIVE
		
		data: Optional[DSA] = next_item.get("data")

		if (not data):
			self._logger.warning(
				f"Ignoring task {next_item.get("id")}, no data.")
			self._staged_queue.remove_first()

			return True # ACTIVE
		
		future: Optional[Future[Any]] = data.get("future")

		success, message, result = self.__execute_item(data)

		success_str: str = ""
		if (success): success_str = f", {len(result)} results returned."

		if (future): self._event_loop.call_soon_threadsafe(
			future.set_result, result)
			
		self._staged_queue.remove_first()

		new_l = self._staged_queue.get_length()

		self._logger.info(
			f"Completed #{next_item.get("id")} ({message}){success_str} "
			f"Success: {success}. Todo: {new_l}")
		
		return True # ACTIVE


	def create_future(self) -> asyncio.Future[Any]:
		return self.event_loop.create_future()
		

	def stage(self, payload: DSA, future: Optional[Future[Any]] = None):
		"""
		Add SQL payloads to queue. You may use this method.

		If you want to receive a response, you should use the `query` method.

		Args
		--------
		payload: dict[str, Any]
			Query data generated by any method of `Table` (`Table.select`, ...)
		
		future: asyncio.Future
			Manually created `future` awaitable for the response of the query.
			This behaviour is incorporated into the `query` method.
		"""

		self._staged_queue.append({
			"payload": payload,
			"future": future
		})


	async def query(self, query: DSA):
		"""
		Wrapper for `self.stage` which contains `asyncio.Future` logic.

		This should be used to wait for a response, else use `stage` to
		declare a query and "walk away" - Maurice Moss style.
		"""
		future = self.create_future()

		self.stage(query, future)
		response: DSA = await future

		return response
	
	

	# METHOD CALLED AFTER t.start()!
	def run(self):
		"""
		Must be called at most ONCE.
		
		This is overwriting the default run() method of threading.Thread
		"""
		assert self._engine

		self._logger.debug("DB Queue starting.")

		last_dump = datetime.fromtimestamp(0)
		last_notice = datetime.now() - timedelta(
			seconds = NOTICE_INTERVAL - WAIT_BEFORE_FIRST_NOTICE)

		while True:
			if (not self._active): time.sleep(AVG_WORK_SPEED) # PREVENT RAPID-FIRE

			try:
				if (not self._engine.is_connected): self._engine.connect()
				self._active = self._main_process() # PROCESS NEXT QUEUE ITEM

				n = datetime.now()

				if ((n - last_dump).total_seconds() > DUMP_INTERVAL):
					self.dump()
					last_dump = n
				
				if ((n - last_notice).total_seconds() > NOTICE_INTERVAL):
					self.notice()
					last_notice = n

			
			except Exception as e:
				self._logger.exception(f"MAIN PROCESS STOPPED, {e}")
				time.sleep(RECONNECTION_WAIT)