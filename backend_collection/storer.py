from typing import Any # TODO: MAKE ALL TYPES COME FROM types
import copy

from backend_collection.types import DSA
from backend_collection.constants import StoreNames

from dbmanager.process import DBThread # ONLY FOR TYPE. DO NOT CREATE A THREAD HERE. ONLY ONE MAY EXIST.
from dbmanager.engine import TableRow, Join

import backend_collection.dbclasses as objs
from backend_collection.dbclasses import Queries





class Writer():
	# TODO: ON INIT, READING .state ETC, CREATE STORE DATA (CACHE STORE IDS)
	_store_data = {
		"UNKNOWN": 0,
		"TESCO": 1,
		"ASDA": 2,
		"MORRISONS": 3,
		"SAINSBURYS": 4,
		"ALDI": 5
	}

	def __init__(self, db_thread: DBThread):
		self._db_thread = db_thread
	

	def _get_data_of_type(self, data: list[DSA], type_: str) -> list[DSA]:
		return list(filter(
			lambda x: x.get("type") == type_,
			data
		))


	def _extract_link_data(
			self, links: list[DSA]) -> tuple[list[int], int, str]:
		upc: list[int] = []
		cin = links[0]["data"]["cin"]
		store = links[0]["data"]["store_name"]

		for link in links:
			this_upc: int | None = link.get("upc")
			if (this_upc and (not this_upc in upc)): upc.append(this_upc)
		
		return (upc, cin, store)
	
	def get_store_id(self, store_name: str):
		id_ = self._store_data.get(store_name)

		return id_ if (id_ is not None) else self._store_data[StoreNames.unknown]
	
	def _query_brand_with_name(self, brand_name: str):
		joined_brand = objs.NestedBrand#.duplicate()

		query = objs.Brands.select(
			objs.Brand.name == brand_name, # TODO ignorecase
			join_on = [Join(
				joined_brand, joined_brand.db_id == objs.Brand.parent,
				"LEFT"
			)]
		)

		print(query["query"])



	async def get_brand_id(self, brand_name: str) -> int:

		query = objs.Brands.select(
			objs.Brand.name == brand_name, # TODO ignorecase
			join_on = [Join(objs.Brand, objs.Brand.db_id == objs.Brand.parent, "LEFT", True)]
		)
		print(query)
		existing: list[objs.Brand] = await self._db_thread.query(query)

		if (existing):
			brand = existing[0]

			return brand.parent.db_id if (brand.parent) else brand.db_id # type: ignore
		
		new_id = await self.create_brand(brand_name)
		return new_id
		


	async def _get_existing_links_from_ids(
			self, upcs: list[int],
			cin: int, store: int) -> list[objs.ProductLink]:
		
		query = Queries.get_link_by_ids(upcs, cin, store)
		return await self._db_thread.query(query)
	
	async def create_brand(self, brand_name: str) -> int:
		db_row = objs.Brand()
		db_row.name = brand_name# type: ignore TODO

		brand_id = await self._db_thread.query(objs.Brands.insert(db_row))
		return brand_id


	async def create_product(self, product: DSA):
		db_row = objs.Product.from_py_dict(product)

		# TODO: ADD BRAND ID
		# db_row.brand.db_id OR db_row.brand = ..
		brand_id = await self.get_brand_id(product["brand_name"])
		
		query = objs.Products.insert(db_row)
		new_id: int = await self._db_thread.query(query)

		return new_id


	async def get_product_id(self, product: DSA, links: list[DSA]) -> int | None:
		upcs, cin, store = self._extract_link_data(links)
		store_id = self.get_store_id(store)

		existing_links: list[objs.ProductLink] = await self._get_existing_links_from_ids(upcs, cin, store_id)

		product_id = None
		print(existing_links)

		#for link in existing_links:
			#link.product.

		if (not product_id):
			product_id = await self.create_product(product)
		
		return product_id







	#def verify_types()


	async def write_storable_group(self, data: list[DSA]):
		product = self._get_data_of_type(data, "product")[0]["data"]
		links = self._get_data_of_type(data, "link")

		pid = await self.get_product_id(product, links)

