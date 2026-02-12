from datetime import datetime, time as dtime, timedelta, timezone
from dotenv import dotenv_values
from os import path
import sshtunnel # type: ignore
import platform
import asyncio
import time



from dbmanager.process import DBThread
from dbmanager.engine import Database


from backend.collector.modules import akamai, aldi, algolia, clusters, graphql
from backend.collector.storer import Writer
from backend.collector.state import State

from backend.dbclasses import Stores, Store
from backend.log_handler import get_logger, CustomLogger
from backend.constants import utcnow, DATE_FMT



RESULTS_PER_SEARCH = 100
config = dotenv_values(".config")
env = dotenv_values(".env")

logger = get_logger("collection", path.join("state", "stats.json"))


asd = algolia.AlgoliaCollector(logger, env, config, RESULTS_PER_SEARCH) # good cfw
tsc = graphql.GQLCollector(logger, env, config, RESULTS_PER_SEARCH) # good cfw
mor = clusters.ClusterCollector(logger, env, config, RESULTS_PER_SEARCH) # good cfw
sns = akamai.AKMCollector(logger, env, config, RESULTS_PER_SEARCH) # bad cfw
ald = aldi.ALDCollector(logger, env, config, 60) # "Page limit must be equal to some of there values: [12,16,24,30,32,48,60]"
COLLECTORS = [asd, tsc, mor, sns, ald]

DEBUG = config["DEBUG"] == "True"
# DISABLES SALVAGING OF LAST BATCH's KEYWORDS OR RUNNING IMMEDIATELY IF DELAYED.
ONLY_WAIT_FOR_NEXT_BATCH = config["ONLY_WAIT_FOR_NEXT_BATCH"] == "True" 

# LIST MUST BE IN ORDER
RUNTIMES = [
	dtime( 1,00),
	dtime( 5,00),
	dtime(12,00)
]


COOLDOWN = 1 # SECONDS
MAX_DB_QUEUE_BEFORE_WAIT = 1000 # ITEMS


