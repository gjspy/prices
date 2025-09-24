from typing import Any


from dbmanager.process import DBThread # ONLY FOR TYPE. DO NOT CREATE A THREAD HERE. ONLY ONE MAY EXIST.
import dbclasses as objs
from dbclasses import Queries

import asyncio




class StorageManager():
	def __init__(self, db_thread: DBThread, data: dict[str, Any]):
		self._db_thread = db_thread
		self._data = data






	async def query_product_exists(self):
		link_data: dict[str, Any] = self._data["link"]
		
		future = self._db_thread.create_future()
		query = Queries.get_link_by_some_id(link_data)

		print(query)

		if (not query):
			# TODO: log
			return

		self._db_thread.stage(query, future)
		async with asyncio.timeout(5): # SEE ABT THIS! JUST FOR TESTING RN? TODO
			result = await future

		a = result[0]
		a: objs.ProductLink

		a.cin

		print("HELLO")
		print(a.to_dict())
		print(a.product_id)
		print("EEEEE")



		


	def process_product_storable(self):
		# 1) HAVE WE SEEN THIS BEFORE?

		...