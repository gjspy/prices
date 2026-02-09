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
		self._urgent_queue = misc.Queue() # like a fast track. serve these first, always
		self._engine = engine_
		self._active: bool = False
		self._event_loop = event_loop
		
		self._state_fp = state_fp

		self._locked_tables: dict[engine.Table[Any], int] = {}
		self._lock_data: dict[int, engine.Table[Any]] = {}
		self._locks_created = 0

	
	@property
	def logger(self): return self._logger

	@property
	def log_newline(self) -> str:
		return "\n" + (" " * self._logger.handlers[0].formatter.prefix_length) # type: ignore

	@logger.setter
	def set_logger(self, new: Logger): self._logger = new

	def get_queue_length(self):
		return self._staged_queue.get_length()


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
		if (payload.get("no_sql") == True): return (True, "no SQL", {})

		result: DSA = {}

		try: result = self._engine.execute_payload(payload)
		except:
			# HAS ALREADY BEEN CAUGHT, LOGGED & RETHROWN
			# NO NEED TO LOG AGAIN.
			return (False, "error occurred", {})

		debug_str = self.get_debug_str(payload)
		return (True, debug_str, result)
	


	def _check_workable(self, item: Optional[DSA]):
		if (item is None): return True # STOP WORKING, WILL STOP ITSELF.
		
		data: Optional[DSA] = item.get("data")

		if (not data): return True # WORKABLE, JUST GETS REMOVED.

		lock_id = data.get("lock_id")
		create_lock_on = data.get("create_lock_on")
		if (lock_id is None and not create_lock_on):
			return True # NO RESTRICTION

		if (create_lock_on):
			current_lock_id: Optional[int] = self._locked_tables.get(create_lock_on)

			if (current_lock_id is None): return True # NOT LOCKED YET. MAY DO NOW.
			return False # WANTS TO CREATE LOCK, MUST WAIT.

		payload = data.get("payload")
		if (not payload): return True # WILL BE IGNORED LATER

		tables_involved = payload.get("tables_involved")
		if (not tables_involved): return True # ??? OKAY

		for table in tables_involved:
			table_locked_to_id = self._locked_tables.get(table)
			if (table_locked_to_id is None): continue

			if (table_locked_to_id == lock_id): return True # IS THIS LOCK.
			return False # NOT THIS LOCK. REFUSE
		
		return True # NO TABLES INVOLVED HAVE LOCKS.

		


	
	def _get_next_workable(self) -> tuple[Optional[DSA], int, bool]:

		urgent_item: Optional[DSA] = self._urgent_queue.get_next()
		if (urgent_item):
			return (urgent_item, 0, True)

		for i in range(self.get_queue_length()):
			future_item = self._staged_queue.work_ahead(i)
			if (future_item is None): return (future_item, i, False)

			workable = self._check_workable(future_item)

			if (workable == True): return (future_item, i, False)

			"""debug = self._staged_queue.get_debug_from_queue_item(future_item)
			debug_str = self.get_debug_str({ "debug": debug }) if debug else ""

			self._logger.info(
				f"Skipping #{future_item.get("id")} due to lock. "
				f"({debug_str})" )"""
		
		# NEED TO WAIT AND COME BACK. UNLOCK CMD NOT YET FOUND IN QUEUE.
		return (None, 0, False) 
		





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
		
		next_item, index, is_urgent = self._get_next_workable()
		if (next_item is None): return False # SET NOT ACTIVE

		data: Optional[DSA] = next_item.get("data")

		if (not data):
			self._logger.warning(
				f"Ignoring task {next_item.get("id")}, no data.")
			self._staged_queue.remove_worked_ahead(index)

			return False # SET NOT ACTIVE
		
		
		create_lock: Optional[engine.Table[Any]] = data.get("create_lock_on")
		lock_id: Optional[int] = data.get("lock_id")
		close_lock: Optional[bool] = data.get("close_lock_after_query")

		if (create_lock):
			lock_id = self._create_lock(create_lock)
		
		future: Optional[Future[Any]] = data.get("future")

		success, message, result = self.__execute_item(data)

		if (close_lock and lock_id is not None): self._close_lock(lock_id)

		success_str = ""
		if (success): success_str = f", {len(result)} results returned."

		lock_str = ""
		if (lock_id is not None):
			result["lock_id"] = lock_id

			if (create_lock):
				lock_str = f"CREATED LOCK {lock_id} ON {create_lock.name}. "
			
			elif (close_lock): lock_str = f"CLOSED LOCK {lock_id}. "
			else: lock_str = f"USING LOCK {lock_id} "
		
		urgent_str = "URGENT ACTION " if is_urgent else ""

		if (future): self._event_loop.call_soon_threadsafe(
			future.set_result, result)
			
		if (is_urgent): self._urgent_queue.remove_worked_ahead(index)
		else: self._staged_queue.remove_worked_ahead(index)

		new_l = self._staged_queue.get_length()

		self._logger.info(
			f"Completed #{next_item.get("id")} {urgent_str}({message})"
			f"{success_str} {lock_str}Success: {success}. Todo: {new_l}" )
		
		return True # ACTIVE


	def create_future(self) -> asyncio.Future[Any]:
		return self.event_loop.create_future()


	def _create_lock(self, table: engine.Table[Any]):
		"""
		Locks must be created from the _main_process.

		This ensures that locks are created and deleted in the correct order.
		"""
		id_ = self._locks_created
		self._locks_created += 1

		self._locked_tables[table] = id_
		self._lock_data[id_] = table

		return id_


	def _close_lock(self, lock_id: int):
		table = self._lock_data.get(lock_id)
		if (table is None): return # TODO dangerous

		if (self._locked_tables.get(table) is not None):
			del self._locked_tables[table]
		
		del self._lock_data[lock_id]



		

	def stage_withlock(
			self,
			payload: DSA,
			future: Optional[Future[Any]] = None,
			create_lock_on: Optional[engine.Table[Any]] = None,
			lock_id: Optional[int] = None,
			close_lock_after_query: Optional[bool] = None,
			urgent: bool = False):
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
		
		create_lock_on: engine.Table
			Allows you to create a group or simulated transaction.

		lock_id: int
			The ID of a previously created lock, to continue its use.
		
		close_lock_after_query: bool
			Whether to close the lock of lock_id after this query.

		urgent: bool
			Whether action should be executed immediately (next iteration)
			by staging to urgent_queue.
		"""

		a = create_lock_on is not None
		b = lock_id is not None
		
		if ((a and b) or not (a or b)): raise ValueError(
			"You must provide exactly one of create_lock_on "
			"and close_lock_after_query" )
		
		o = {
			"payload": payload,
			"future": future,
			"lock_id": lock_id,
			"create_lock_on": create_lock_on,
			"close_lock_after_query": close_lock_after_query
		}

		if (urgent): self._urgent_queue.append(o)
		else: self._staged_queue.append(o)

		return lock_id

	
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

		Args
		--------
		query: DSA
			Data from any `Table.*` method to be passed to the DB engine.
		"""
		future = self.create_future()

		self.stage(query, future)
		response: DSA = await future

		return response
	

	async def query_withlock(
			self, query: DSA,
			create_lock_on: Optional[engine.Table[Any]] = None,
			lock_id: Optional[int] = None,
			close_lock_after_query: Optional[bool] = None):
		"""
		Wrapper for `self.stage` which contains `asyncio.Future` logic.

		This should be used to wait for a response, else use `stage` to
		declare a query and "walk away" - Maurice Moss style.

		Args
		--------
		query: DSA
			Data from any `Table.*` method to be passed to the DB engine.

		create_lock_on: engine.Table
			Allows you to create a group or simulated transaction.

		lock_id: int
			The ID of a previously created lock, to continue its use.

		close_lock_after_query: bool
			Whether to close the lock of lock_id after this query.
		"""

		if (create_lock_on is None and lock_id is None): raise ValueError(
			"You must provide exactly one of create_lock_on "
			"and close_lock_after_query, you provided none." )

		if (close_lock_after_query is not None and lock_id is None):
			raise ValueError("To close a lock you must provide its id.")

		future = self.create_future()

		lock_id = self.stage_withlock(
			query, future, create_lock_on, lock_id, close_lock_after_query)

		response: DSA = await future

		return response
	

	def close_lock(self, lock_id: int):
		"""
		Stages a close_lock command.

		This must be called after the lock has been completely used.
		You *must* `await` the final query which relies on the lock
		before staging the close_lock.

		If your queries are scheduled and delated, this lock will be
		released before they execute, as close_lock applies immediately.
		Therefore you must wait until you have finished with the lock
		before staging this.

		Using urgent_queue because otherwise the close_lock query could be
		buried behind thousands of other queries, forcing them to run first,
		which is not ideal. We want to prioritise Product queries, and these
		would only run after 1000 queries had completed to allow the close_lock
		command to run.
		"""

		self.stage_withlock(
			{"no_sql": True}, # FILLER ENTRY, NO QUERY JUST CLOSE LOCK.
			lock_id = lock_id,
			close_lock_after_query = True,
			urgent = True)
	
	

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

				locks_str = ", ".join(
					f"{v.name}: {i}"
					for v, i in self._locked_tables.items() )

				self._logger.critical(
					f"DROPPING ALL LOCKS DUE TO ABOVE EXCEPTION. "
					f"Lost {locks_str}")
				
				self._locked_tables = {}