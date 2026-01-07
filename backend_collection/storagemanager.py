from typing import Any


from dbmanager.process import DBThread # ONLY FOR TYPE. DO NOT CREATE A THREAD HERE. ONLY ONE MAY EXIST.
from dbmanager.engine import TableRow
import dbclasses as objs
from dbclasses import Queries

import asyncio




class StorageManager():
	def __init__(self, db_thread: DBThread, data: DSA):
		self._db_thread = db_thread
		self._data = data






	"""async def query_product_exists(self):
		link_data: DSA = self._data["link"]
		
		future = self._db_thread.create_future()
		query = Queries.get_link_by_some_id(link_data)

		print(query)

		if (not query):
			# TODO: log
			return

		self._db_thread.stage(query, future)
		#async with asyncio.timeout(5): # SEE ABT THIS! JUST FOR TESTING RN? TODO
		db_response = await future

		if (len(db_response) == 0): return
		else: return db_response[0]"""

		
	async def query_product_exists(self, data: dict[str, int | str]) -> list[TableRow] | None:		
		future = self._db_thread.create_future()
		query = Queries.get_link_by_some_id(data)

		print(query)

		if (not query):
			# TODO: log? 
			return

		self._db_thread.stage(query, future)
		#async with asyncio.timeout(5): # SEE ABT THIS! JUST FOR TESTING RN? TODO
		db_response = await future

		if (len(db_response) == 0): return
		else: return db_response



	async def create_product(self):
		product = objs.Product.from_dict(self._data["product"])

		insert = objs.Products.insert(product)
		future = self._db_thread.create_future()
		self._db_thread.stage(insert, future)
		result = await future

		our_product_id = result[0]

		return our_product_id

	async def create_product_link(self):
		product_link = objs.ProductLink.from_dict(self._data["link"])

		insert = objs.ProductLinks.insert(product_link)
		future = self._db_thread.create_future()
		self._db_thread.stage(insert, future)
		result = await future

		return result



	async def create_price_entry(self):
		price_entry = objs.PriceEntry.from_dict(self._data["price"])



	async def process_product_storable(self):
		link_data: DSA = self._data["link"]
		upc: int | None = link_data.get("upc")
		cin: int = link_data.get("cin") # type: ignore
		store: str = link_data.get("store") # type: ignore

		# DOES CIN + STORE EXIST?
		current_link_by_cin = await self.query_product_exists({"cin": cin, "store": store})

		if (not current_link_by_cin): # DOES NOT EXIST
			created_product_id = await self.create_product() # SO CREATE PRODUCT
			unlinked = True

			if (upc): # DOES PRODUCT HAVE UPC?
				# DOES UPC EXIST ELSEWHERE?
				other_existing = await self.query_product_exists({"upc": upc})

				if (other_existing and len(other_existing) > 1): # UPC ALREADY EXISTS
					unlinked = False
					# TODO: UPDATE OTHER ROWS TO MAKE Unlinked = False

			# CREATE PRODUCT LINK BY CIN AND Store (AND UPC IF PRODUCT HAS)
			self._data["link"]["unlinked"] = unlinked
			self._data["link"]["our_product_id"] = created_product_id
			await self.create_product_link()


		# CIN + STORE ENTRY NOW EXIST
		# UPC WILL EXIST IN THE SAME ROW IF PRODUCT HAS IT.

		# CREATE PRICE ENTRIES
		await self.create_price_entry()