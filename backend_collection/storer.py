# TODO: MAKE ALL TYPES COME FROM types
from backend_collection.types import DSA, DSI, Any, Optional
from backend_collection.constants import StoreNames

from dbmanager.process import DBThread # ONLY FOR TYPE. DO NOT CREATE A THREAD HERE. ONLY ONE MAY EXIST.
from dbmanager.engine import TableRow, Join, LOWER

from backend_collection.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores,

	# TableRows ONLY IMPROTED FOR TYPEHINTS.
	ProductLink, Brand, Store
)
from backend_collection.dbclasses import Queries





class Writer():
	# TODO: ON INIT, READING .state ETC, CREATE STORE DATA (CACHE STORE IDS)
	"""_store_data = {
		"UNKNOWN": 0,
		"TESCO": 1,
		"ASDA": 2,
		"MORRISONS": 3,
		"SAINSBURYS": 4,
		"ALDI": 5
	}"""

	def __init__(self, db_thread: DBThread):
		self._db_thread = db_thread
		self._this_batch: dict[int, tuple[int, list[int]]] = {}
		self._store_data: DSI = {}

	
	async def init_store_data(self):
		data = await self._db_thread.query(Stores.select())

		v: Store
		for v in data:
			store_name: str = v.name.value # type: ignore[reportAssignmentType]
			store_id: int = v.db_id.value #  type: ignore[reportAssignmentType]
			self._store_data[store_name] = store_id




	def reset_batch(self):
		"""
		Start new batch, to allow all product ids to have a new price entry
		recorded.
		"""
		self._this_batch = {}
	
	def get_price_this_batch(self, product_id: int):
		"""
		Returns `tuple` of `(price_pence, list[offer_id])` for product_id
		from this batch.
		"""
		return self._this_batch.get(product_id)
	

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
		id_: Optional[int] = self._store_data.get(store_name)

		return id_ if (id_ is not None) else self._store_data[StoreNames.unknown]



	async def get_brand_id(self, brand_name: str) -> int:
		query = Brands.select(
			where = LOWER(Brands.name) == brand_name.lower(),
			join_all = True)
		print(query)
		existing: list[Brand] = await self._db_thread.query(query)

		if (existing):
			brand = existing[0]

			return brand.parent.db_id if (brand.parent) else brand.db_id # type: ignore TODO ?
		
		new_id = await self.create_brand(brand_name)
		return new_id
		


	async def _get_existing_links_from_ids(
			self, upcs: list[int],
			cin: int, store: int) -> list[ProductLink]:
		
		query = Queries.get_link_by_ids(upcs, cin, store)
		return await self._db_thread.query(query)
	

	async def create_brand(self, brand_name: str) -> int:
		db_row = Brands.row.new()
		db_row.name.value = brand_name

		brand_id = await self._db_thread.query(Brands.insert(db_row))
		return brand_id


	async def create_product(self, product: DSA):
		db_row = Products.row.from_dict(product)

		# TODO: ADD BRAND ID
		# db_row.brand.db_id OR db_row.brand = ..
		brand_id = await self.get_brand_id(product["brand_name"])
		db_row.brand.value = brand_id
		
		new_id: int = await self._db_thread.query(Products.insert(db_row))

		return new_id
	
	def create_link(self, product_id: int, link: DSA):
		db_row = ProductLinks.row.new()

		db_row.cin.value = link["cin"]
		db_row.store.value = self.get_store_id(link["store"])

		upc = link.get("upc")
		if (upc): db_row.upc.value = upc

		self._db_thread.stage(ProductLinks.insert(db_row)) # DON'T WANT RESPONSE SO STAGE, NOT QUERY


	async def create_price_entry(self, product_id: int, store_id: int, ):...


	async def get_product_id(self, product: DSA, links: list[DSA]) -> int:
		upcs, cin, store = self._extract_link_data(links)
		store_id = self.get_store_id(store)

		existing_links: list[ProductLink] = await self._get_existing_links_from_ids(upcs, cin, store_id)

		product_id = None
		print(existing_links)

		#for link in existing_links:
		#	if (not link.product.id): continue # type?
		#	product_id = link.product.?

		if (not product_id):
			product_id = await self.create_product(product)

			for link in links: self.create_link(product_id, link)

		
		return product_id
	

	async def get_offer_ids(self, product: DSA, offers: list[DSA]) -> list[int]:
		' Query offers by internal id, exist = return, no = make '




	async def write_storable_group(self, data: list[DSA]):
		product = self._get_data_of_type(data, "product")[0]["data"]
		links = self._get_data_of_type(data, "link")
		offers = self._get_data_of_type(data, "offer")
		price = self._get_data_of_type(data, "price")[0]["data"]

		pid = await self.get_product_id(product, links)
		offer_ids = await self.get_offer_ids(product, offers)

		current_price = price["price_pence"]

		existing_data = self.get_price_this_batch(pid)

		if (not (
				existing_data and 
				existing_data[0] == current_price and 
				existing_data[1] == offer_ids)):
			await self.create_price_entry()
		
		# RATINGS -> UPDATE if exists
		# LABELS (PRICEMATCH)
		# Image, do before productId or during maybe?
		# DONT SET preferredthumb, thats only for manually setting.

		# SAVE ALL IMAGES LOCALLY
		# store JSON datas in thsi class.
		# TODO: get store data instead of dict.

		
		
		

		



