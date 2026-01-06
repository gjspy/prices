from copy import deepcopy
import urllib
import re
from uuid import uuid4
import time


from backend_collection.collectors.basecollector import BaseCollector
from backend_collection.mytypes import Result
from backend_collection.constants import (
	safe_deepget, int_safe, convert_str_to_pence, dict_add_values, 
	clean_product_name, standardise_packsize, regex)


class AKMCollector(BaseCollector):
	def __init__(
			self, env: Result, config: Result, endpoint: str,
			store: str, results_per_search: int):
		
		super().__init__()

		self.endpoint = endpoint
		self.__HEADERS = {
			"Accept": "application/json",
			"User-Agent": "Chrome/143.0.0.0"
		}
		self.http_method = "GET"
		self._compute_cfw_e(env)
		self._cfwt = False # akamai IS API SECURITY ORG. WILL NEVER WORK.

		self.store = store
		self.results_per_search = results_per_search

		self.results_path = ["products"]
		self.best_category_path = ["categories", 0, "name"]
		self.promo_original_price_path = ["promotions", 0, "original_price"]

		# INFO IN get_headers DOCSTRING.
		#self.headers_traceparent_format = "00-{traceid}-{parent}-01"
		#self.headers_tracestate_format = "2092320@nr=0-1-1782819-181742266-{parent}----{timestamp}"

	def get_headers(self):
		# TODO: randomise user-agent?
		
		return self.__HEADERS
		
	def get_gettable_search_params(self, query: str):
		return {
			"filter[keyword]": query,
			"page_size": self.results_per_search,
		}


	def process_promo(self, result: Result, specific_promo: Result) -> Result:
		promo_id = specific_promo.get("promotion_uid")
		promo_description: str | None = specific_promo.get("strap_line")

		if ((not promo_id) or (not promo_description)): return {}

		formatted_data = {
			"start_date": specific_promo.get("start_date"),
			"end_date": specific_promo.get("end_date"),
			"requires_membership": bool(specific_promo.get("is_nectar")),
			"store_given_id": specific_promo.get("promotion_id")
		}

		# "Buy x for y"
		multibuy_match = re.match(regex.MULTIBUY, promo_description.lower())

		if (multibuy_match):
			groups = multibuy_match.groups()

			return {
				"offer_type": "_Reduction",
				
			}



	def parse_packsize(self, result: Result, product_name: str):
		"""
		This method parses all possible methods of finding PACKSIZE and
		decides which one to keep.

		No field here, so just name.
		"""

		return self._parse_packsize_str(product_name)
	

	def get_storables_from_result(self, result: Result) -> list[Result]:
		name = result.get("name") or ""
		img = result.get("image") or ""
		# NO BRAND NAME FIELD :(
		
		count, size_each, unit = self.parse_packsize(result, name)

		# RETAIL_PRICE IS DISCOUNTED. NEED TO DIG FOR ORIGINAL :(

		price_data: Result = result.get("retail_price") or {}
		promo_original: int = safe_deepget(result, self.promo_original_price_path)
		rating_data: Result = result.get("reviews") or {}

		price = promo_original or price_data.get("price")
		price_pence = price * 100 if (price) else -1

		eans: list[str] = result.get("eans") or []
		cin = result.get("product_uid")

		promotions: list[Result] = result.get("promotions") or []

		return [
			{
				"type": "product",
				"data": {
					#"brand_name": ,
					"name": clean_product_name(name),
					"packsize": {
						"count": count,
						"sizeeach": size_each,
						"unit": unit
					}
				}
			},
			{
				"type": "image",
				"data": {
					"url": img
				}
			},
			*({
				"type": "link",
				"data": {
					"upc": ean,
					"store": self.store,
					"cin": cin
				}
			} for ean in eans),
			*({
				"type": "offer",
				"data": self.process_promo(result, this_promo)
			} for this_promo in promotions),
			{
				"type": "price",
				"data": {
					"price_pence": price_pence,
					# "available" IS NOT STOCK LEVELS. THEY'RE PER STORE.
					"available": result.get("is_available") == True
				}
			},
			{
				"type": "rating",
				"data": {
					"avg": rating_data.get("average_rating"),
					"count": rating_data.get("total")
				}
			},
			{
				"type": "category",
				"data": {
					# ALL THEIR CATEGORIES ARE WASHY AND VAGUE. JUST TAKE FIRST ONE.
					"category": safe_deepget(result, self.best_category_path)
				}
			}
		]
	




"""
unused code for headers. they don't need trace values, just wanted a user-agent :)

		Need to generate trace values for this store!

		trace fields follow W3C Trace Context: 
		- traceparent: "version-traceid-parentid-flags"
		- tracestate: more vague, vendor-specific flags, we don't care


		traceparent_trace = uuid4().hex
		traceparent_parent = uuid4().hex[:16]
		
		headers["traceparent"] = self.headers_traceparent_format.format(
			traceid = traceparent_trace,
			parent = traceparent_parent)
		
		headers["tracestate"] = self.headers_tracestate_format.format(
			parent = traceparent_parent,
			timestamp = int(time.time() * 1000))s

"""