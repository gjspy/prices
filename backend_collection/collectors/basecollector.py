from concurrent.futures import ThreadPoolExecutor as TPE
from asyncio import get_running_loop
from functools import partial
from typing import Any, Callable
from copy import deepcopy
from requests import Response
import requests
import json

from constants import safe_deepget


async def async_executor(func: partial[Any]):
	loop = get_running_loop()

	with TPE() as pool:
		result = await loop.run_in_executor(pool, func)
	
	return result

def create_partial(func: Callable[Any, Any], *args, **kwargs)


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

	
	def get_sendable_search_request(
			self, query: str) -> dict[str, Any]:
		v = deepcopy(self._base_search_request)
		v["requests"][0]["query"] = query

		return v
	
	def parse_data(self, data: dict[str, Any]):
		results: list[dict[str, Any]] | None
		results = safe_deepget(data, self.results_path)

		if (not results): return ...

		clean_datas = []

		
	

	async def search(self, query: str):
		req_body = self.get_sendable_search_request(query)

		result = await self._post(body = req_body)
		data = result.json()





