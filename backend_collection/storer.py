from functools import partial
from datetime import datetime
from logging import Logger
from os import path
import requests
import json


# TODO: MAKE ALL TYPES COME FROM types
from backend_collection.types import DSA, DSI, Any, Optional
from backend_collection.constants import StoreNames, async_executor, LABEL_TYPES, utcnow, DATE_FMT

from dbmanager.process import DBThread # ONLY FOR TYPE. DO NOT CREATE A THREAD HERE. ONLY ONE MAY EXIST.
from dbmanager.engine import TableRow, Join, LOWER

from backend_collection.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores, Offers, OfferHolders, Labels,

	# TableRows ONLY IMPROTED FOR TYPEHINTS.
	ProductLink, Brand, Store, Product, Offer
)
from backend_collection.dbclasses import Queries
from backend_collection.state import State


class Writer():
	NOSQL_DATA_DIR = "storage"
	IMAGE_FILES_DIR = path.join(NOSQL_DATA_DIR, "images")
	OFFERS_DIR = path.join(NOSQL_DATA_DIR, "offers")
	IMAGE_NAME_FMT = "{0}.png"
	OFFERS_NAME_FMT = "{0}.json"
	# TODO: ON INIT, READING .state ETC, CREATE STORE DATA (CACHE STORE IDS)

	def __init__(self, env: DSA, logger: Logger, thread: DBThread, state: State):
		self._db_thread = thread
		self._logger = logger
		self._state = state


		self.__cfww = env["CFW"]
		self.__cfws = env["CFW_S"]
		self.__cfwa = json.loads(env["CFW_A"])
	

