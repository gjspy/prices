from datetime import datetime
import asyncio
import json

from dotenv import dotenv_values


from dbmanager.engine import Database, MAX
from dbmanager.process import DBThread


from backend_collection.collectors import (
	akamai, aldi, algolia, clusters, graphql)

from backend_collection.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores,
	
	Store)

from backend_collection.log_handler import logger
from backend_collection.storer import Writer
from backend_collection.state import State

from backend_collection.constants import utcnow


RESULTS_PER_SEARCH = 100
config = dotenv_values(".config")
env = dotenv_values(".env")


asd = algolia.AlgoliaCollector(env, config, RESULTS_PER_SEARCH) # good cfw
tsc = graphql.GQLCollector(env, config, RESULTS_PER_SEARCH) # good cfw
mor = clusters.ClusterCollector(env, config, RESULTS_PER_SEARCH) # good cfw
sns = akamai.AKMCollector(env, config, RESULTS_PER_SEARCH) # bad cfw
ald = aldi.ALDCollector(env, config, 60) # "Page limit must be equal to some of there values: [12,16,24,30,32,48,60]"








class Scheduler():
	def __init__(self, thread: DBThread, state: State):
		self._db_thread = thread
		self.state = state
	

	async def init_store_data(self):
		q = Stores.select()
		data = await self._db_thread.query(q)

		v: Store
		for v in data:
			store_name = v.name.plain_value
			store_id = v.db_id.plain_value

			if (not (store_name and store_id)): raise Exception(
				f"FATAL: could not get store_name {store_name} {store_id}"
				f"{q}")
			
			self.state.store_names[store_name] = store_id
	
	"""async def init_batch_n(self):
		q = PriceEntries.select(
			[MAX(PriceEntries.row.batch)],
			objectify_results = False)
		
		data = await self._db_thread.query(q)
		self.state.batch = data[0][0]""" # WORKS
	





async def __main__():
	db = Database.from_env(env, logger)
	db.declare_tables(
		Products, ProductLinks, PriceEntries, Ratings, Images, Brands, Stores)
	
	db.connect()

	thread = DBThread(logger, db, asyncio.get_event_loop())
	thread.start()

	writer = Writer(thread)
	await writer.init_store_data()




if (__name__ == "__main__"): asyncio.run(__main__())