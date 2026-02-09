from functools import partial
from datetime import datetime
from os import path
import requests
import asyncio
import json


from backend_collection.types import DSA, Optional, Any
from backend_collection.log_handler import CustomLogger
from backend_collection.constants import (
	StoreNames, async_executor, LABEL_TYPES, utcnow, DATE_FMT )

from dbmanager.process import DBThread # ONLY FOR TYPE. DO NOT CREATE A THREAD HERE. ONLY ONE MAY EXIST.
from dbmanager.engine import LOWER

from backend_collection.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Offers, OfferHolders, Labels, Keywords,

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


	def __init__(self, env: DSA, logger: CustomLogger, thread: DBThread):
		self._db_thread = thread
		self._logger = logger
		self._state = None

		self.__cfww = env["CFW"]
		self.__cfws = env["CFW_S"]
		self.__cfwa = json.loads(env["CFW_A"])


	def set_state(self, state: State):
		self._state = state
		self.__cfwn = [self.get_store_id(StoreNames.sainsburys)]


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
			this_upc: Optional[int] = link["data"].get("upc")
			if (this_upc and (not this_upc in upc)): upc.append(this_upc)

		return (upc, cin, store)



	def get_store_id(self, store_name: str):
		assert self._state

		id_: Optional[int] = self._state.store_names.get(store_name)

		return id_ if (id_ is not None) else self._state.store_names[store_name]



	async def fetch_image_data(self, src: str, store_id: int):
		func = partial(
				requests.request,
				method = "GET",
				url = src,
				headers = {
					"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
					"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
					"Host": src.split("/")[2] }
			) if (store_id in self.__cfwn) else partial(
				requests.request,
				method = "POST",
				url = self.__cfww,
				headers = self.__cfwa,
				json = {"u": src, "s": self.__cfws}
			)

		self._logger.add_to_stats(f"IMAGE{store_id}")

		result = await async_executor(func)
		return result






	def store_label(self, product_id: int, store_id: int, label: DSA):
		label_type = LABEL_TYPES.get_type(label)
		label_data = LABEL_TYPES.return_params(label_type, label)

		db_row = Labels.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.label_type.value = label_type
		db_row.param1.value = label_data[0]

		# ONLY SET UpdatedDate INCASE INSERT DOES ODK UPDATE, DON'T
		# OVERWRITE ORIGINAL CreatedDate, BUT APPLY NEW UpdatedDate.
		db_row.updated_date.value = utcnow()

		self._db_thread.stage(Labels.insert(
			db_row, on_duplicate_key_update = True))



	def store_keywords(self, product_id: int, store_id: int, keywords: DSA):
		v = keywords.get("value")
		if ((not v) or (v == " ")): return
		db_row = Keywords.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.data.value = v

		self._db_thread.stage(Keywords.insert(db_row, on_duplicate_key_update=True))



	def store_rating(self, product_id: int, store_id: int, rating: DSA):
		avg, count = rating.get("avg"), rating.get("count")

		# DON'T HAVE avg == 0, CUS PPL MIGHT UNANIMOUSLY
		# HATE THAT THING!!
		if (avg is None or count is None or count == 0): return
		db_row = Ratings.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.avg.value = avg
		db_row.count.value = count

		self._db_thread.stage(Ratings.insert(db_row, on_duplicate_key_update=True))



	def store_labels(self, product_id: int, store_id: int, labels: list[DSA]):
		for label in labels:
			self.store_label(product_id, store_id, label["data"])



	def create_offer_holder(self, offer_id: int, product_id: int):
		db_row = OfferHolders.row.new()

		db_row.offer.ref_value(Offer).db_id.value = offer_id
		db_row.product.ref_value(Product).db_id.value = product_id

		# UNIQUE CONTRAINT WILL PREVENT DUPLICATION
		self._db_thread.stage(OfferHolders.insert(
			db_row, quiet_on_duplicate_entry = True))



	async def create_offer(
			self, store_id: int, offer: DSA, store_given_id: int):
		db_row = Offers.row.from_dict(offer, False)

		db_row.store_given_id.value = store_given_id
		db_row.store.ref_value(Store).db_id.value = store_id

		created = await self._db_thread.query(Offers.insert(
			db_row, on_duplicate_key_return_existing_id = True,
		)) # LOCK NOT NEEDED, AS ODK RETURN EXISTING IS SUFFICIENT.

		lastrowid = created.get("lastrowid")
		if (lastrowid is None): return

		# ALREADY EXIST, NO NEW FILE.
		# STILL USE odk_return_existing TO CREATE OfferHolders!
		if (created.get("rowsaffected") != 1): return lastrowid

		p = path.join(self.OFFERS_DIR, self.OFFERS_NAME_FMT.format(lastrowid))

		s = offer.get("start_date")
		e = offer.get("end_date")

		if (s): offer["start_date"] = datetime.strftime(s, DATE_FMT)
		if (e): offer["end_date"] = datetime.strftime(e, DATE_FMT)

		with open(p, "w") as f:
			json.dump(offer, f)

		return lastrowid



	async def _store_image(self, product_id: int, store_id: int, image: DSA):
		existing_id = await self.get_existing_image(product_id, image["url"])
		if (existing_id): return

		db_row = Images.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.src.value = image["url"]

		resp = await self._db_thread.query(Images.insert(
			db_row, quiet_on_duplicate_entry = True ))

		lastrowid = resp.get("lastrowid")
		if (lastrowid is None): return # INSERT FAILED, UNIQUE CONSTRAINT.

		data = await self.fetch_image_data(image["url"], store_id)

		p = path.join(
			self.IMAGE_FILES_DIR, self.IMAGE_NAME_FMT.format(lastrowid))

		with open(p, "wb") as f:
			f.write(data.content)



	async def store_image(self, got_pid: int, store_id: int, data: list[DSA]):
		try:
			image = self._get_data_of_type(data, "image")[0]["data"]
			await self._store_image(got_pid, store_id, image)

			self._logger.info(f"Created images for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create images for P#{got_pid} / {e}")



	def create_price_entry(self, product_id: int, store_id: int, price: DSA):
		db_row = PriceEntries.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		db_row.fetched_session.value = self._state.session # type: ignore

		db_row.price_pence.value = price["price_pence"]
		db_row.available.value = price["available"]

		self._db_thread.stage(PriceEntries.insert(
			db_row, quiet_on_duplicate_entry = True))



	def create_link_row(
			self, product_id: int, link: DSA,
			store_id: int, _include_cin: bool = True) -> ProductLink:
		db_row = ProductLinks.row.new()

		db_row.product.ref_value(Product).db_id.value = product_id
		db_row.store.ref_value(Store).db_id.value = store_id

		if (_include_cin): db_row.cin.value = link["cin"]

		upc = link.get("upc")
		if (upc is not None): db_row.upc.value = upc

		return db_row



	async def create_brand(self, brand_name: str, store_id: int) -> int:
		db_row = Brands.row.new()
		db_row.brand_name.value = brand_name
		db_row.store.ref_value(Store).db_id.value = store_id

		brand_id = await self._db_thread.query(Brands.insert(
			db_row, on_duplicate_key_return_existing_id = True))

		key = brand_id.get("lastrowid")

		if (key is None): raise LookupError(
			f"Could not create brand for {brand_name}, query gave []")

		return key







	async def create_product(self, product: DSA, cin: int, store_id: int) -> int:
		db_row = Products.row.from_dict(product)

		brand_id = await self.get_brand_id(product["brand_name"], cin, store_id)
		db_row.brand.ref_value(Brand).db_id.value = brand_id

		new_id = await self._db_thread.query(Products.insert(db_row))
		key = new_id.get("lastrowid")

		if (key is None): raise LookupError(
			f"Could not create product for {product}, query gave []")

		return key





	async def get_existing_image(self, product_id: int, url: str):
		"""
		Must get existing, as we stop collecting once there is an image
		with ProductID and IsPreferred. This is not possible to raise through
		a UNIQUE constraint so we must query for it first.
		"""

		query = Images.select(
			[Images.row.db_id],
			where = (Images.row.src == url) | (
				(Images.row.product == product_id) & (Images.row.preferred == True)
			))

		existing = await self._db_thread.query(query)
		key = existing.get("lastrowid")

		return key



	async def get_offer_id(
			self, product_id: int, store_id: int,
			cin: int, offer: DSA) -> Optional[int]:
		
		store_given_id = offer.get("store_given_id")
		try: store_given_id = int(store_given_id) # type: ignore
		except: store_given_id = cin

		resp = await self._db_thread.query(
			Queries.get_offer_by_store_data(store_id, store_given_id))

		# QUERY EXISTING BECAUSE WE NEED ITS ID FOR OFFERHOLDER.
		# WE NEED OfferIDs TO BE NON-DUPLICATED, SO WE CAN DISPLAY
		# ALL PRODUCTS IT APPLIES TO.

		results = resp.get("fetchall")

		existing_id: Optional[int] = None

		if (results and len(results) != 0):
			db_row: Offer = results[0]

			existing_id = db_row.db_id.plain_value
			end_date = offer.get("end_date")

			if (end_date is not None and db_row.end_date.value != end_date):
				# UPDATE EXPRING IF ITS NOT MEANT TO!
				db_row.end_date.value = end_date
				self._db_thread.stage(Offers.update(db_row))

		else:
			existing_id = await self.create_offer(
				store_id, offer, store_given_id)

		if (not existing_id): return None
		self.create_offer_holder(existing_id, product_id)

		return existing_id



	async def get_existing_links_from_ids(
			self, upcs: list[int],
			cin: int, store: int) -> tuple[list[ProductLink], int]:

		query = Queries.get_link_by_ids(upcs, cin, store)
		resp = await self._db_thread.query_withlock(
			query, create_lock_on = ProductLinks)
		
		results: list[ProductLink] = resp.get("fetchall") or []
		
		lock_id: Optional[int] = resp.get("lock_id")
		if (lock_id is None):
			self._logger.critical(
				f"No lock ID but query executed {upcs} {store}-{cin}")
			
			lock_id = -1

		return (results, lock_id)



	async def get_offer_ids(
			self, product_id: int,
			store_id: int, cin: int, offers: list[DSA]):

		for offer in offers:
			this = await self.get_offer_id(product_id, store_id, cin, offer["data"])
			if (not this): continue



	async def get_brand_id(
			self, brand_name: str, cin: int, store_id: int) -> int:

		if (not brand_name):
			new_id = await self.create_brand(str(cin), store_id)
			return new_id # TODO: another admin task, clean up brand names which were unknown

		query = Brands.select(
			[Brands.row.db_id, Brands.row.parent],
			where = ((LOWER(Brands.row.brand_name) == brand_name.lower()) &
				(Brands.row.store == store_id)),
			join_on = [Brands.row.parent.join])

		resp = await self._db_thread.query(query)
		existing: list[Brand] = resp.get("fetchall") or []

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



	async def get_product_id(
			self, product: DSA, links: list[DSA],
			upcs: list[int], cin: int, store_id: int ) -> int:

		existing_links: list[ProductLink]; lock_id: int
		existing_links, lock_id = await self.get_existing_links_from_ids(
			upcs, cin, store_id)

		upcs_with_existing_link: list[str] = []
		cinandstore_with_existing_link: list[tuple[str, int]] = []
		product_id: Optional[int] = None

		# GET PID FROM LINKS
		for link in existing_links:
			this_pid = link.product.ref_value(Product).db_id.plain_value
			if (product_id is None and this_pid is not None):
				product_id = this_pid
			
			this_upc = link.upc.plain_value
			if (this_upc is not None):
				upcs_with_existing_link.append(str(this_upc))
				# MAKE ALL str AS PARAM upcs CAN BE str.
			
			this_cin = link.cin.plain_value
			this_store = link.store.ref_value(Store).db_id.plain_value
			if (this_cin is not None and this_store is not None):
				cinandstore_with_existing_link.append((str(cin), this_store))
		
		# Create new Links even if we have existing_links.
		# If there are multiple UPCs, we might be able to 'daisy-chain':
		# say we got here by get_product_id(upcs = [1,2,3])
		# we query existing links, get back upcs [1,2].
		# We now have upc 3, which does not have a Link, but we now know PID!
		# so we should create the link!

		product_just_created = False

		if (product_id is None):
			product_just_created = True
			product_id = await self.create_product(product, cin, store_id)

		rows: list[ProductLink] = []

		for link in links: # CREATE ROWS DOCUMENTING EVERY UPC WE HAVE.
			link = link.get("data")
			if (not link): continue

			upc = link.get("upc")
			if (upc is None): continue
			if (str(upc) in upcs_with_existing_link): continue

			this_cinandstore = (str(link["cin"]), store_id)
			include_cin = this_cinandstore in cinandstore_with_existing_link

			rows.append(self.create_link_row(product_id, link, store_id, include_cin))

		# NO ROWS MADE TO DOCUMENT UPC (DOESNT EXIST?)
		# AND PRODUCT WAS JUST MADE, WE NEED TO LINK CIN + STORE.
		if (len(rows) == 0 and product_just_created):
			rows.append(self.create_link_row(
				product_id, links[0]["data"], store_id))
		

		if (len(rows) == 0): # FOUND PRODUCT ID, NO LINKS TO MAKE.
			self._db_thread.close_lock(lock_id)
		
		else: # LINKS TO MAKE.

			# THIS WILL RAISE ERROR IF A UPC EXISTS ALREADY.
			# SHOULD NEVER HAPPEN, CAN ONLY IF LOCKS FAIL.
			await self._db_thread.query_withlock(
				ProductLinks.insert(*rows),
				lock_id = lock_id,
				close_lock_after_query = True)


		return product_id






	async def write_storable_group(self, data: list[DSA], is_retry: bool = False):
		if (not self._state):
			self._logger.critical(
				"NO SELF.STATE, CANT DO ANYTHING WITHOUT STORE DATA.")
			return

		product = self._get_data_of_type(data, "product")[0]["data"]

		links = self._get_data_of_type(data, "link")
		upcs, cin, store = self._extract_link_data(links)
		store_id = self.get_store_id(store)

		r = "RETRY " if is_retry else ""
		if (is_retry):
			self._logger.warning(f"RETRYING {store}-{cin} NOW.")


		# 1) GET / CREATE PRODUCT
		# 	a) GET / CREATE BRAND
		# 	b) GET / CREATE LINKS
		try:
			self._logger.info(f"New {r}getting product_id for {store}-{cin}")

			got_pid = await self.get_product_id(
				product, links, upcs, cin, store_id)

			self._logger.info(f"Got product_id of {store} {cin}: P#{got_pid}")

		except Exception as e:
			self._logger.error(
				f"Couldn't get product_id for {store}-{cin} "
				f"/ {e.__class__.__name__} {e.args}")
			return False


		# 2) CREATE PRICEENTRY
		try:
			price = self._get_data_of_type(data, "price")[0]["data"]
			self.create_price_entry(got_pid, store_id, price)

			self._logger.info(f"Created price entries for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create prices for P#{got_pid} "
				f"/ {e.__class__.__name__} {e.args}")


		# 3) STORE IMAGE
		asyncio.create_task(self.store_image(got_pid, store_id, data))
		# DON'T WAIT FOR IMAGE TO FINISH, AS IS SLOW (NEW NETWORK CALL)
		# BUT STILL NEED ASYNC. AND HAVE TRY/CATCH INSIDE FUNC
		# TO LOG ERRORS WITH SAVING IMAGE.


		# 4) STORE OFFERS + HOLDERS.
		try:
			offers = self._get_data_of_type(data, "offer")
			if (offers):
				await self.get_offer_ids(got_pid, store_id, cin, offers)
				self._logger.info(f"Created offers for P#{got_pid}")

			else: self._logger.debug(f"No offers for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create offers for P#{got_pid} "
				f"/ {e.__class__.__name__} {e.args}")


		# 5) STORE LABELS
		try:
			labels = self._get_data_of_type(data, "label")
			if (labels):
				self.store_labels(got_pid, store_id, labels)
				self._logger.info(f"Created labels for P#{got_pid}")

			else: self._logger.debug(f"No labels for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create labels for P#{got_pid} "
				f"/ {e.__class__.__name__} {e.args}")


		# 6) STORE RATING
		try:
			rating = self._get_data_of_type(data, "rating")[0]["data"]
			if (rating):
				self.store_rating(got_pid, store_id, rating)
				self._logger.info(f"Created rating for P#{got_pid}")

			else: self._logger.debug(f"No rating for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create rating for P#{got_pid} "
				f"/ {e.__class__.__name__} {e.args}")

		# 7) STORE KEYWORDS
		try:
			keyword = self._get_data_of_type(data, "keywords")[0]["data"]
			if (keyword):
				self.store_keywords(got_pid, store_id, keyword)
				self._logger.info(f"Created keyword for P#{got_pid}")

			else: self._logger.debug(f"No rating for P#{got_pid}")
		except Exception as e:
			self._logger.error(f"Couldn't create keyword for P#{got_pid} "
				f"/ {e.__class__.__name__} {e.args}")


		self._logger.info(f"Completed storage of P#{got_pid} ({store}-{cin})")

		# DONE OMG
		return True


	async def _retrier(
			self, data: list[list[DSA]],
			coros: list[asyncio.Task[Any]], fetchid: str):
		"""
		`asyncio.gather` results of writer `Future`s.
		If any returned `False`, indicating failure, retry failed once each.
		"""

		results = await asyncio.gather(*coros)
		to_retry = results.count(False)

		if (to_retry == 0):
			self._logger.progress(f"Completed Fetch#{fetchid} slow.")
			return

		self._logger.warning(
			f"Retrying {to_retry} writes from Fetch#{fetchid}")

		last = 0
		for _ in range(to_retry):
			i = results.index(False, last)
			last = i

			await self.write_storable_group(data[i], True)

		self._logger.progress(f"Finished retries for Fetch#{fetchid}")





	async def write_from_search_results(
			self, data: list[list[DSA]], fetchid: str, slow: bool = False):

		if (slow):
			# NO RETRIER FOR slow MODE. ONLY PURPOSE FOR RETRIER IS
			# OVERLAP CAUSING ERRORS. NO OVERLAP WITH slow.

			for group in data: await self.write_storable_group(group)

			self._logger.progress(f"Completed Fetch#{fetchid} slow.")
			return

		coros: list[asyncio.Task[Any]] = []

		for group in data:
			coros.append(
				asyncio.create_task(self.write_storable_group(group)))

		# retrier USED FOR OVERLAP. EXAMPLE ISSUE THIS FIXES:
		# get_product_id -> get_brand_id returns None
		# so create_brand, but between SELECT and INSERT, another
		# product executed INSERT, causing this to fail.
		# RARE CIRCUMSTANCE, but worth having fallback.

		asyncio.create_task(self._retrier(data, coros, fetchid))
