# TODO PRICE THIS BATCH STUFF
	

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
		id_: Optional[int] = self._state.store_names.get(store_name)

		return id_ if (id_ is not None) else self._state.store_names[store_name]




	async def get_brand_id(self, brand_name: str, store_id: int) -> int:
		query = Brands.select(
			where = ((LOWER(Brands.row.brand_name) == brand_name.lower()) &
				(Brands.row.store == store_id)),
			join_on = [Brands.row.parent.join])

		existing: list[Brand] = await self._db_thread.query(query)

		if (existing):
			brand = existing[0]

			parent_v = brand.parent.value
			if (parent_v and isinstance(parent_v, Brand)):
				db_id = parent_v.db_id.plain_value
				if (db_id): return db_id
			
			db_id = brand.db_id.plain_value
			if (db_id): return db_id

			raise LookupError(
				f"Could not get brand_id for {brand_name}, it does exist.")

		new_id = await self.create_brand(brand_name, store_id)
		return new_id
		


	async def _get_existing_links_from_ids(
			self, upcs: list[int],
			cin: int, store: int) -> list[ProductLink]:
		
		query = Queries.get_link_by_ids(upcs, cin, store)
		return await self._db_thread.query(query)
	

	async def create_brand(self, brand_name: str, store_id: int) -> int:
		db_row = Brands.row.new()
		db_row.brand_name.value = brand_name
		db_row.store.ref_value(Store).db_id.value = store_id

		brand_id = await self._db_thread.query(Brands.insert(db_row))

		if (len(brand_id) == 0): raise LookupError(
			f"Could not create brand for {brand_name}, query gave []")

		return brand_id[0]


	async def create_product(self, product: DSA, store_id: int) -> int:
		db_row = Products.row.from_dict(product)

		brand_id = await self.get_brand_id(product["brand_name"], store_id)
		db_row.brand.ref_value(Brand).db_id.value = brand_id

		new_id = await self._db_thread.query(Products.insert(db_row))

		if (len(new_id) == 0): raise LookupError(
			f"Could not create brand for {product}, query gave []")

		return new_id[0]
	
	def create_link(self, product_id: int, link: DSA):
		db_row = ProductLinks.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = self.get_store_id(link["store_name"])

		db_row.cin.value = link["cin"]

		upc = link.get("upc")
		if (upc): db_row.upc.value = upc

		# DON'T WANT RESPONSE SO thread.STAGE, NOT QUERY
		self._db_thread.stage(ProductLinks.insert(db_row)) 


	def create_price_entry(self, product_id: int, store_id: int, price: DSA):
		db_row = PriceEntries.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.price_pence.value = price["price_pence"]
		db_row.available.value = price["available"]

		self._db_thread.stage(PriceEntries.insert(db_row))


	async def get_image_data(self, src: str):
		func = partial(requests.request,
			method = "POST",
			url = self.__cfww,
			headers = self.__cfwa,
			json = {"u": src, "s": self.__cfws})

		result = await async_executor(func)
		return result
	


	async def store_image(self, product_id: int, store_id: int, image: DSA):
		db_row = Images.row.new()

		db_row.product_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.src.value = image["url"]

		resp = await self._db_thread.query(Images.insert(db_row))
		if (len(resp) == 0): return # INSERT FAILED, UNIQUE CONSTRAINT.

		data = await self.get_image_data(image["url"])

		p = path.join(
			self.IMAGE_FILES_DIR, self.IMAGE_NAME_FMT.format(resp[0]))

		with open(p, "wb") as f: f.write(data.content)
	

	async def store_label(self, product_id: int, store_id: int, label: DSA):
		label_type = LABEL_TYPES.get_type(label)
		label_data = LABEL_TYPES.return_params(label_type, label)

		db_row = Labels.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.label_type.value = label_type
		db_row.param1.value = label_data[0]
		db_row.entry_verified.value = utcnow()

		await self._db_thread.query(Labels.insert(db_row, on_duplicate_key_update=True))
		#if (len(resp) != 0): return # CREATED NEW

		# ELSE, UPDATE OLD TO VERIFY
		"""self._db_thread.stage(Labels.update_blanket(
			(Labels.row.product == product_id) &
			(Labels.row.store == store_id) &
			(Labels.row.label_type == label_type) &
			(Labels.row.param1 == label_data[0]),

			[ ( Labels.row.entry_verified, utcnow() ) ]))"""


	async def store_rating(self, product_id: int, store_id: int, rating: DSA):
		db_row = Ratings.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.avg.value = rating["avg"]
		db_row.count.value = rating["count"]

		await self._db_thread.query(Ratings.insert(db_row, on_duplicate_key_update=True))
		"""if (len(resp) != 0): return # CREATED NEW

		# ELSE, REPLACE OLD WITH NEW DATA
		db_row.db_id.value = resp[0] # SET PKEY
		self._db_thread.stage(Ratings.update(db_row)) # UPDATE BY PKEY"""




	async def store_labels(self, product_id: int, store_id: int, labels: list[DSA]):
		for label in labels:
			await self.store_label(product_id, store_id, label["data"])




	async def create_offer(self, store_id: int, offer: DSA):
		db_row = Offers.row.from_dict(offer, False)
		db_row.store.ref_value(Store).db_id.value = store_id

		created = await self._db_thread.query(Offers.insert(db_row))
		if (len(created) == 0): return created # ALREADY EXIST. NO FILE.

		p = path.join(self.OFFERS_DIR, self.OFFERS_NAME_FMT.format(created[0]))

		s = offer.get("start_date")
		e = offer.get("end_date")

		if (s): offer["start_date"] = datetime.strftime(s, DATE_FMT)
		if (e): offer["end_date"] = datetime.strftime(e, DATE_FMT)
		
		with open(p, "w") as f:
			json.dump(offer, f)

		return created


	def create_offer_holder(self, offer_id: int, product_id: int):
		db_row = OfferHolders.row.new()

		db_row.offer.ref_value(Offer).db_id.value = offer_id
		db_row.product.ref_value(Product).db_id.value = product_id

		# UNIQUE CONTRAINT WILL PREVENT DUPLICATION
		self._db_thread.stage(OfferHolders.insert(db_row))
	


	async def get_product_id(
			self, product: DSA, links: list[DSA],
			upcs: list[int], cin: int, store_id: int ) -> int:

		existing_links: list[ProductLink] = await self._get_existing_links_from_ids(upcs, cin, store_id)

		product_id = None
		print(existing_links)

		# GET PID FROM LINKS
		for link in existing_links:
			product_id = link.product.ref_value(Product).db_id.plain_value
			if (product_id is not None): break

		if (not product_id):
			product_id = await self.create_product(product, store_id)

			for link in links: self.create_link(product_id, link["data"])
		
		return product_id


	async def get_offer_id(
			self, product_id: int, store_id: int, offer: DSA) -> Optional[int]:
		existing = await self._db_thread.query(
			Queries.get_offer_by_store_data(store_id, offer["store_given_id"]))
		# QUERY EXISTING BECAUSE WE NEED ITS ID FOR OFFERHOLDER.
		
		existing_id: Optional[int] = None
		
		if (existing and len(existing) != 0):
			existing_id = existing[0].db_id.value

		else:
			existing = await self.create_offer(store_id, offer)
			if (len(existing) != 0): existing_id = existing[0]
		
		if (not existing_id): return None

		self.create_offer_holder(existing_id, product_id)

		return existing_id


	

	async def get_offer_ids(
			self, product_id: int,
			store_id: int, offers: list[DSA]) -> list[int]:

		got: list[int] = []

		for offer in offers:
			print(offer)
			this = await self.get_offer_id(product_id, store_id, offer["data"])
			if (not this): continue

			got.append(this)
		
		return got




	async def write_storable_group(self, data: list[DSA]):
		product = self._get_data_of_type(data, "product")[0]["data"]

		links = self._get_data_of_type(data, "link")
		upcs, cin, store = self._extract_link_data(links)
		store_id = self.get_store_id(store)


		# 1) GET / CREATE PRODUCT
		# 	a) GET / CREATE BRAND
		# 	b) GET / CREATE LINKS
		try:
			self._logger.info(f"New getting product_id for {store}-{cin}")
			
			got_pid = await self.get_product_id(
				product, links, upcs, cin, store_id)
			
			self._logger.info(f"Got product_id of {store} {cin}: P#{got_pid}")

		except Exception as e:
			self._logger.error(f"Couldn't get product_id for {store}-{cin} / {e}")
			return
		

		# 2) CREATE PRICEENTRY
		try:
			price = self._get_data_of_type(data, "price")[0]["data"]
			self.create_price_entry(got_pid, store_id, price)

			self._logger.info(f"Created price entries for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create prices for P#{got_pid} / {e}")

		# 3) STORE IMAGE
		try:
			image = self._get_data_of_type(data, "image")[0]["data"]
			await self.store_image(got_pid, store_id, image)

			self._logger.info(f"Created images for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create images for P#{got_pid} / {e}")


		# 4) STORE OFFERS + HOLDERS.
		try:
			offers = self._get_data_of_type(data, "offer")
			if (offers):
				await self.get_offer_ids(got_pid, store_id, offers)
				self._logger.info(f"Created offers for P#{got_pid}")
			
			else: self._logger.debug(f"No offers for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create offers for P#{got_pid} / {e}")

		# 5) STORE LABELS
		try:
			labels = self._get_data_of_type(data, "label")
			if (labels):
				await self.store_labels(got_pid, store_id, labels)
				self._logger.info(f"Created labels for P#{got_pid}")
			
			else: self._logger.debug(f"No labels for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create labels for P#{got_pid} / {e}")
		
		
		
		# 6) STORE RATING
		try:
			rating = self._get_data_of_type(data, "rating")[0]["data"]
			if (rating):
				await self.store_rating(got_pid, store_id, rating)
				self._logger.info(f"Created rating for P#{got_pid}")
			
			else: self._logger.debug(f"No rating for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create rating for P#{got_pid} / {e}")
		
		self._logger.info(f"Completed storage of P#{got_pid} ({store}-{cin})")
	
	# DONE OMG

		
		
		

		