class Scheduler():
	KEYWORDS_PATH = path.join("state", "keywords.csv")

	def __init__(
			self, logger: CustomLogger, thread: DBThread,
			state: State, writer: Writer):

		self._logger = logger
		self._db_thread = thread
		self._state = state
		self._writer = writer


	async def init_store_data(self):
		q = Stores.select()
		data = await self._db_thread.query(q)
		
		results = data.get("fetchall")
		if (not results):
			raise Exception("No results from Stores query, can't get names.")

		v: Store
		for v in results:
			store_name = v.name.plain_value
			store_id = v.db_id.plain_value

			if (store_name is None or store_id is None): raise Exception(
				f"FATAL, could not get store_name {store_name} {store_id}")

			self._state.store_names[store_name] = store_id


	def get_session_n(self):
		return int(time.time()) // (60 * 60 * 24)

	def get_nearest_runtime(self):
		now = utcnow()
		next_time = None

		for runtime in RUNTIMES:
			diff = (
				((runtime.hour * 60) + runtime.minute) - 
				((now.hour * 60) + now.minute))

			if (diff <= 0): continue

			next_time = runtime
			break

		if (next_time):
			return datetime(
				now.year, now.month, now.day,
				next_time.hour, next_time.minute,
				tzinfo = timezone.utc)

		tmrw = now + timedelta(days = 1)
		next_time = RUNTIMES[0] # NONE LEFT TODAY. WAIT UNTIL TMRW.

		return datetime(
			tmrw.year, tmrw.month, tmrw.day,
			next_time.hour, next_time.minute,
			tzinfo = timezone.utc)


	def get_keywords(self):
		with open(self.KEYWORDS_PATH,"r") as f:
			file = f.read().splitlines(False)

		return file

	async def scrape(self, keywords: list[str]):
		"""
		Iterate STORES for every keyword, as STORES is the smaller group.
		want to quickly get variety of products.

		If iterated KEYWORD for every STORE, would be slower to update
		entire stores' data.
		"""

		for i in range(len(keywords)):
			ql = self._db_thread.get_queue_length()

			if (ql > MAX_DB_QUEUE_BEFORE_WAIT):
				self._logger.progress(
					"Waiting before next keyword. DB Thread has queue "
					f"of {ql}, > max [{MAX_DB_QUEUE_BEFORE_WAIT}].")
				
				while ql > (MAX_DB_QUEUE_BEFORE_WAIT / 2):
					await asyncio.sleep(COOLDOWN)
					ql = self._db_thread.get_queue_length()

			kw = keywords[i]
			self._logger.progress(f"Starting fetch for keyword {kw}")

			for store in COLLECTORS:
				fetchid = f"{store.store}-{kw}"

				result = await store.search(kw, DEBUG)

				self._logger.progress(
					f"Writing {len(result)} results for Fetch#{fetchid}" )

				asyncio.create_task(
					self._writer.write_from_search_results(result, fetchid))

			self._state.now = utcnow()
			self._state.keywords_todo = keywords[i:] # i IS INCLUSIVE.
			# DON'T REMOVE CURR KEYWORD FROM state INCASE CRASHES WHILE
			# DB EXECUTING THESE QUERIES.

			self._state.dump()

			await asyncio.sleep(1)

			self._logger.notice(f"Completed all stores for '{kw}'")







	async def main_loop(self):
		while True:
			await asyncio.sleep(COOLDOWN)

			next_runtime = self._state.time_next_batch
			now = utcnow()
			seconds = next_runtime.timestamp() - now.timestamp()

			self._logger.notice(
				f"New batch starting soon. Time is {now.strftime(DATE_FMT)} "
				f"and next batch to run {next_runtime.strftime(DATE_FMT)}. "
				f"Waiting {int(seconds):,} seconds. ({seconds / 60:.2f} minutes)")

			try: await asyncio.sleep(seconds)
			except asyncio.exceptions.CancelledError: return True

			await self.new_batch()




	async def new_batch(self):
		n = self.get_session_n()
		kwrds = self.get_keywords()
		next_time = self.get_nearest_runtime()
		now = utcnow()

		self._logger.notice(
			f"New batch starting now. Time is {now.strftime(DATE_FMT)} "
			f"and session_id is {n}. {len(kwrds)} keywords staged.")

		self._state.session = n
		self._state.keywords_todo = kwrds
		self._state.time_next_batch = next_time
		self._state.now = now

		self._state.dump()

		await self.scrape(kwrds)

		self._logger.notice(
			f"Batch starting {now.strftime(DATE_FMT)} has finished scraping. "
			f"Next batch queued for {next_time.strftime(DATE_FMT)}, "
			"exiting to main_loop to wait.")


	async def start(self):
		# SALVAGE .state DATA INCASE OF CRASH.
		# PICK UP WHERE WE LEFT OFF.

		self._logger.info("Scheduler has started.")

		time_next = self._state.time_next_batch
		kwrds_todo = self._state.keywords_todo or []
		if (time_next and (not ONLY_WAIT_FOR_NEXT_BATCH)):
			now = utcnow()

			if (time_next.timestamp() <= now.timestamp()):
				self._logger.warning(
					f"Starting new batch, as time is {now.strftime(DATE_FMT)} "
					f"as was meant to start at {time_next.strftime(DATE_FMT)}")

				await self.new_batch() # WAIT!!!!!

			elif (len(kwrds_todo) > 1):
				self._logger.warning(
					"We have time to wait before next batch. Going to restart "
					f"previous batch, to collect {len(kwrds_todo)} keywords.")

				await self.scrape(kwrds_todo) # WAIT FOR IT TO FINISH, INCASE
				# OVERLAPS WITH NEXT BATCH WE WANT

		self._state.time_next_batch = self.get_nearest_runtime()


		while True:
			try:
				quit_debug = await self.main_loop()
				if (quit_debug): return

			except: self._logger.exception("SCHEDULER MAIN_LOOP BROKE")





async def main():
	db = Database.from_env(env, logger)

	succ = db.connect()
	logger.info(f"DB Connected {succ} {db.is_connected}")

	thread = DBThread(
		logger, db, asyncio.get_event_loop(), path.join("state", "queue.txt"))
	thread.start()

	state = State()
	state.load() # from JSON

	writer = Writer(env, logger, thread)
	scheduler = Scheduler(logger, thread, state, writer)

	await scheduler.init_store_data()
	writer.set_state(state)

	await scheduler.start()

	db.disconnect()
	logger.critical("DB disconnected and code exiting.")


def __main__():
	logger.notice(f"BEGAN {utcnow().strftime(DATE_FMT)}")

	if (platform.system() == "Windows"):

		ssh_port = env["SSH_PORT"]
		ssh_host = env["SSH_HOST"]
		ssh_user = env["SSH_USER"]
		ssh_keyy = env["SSH_KEYY"]
		db__host = env["DB_HOST"]
		db__port = env["DB_PORT"]

		assert (
			ssh_port and ssh_host and ssh_user and
			ssh_keyy and db__host and db__port )

		ssh_port = int(ssh_port)
		db__port = int(db__port)

		with sshtunnel.SSHTunnelForwarder(
				ssh_address_or_host = (ssh_host, ssh_port),
				ssh_username = ssh_user,
				ssh_pkey = ssh_keyy,
				remote_bind_address = (db__host, db__port) ) as tunnel:

			assert tunnel
			logger.debug(f"SSH TUNNEL ACTIVE: {tunnel.is_active}")

			env["DB_PORT"] = tunnel.local_bind_port # type: ignore

			asyncio.run(main()) # MUST DO THIS INSIDE "WITH" TO MAINTAIN TUNNEL
		
		return



	asyncio.run(main())



if (__name__ == "__main__"): __main__()