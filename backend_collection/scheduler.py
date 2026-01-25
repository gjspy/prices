from datetime import datetime
import asyncio

from dotenv import dotenv_values


from dbmanager.engine import Database
from dbmanager.process import DBThread


from backend_collection.collectors import (
	akamai, aldi, algolia, clusters, graphql)

from backend_collection.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores)

from backend_collection.log_handler import logger
from backend_collection.storer import Writer


RESULTS_PER_SEARCH = 100
config = dotenv_values(".config")
env = dotenv_values(".env")


asd = algolia.AlgoliaCollector(env, config, RESULTS_PER_SEARCH) # good cfw
tsc = graphql.GQLCollector(env, config, RESULTS_PER_SEARCH) # good cfw
mor = clusters.ClusterCollector(env, config, RESULTS_PER_SEARCH) # good cfw
sns = akamai.AKMCollector(env, config, RESULTS_PER_SEARCH) # bad cfw
ald = aldi.ALDCollector(env, config, 60) # "Page limit must be equal to some of there values: [12,16,24,30,32,48,60]"


class State(): # give same instance to writer and scheduler
	keywords_done = []
	time_to_next_batch = 0
	data_today: dict[int, tuple[int, list[int]]] = {}
	ids_to_interrogate = []

	def new_batch(self):
		data_today = {}
		# set time

	def load(self):
		' load from json '




class Scheduler():
	def __init__(self, thread: DBThread):
		...
	





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