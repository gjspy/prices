from dbmanager.engine import Database, MATCH, Join, TableRow, MAX, ColumnType, JoinInlineTable

from backend.log_handler import get_logger, CustomLogger
from backend.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores, Offers, OfferHolders, Labels, Keywords,

	Store, Product, Brand, PriceEntry, Image)

from backend.api.constants import SortOption
from backend.constants import DATE_FMT
from backend.types import Optional, DSA, DIS, DII, Any

SEARCH_N_RESULTS = 20

FAVOURITE_STORES_FOR_IMAGES = [] # TODO?



def make_product_transferrable(product: Product) -> DSA:
	return {
		"n": product.name.plain_value,
		"b": product.brand.ref_value(Brand).brand_name.plain_value,
		"psc": product.packsize_count.plain_value,
		"pss": product.packsize_sizeeach.plain_value,
		"psu": product.packsize_unit.plain_value,
		"p": [],
		"i": []
	}


def make_price_transferrable(sid_to_name: DIS, price: PriceEntry) -> Optional[DSA]:
	store_id = price.store.ref_value(Store).db_id.plain_value
	if (not store_id): return

	t = price.fetched_time.plain_value
	if (t is not None): t = t.strftime(DATE_FMT)

	return {
		"s": sid_to_name[store_id],
		"t": t,
		"p": price.price_pence.plain_value,
		"a": price.available.plain_value
	}



def build_search_query(query: str, page: int, sort_mode: SortOption):
	products_fulltext = MATCH(Products.row.name, query)
	products_fulltextr = products_fulltext.as_column("PScore")

	brands_fulltext = MATCH(Brands.row.brand_name, query)
	brands_fulltextr = brands_fulltext.as_column("BScore")
	
	q = Products.select(
		[
			Products.row.db_id,
			Products.row.name,
			Products.row.packsize_count,
			Products.row.packsize_sizeeach,
			Products.row.packsize_unit,
			Brands.row.brand_name, # DOES NOT join Parent here.
			products_fulltextr,
			brands_fulltextr
		],
		join_on = [Join(Brands, Brands.row.db_id == Products.row.brand)],
		where = products_fulltext | brands_fulltext,
		order_by = [(products_fulltextr + brands_fulltextr).descending,],
		limit = SEARCH_N_RESULTS,
		page = page,
		objectify_results=True
	)

	return q
	print(q)


def build_prices_query(product_ids: list[int], include_fetch_date: bool = False):
	inner_max = MAX(PriceEntries.row.fetched_time).as_column("LatestFetch")
	latest = PriceEntries.as_alias("LatestRows", True)

	inner = PriceEntries.select(
		[
			latest.row.db_id,
			latest.row.product,
			latest.row.store,
			inner_max
		],
		where = latest.row.product.in_(product_ids),
		group_by = [latest.row.product, latest.row.store],
		is_inline = True
	)


	inline = JoinInlineTable(
		inner, latest, PriceEntries.row.db_id == latest.row.db_id, "INNER" )

	get_cols: list[ColumnType] = [
		PriceEntries.row.product,
		PriceEntries.row.store,
		PriceEntries.row.price_pence,
		PriceEntries.row.available
	]
	if (include_fetch_date): get_cols.append(PriceEntries.row.fetched_time)	

	outer = PriceEntries.select(
		get_cols,
		join_on = [inline]
	)

	return outer


def build_images_query(product_ids: list[int]):
	q = Images.select(
		[
			Images.row.db_id,
			Images.row.product,
			Images.row.preferred
		],
		where = Images.row.product.in_(product_ids)
	)

	return q


def choose_images_per_pid(images: list[Image], product_ids: list[int]):
	response: DII = {}
	is_preferred: dict[int, Optional[bool]] = {}

	for image in images:
		pid = image.product.ref_value(Product).db_id.plain_value
		if (pid is None): continue

		current = response.get(pid)
		if (current is not None and is_preferred.get(pid)): continue
		
		response[pid] = image.db_id.plain_value # type: ignore
		is_preferred[pid] = image.preferred.plain_value

	return response


	


async def search(db: Database, sid_to_name: DIS, query: str, page: int, sort_mode: SortOption) -> list[DSA]:
	q = build_search_query(query, page, sort_mode)

	r = await db.execute_payload_async(q)
	products: Optional[list[dict[str, Product]]] = r.get("fetchall")

	if (not products): return []

	product_ids: list[int] = []
	product_data: dict[int, DSA] = {}

	for v in products:
		prod = v["Products"]
		pid = prod.db_id.plain_value

		if (pid is None): continue

		product_ids.append(pid)
		product_data[pid] = make_product_transferrable(prod)

	if (len(product_ids) == 0): return [] # TODO: log, query error

	q2 = build_images_query(product_ids)
	
	r2 = await db.execute_payload_async(q2)
	images: Optional[list[Image]] = r2.get("fetchall")

	image_datas = ( choose_images_per_pid(images, product_ids)
		if (images) else {} )
	
	for i,v in image_datas.items(): product_data[i]["i"].append(v)

	q3 = build_prices_query(product_ids, False)

	r3 = await db.execute_payload_async(q3)
	prices: Optional[list[PriceEntry]] = r3.get("fetchall")
	
	if (not prices): return list(product_data.values())
	
	for v in prices:
		pid = v.product.ref_value(Product).db_id.plain_value
		
		if (pid is None): continue
		data = make_price_transferrable(sid_to_name, v)

		product_data[pid]["p"].append(data)
	
	return list(product_data.values())