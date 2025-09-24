from concurrent.futures import ThreadPoolExecutor as TPE
from asyncio import get_running_loop
from functools import partial
from typing import Any, Callable
from copy import deepcopy
from requests import Response
import requests
import json
import re

from constants import safe_deepget, int_safe, convert_str_to_pence, split_packsize


async def async_executor(func: partial[Any]):
	loop = get_running_loop()

	with TPE() as pool:
		result = await loop.run_in_executor(pool, func)

	return result


class BaseCollector:
	def __init__(self, config: dict[str, str]):
		self.endpoint: str = ""
		self.headers: dict[str, str] = {}



	async def _get(
			self, query_params: dict[str, str] = {}) -> Response:

		func = partial(requests.request,
			method = "GET",
			url = self.endpoint,
			params = query_params,
			headers = self.headers)

		result = await async_executor(func)

		return result


	async def _post(
			self, query_params: dict[str, str] = {},
			body: dict[str, Any] = {}) -> Response:

		func = partial(requests.request,
			method = "POST",
			url = self.endpoint,
			json = body,
			params = query_params,
			headers = self.headers)

		result = await async_executor(func)

		return result







	async def search(self, *args: Any, **kwargs: Any) -> Any:
		raise NotImplementedError

















class AlgoliaCollector(BaseCollector):
	def __init__(self, config: dict[str, str], algolia_index_name: str):

		super().__init__(config)

		self.endpoint = "https://8i6wskccnv-dsn.algolia.net/1/indexes/*/queries"
		self.headers = {
			"Accept": "*/*",
			"x-algolia-api-key": config["ASDA_ALGOLIA_API_KEY"],
			"x-algolia-application-id": config["ASDA_ALGOLIA_API_APP"]
		}

		self.algolia_index_name = algolia_index_name
		self._base_search_request = {
			"requests": [
				{
					"query": "[UNSET]",
					"indexName": algolia_index_name, # "ASDA_PRODUCTS"
					"clickAnalytics": False,
					"analytics": False,
					"hitsPerPage": 100,
					"page": 0,
					"typoTolerance": True,
					"removeWordsIfNoResults": "allOptional",
					"attributesToRetrieve": [
						"STATUS",
						"BRAND",
						"CIN",
						"NAME",
						"AVG_RATING",
						"RATING_COUNT",
						"ICONS",
						"PRICES.EN",
						"SALES_TYPE",
						"MAX_QTY",
						"STOCK.4565",
						"IS_FROZEN",
						"IS_BWS",
						"PROMOS.EN",
						"LABEL",
						"LABEL_START_DATE",
						"LABEL_END_DATE",
						"IS_SPONSORED",
						"PRODUCT_TYPE",
						"CIN_ID",
						"PRIMARY_TAXONOMY",
						"IMAGE_ID",
						"PACK_SIZE",
						"PHARMACY_RESTRICTED",
						"CS_YES",
						"CS_TEXT",
						"IS_FTO",
						"PURCHASE_START_DATE_FTO",
						"PURCHASE_END_DATE_FTO",
						"DELIVERY_SLOT_START_DATE_FTO",
						"END_DATE",
						"START_DATE",
						"SIZE_DESC",
						"REWARDS",
						"SHOW_PRICE_CS",
						"ID"
					]
				}
			]
		}

		self.results_path = ["results", 0, "hits"]
		self.prices_from_result = ["PRICES", "EN"]
		self.promo_from_result = ["PROMO", "EN", 0]


	def get_sendable_search_request(
			self, query: str) -> dict[str, Any]:
		v = deepcopy(self._base_search_request)
		v["requests"][0]["query"] = query

		return v

	def parse_packsize(self, packsize: str) -> tuple[int, int | float, str]:
		packsize = packsize.upper()

		multi = re.search(r"([\d\.]+)X([\d\.]+)([A-z]*)", packsize)
		if (multi):
			count, size_each, unit = multi.groups()

			if (unit): # THEY GIVE "2L" OR "8X330". NO UNIT ON MULTIs. IN ADMIN PANEL, WRITE THEM.
				size_, unit_ = split_packsize(size_each, unit)
				return (int(count), size_, unit_)


		size, unit = split_packsize(packsize)
		if (size != -1): return (1, size, unit)

		return (0, -1, "")
	


	def get_storable_from_result(self, result: dict[str, Any]) -> dict[str, Any]:
		prices_data: dict[str, str] | None = safe_deepget(result, self.prices_from_result)
		promo_data: dict[str, str] | None = safe_deepget(result, self.promo_from_result)
		offer = {}

		if (prices_data):
			offer_type = prices_data.get("OFFER")

			if (offer_type and offer_type != "List"):
				# Rollback, Dropped
				offer = {
					"offer": prices_data["OFFER"],
					"was_price": prices_data["WASPRICE"]
				}

		elif (promo_data):
			offer_value = promo_data["NAME"]
			match = re.match(r"Any (\d+) for ((?:£\d+\.\d+)|(?:£\d+)|(?:\d+p))", offer_value)

			if (match):
				groups = match.groups()

				offer = {
					"offer": "_AnyFor",
					"any_count": int(groups[0]),
					"for_price": convert_str_to_pence(groups[1]),
					"id": promo_data["ID"] # CAN MIX AND MATCH OTHER PRODUCTS
				}
			else: print("NO MATCH FOR ANY X FOR X", offer_value)



		return {
			"product": {
				"upc": int_safe(result["IMAGE_ID"]),
				"brand_name": result["BRAND"],
				"name": result["NAME"],
				"pack_size": result["PACK_SIZE"],
			},
			"price": {
				"price_pence": int(result["PRICES"]["EN"]["Price"]) * 100,
				"was_price": result["PRICES"]["EN"].get("WASPRICE"),
				"available": result["STATUS"] == "A" # NOT STOCK LEVELS. THEY'RE PER STORE.
			},
			"offer": offer,
			"rating": {
				"avg": result["AVG_RATING"],
				"count": result["RATING_COUNT"]
			},
			"category": {
				"category": result["PRIMARY_TAXONOMY"]["CAT_NAME"], # eg Chilled Food
				"department": result["PRIMARY_TAXONOMY"]["DEPT_NAME"] # eg Cheese
				# also has aisle [Cheddar & Regional Cheese]
				# and shelf [Mature Cheese] but thats too granular
			}
		}


	def parse_data(self, data: dict[str, Any]) -> list[dict[str, Any]]:
		results: list[dict[str, Any]] | None
		results = safe_deepget(data, self.results_path)

		if (not results): return ...

		clean_datas: list[dict[str, Any]] = []

		for result in results:
			try:
				clean_datas.append(self.get_storable_from_result(result))
			except Exception as err:
				... # LOG, FIGURE LOGGING OUT
				print(err)
			
		return clean_datas
			




	async def search(self, query: str) -> list[dict[str, Any]]:
		req_body = self.get_sendable_search_request(query)

		result = await self._post(body = req_body)
		data = result.json()

		storables = self.parse_data(data)

		return storables
