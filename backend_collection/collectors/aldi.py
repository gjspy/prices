from typing import Any, Callable
from copy import deepcopy
from uuid import uuid4


from backend_collection.collectors.basecollector import BaseCollector
from backend_collection.types import DSA, Result, SDG_Key
from backend_collection.constants import (
	safe_deepget, int_safe, convert_str_to_pence, 
	clean_product_name, standardise_packsize, regex, OFFER_TYPES, StoreNames)


# ALDI ARE THE OPPOSITE OF TRYHARDS
# THEY DON'T HAVE PROMOS (OR JUST NOT SHOWN ON SITE?)

class ALDCollector(BaseCollector):
	# NO PromoProcessor

	store = StoreNames.aldi
	endpoint = "https://api.aldi.co.uk/v3/product-search"
	http_method = "GET"
	_get_query_remove_quotes = True
	
	_path_results_from_resp = ["data"]

	_path_category_from_result = ["categories", 0, "name"]
	_path_dept_from_result = ["categories", 1, "name"]
	

	def __init__(self, env: DSA, config: DSA, results_per_search: int):
		self._HEADERS = {
			"Accept": "application/json"
		}
		self._compute_cfw_e(env)
		print("CFW OFF TEMP")
		self._cfwt = False

		self.results_per_search = results_per_search

	def get_gettable_search_params(self, query: str):
		return {
			"currency": "GBP",
			"serviceType": "walk-in",
			"q": query,
			"limit": self.results_per_search,
		}
	
		#https://api.aldi.co.uk/v3/product-search?currency=GBP&serviceType=walk-in&q=cheese&limit=30&offset=0&sort=relevance&servicePoint=C092

	def parse_packsize(self, result: DSA, product_name: str):
		"""
		Name does not have packsize (is clean!!)
		So can get only from sellingSize field.
		"""

		return self._parse_packsize_str(result.get("sellingSize"))

	def get_storables_from_result(self, result: DSA) -> list[DSA]:
		brand_name = result.get("brandName") or ""
		name = result.get("name") or ""

		sale_data: DSA = result.get("price") or {}
		price: int | None = sale_data.get("amount")
		if (not price): return []

		count, size_each, unit = self.parse_packsize(result, name)

		assets: list[DSA] = result.get("assets") or []
		img = ""
		if (len(assets) > 0):
			data = assets[0]

			max_wid = data.get("maxWidth") or 1000
			img = (data.get("url") or "").format(width = max_wid, slug = "")

		category = safe_deepget(result, self._path_category_from_result)
		dept = safe_deepget(result, self._path_dept_from_result)

		return self._build_storables(
			product_name = clean_product_name(name, brand_name),
			brand_name = brand_name,
			ps_count = count, # ONLY IN TITLE.
			ps_sizeeach = size_each,
			ps_unit = unit,
			thumb = img, # HAS ICONS :( # TODO: STANDARDISE IMAGE SIZE. TESCO HAVE ?h=x&w=x, ASDA?
			upcs = None,
			cin = int_safe(result.get("sku")),
			price_pence = price,
			is_available = not result.get("discontinued"), # FIELD = False, IF NONE ASSUME ITS AVAILABLE.
			rating_avg = None,
			rating_count = None,
			category = category,
			dept = dept,
			promos = None,
			labels = None
		)