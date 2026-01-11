from concurrent.futures import ThreadPoolExecutor as TPE
#from urllib import parse as urlparse
from asyncio import get_running_loop
from functools import partial
from typing import Any, Optional
from requests import Response
import requests
import time
import json
import re


from backend_collection.mytypes import Number, DSA
from backend_collection.constants import (
	safe_deepget, regex, split_packsize_str, standardise_packsize,
	stringify_query)
from backend_collection.promo_processor2 import PromoProcessor


# WE HAVE EXECUTOR AS requests IS NOT NATIVELY ASYNCHRONOUS.
async def async_executor(func: partial[Any]):
	loop = get_running_loop()

	with TPE() as pool:
		result = await loop.run_in_executor(pool, func)

	return result


class BaseCollector:
	_HEADERS: dict[str, str] = {}

	PromoProcessor: type[PromoProcessor]

	endpoint: str
	store: str
	http_method: str

	_path_results_from_resp: list[Any]
	_path_promos_from_result: list[Any]

	async def __request(self, options: DSA):
		if (not self._cfwt):
			p = options.get("p") or ""

			func = partial(requests.request,
				method = options["m"],
				url = self.endpoint + (f"?{p}" if p else ""),
				headers = options.get("h"),
				json = options.get("b"))

			result = await async_executor(func)
			return result
		
		b = options.get("b")
		d = {
			"s": self.__cfws,
			"i": self.__cfwe,
			"p": options.get("p"),
			"h": options.get("h"),
			"m": options.get("m"),
			"b": json.dumps(b) if b else None
		}

		f = partial(requests.request,
			method = "POST",
			url = self.__cfww,
			json = d,
			headers =  self.__cfwa)
		
		result = await async_executor(f)
		return result


	async def _get(
			self, query_params: dict[str, str] = {}) -> Response:
		
		r = await self.__request({
			"m": "GET",
			"h": self.get_headers(),
			"p": stringify_query(query_params)
		})

		return r


	async def _post(
			self, query_params: dict[str, str] = {},
			body: DSA = {}) -> Response:

		r = await self.__request({
			"m": "POST",
			"h": self.get_headers(),
			"p": stringify_query(query_params),
			"b": body
		})

		return r
	

	def _compute_cfw_e(self, env: DSA):
		try:
			self.__cfwe = json.loads(env["CFW_E"]).index(self.endpoint)
			self.__cfws = env["CFW_S"]
			self.__cfwa = json.loads(env["CFW_A"])
			self.__cfww = env["CFW"]
			self._cfwt = True
		except Exception as err:
			err.add_note("FATAL: COULD NOT COMPUTE CFW")
			raise err


	def _load_data_from_response(self, response: requests.Response):
		"""
		Use this method to control how JSON data is loaded,
		instead of using `Response.json()`

		Included to reduce issues with response text encoding.
		Not sure if it's an issue anymore, this may be redundant?

		Original observed issue: '\\u00a3' -> '£'
		"""

		content = response.content # RAW BYTES
		return json.loads(content)

		


	def get_postable_search_body(self, query: str) -> Any:
		raise NotImplementedError
	
	def get_gettable_search_params(self, query: str) -> Any:
		raise NotImplementedError
	


	def get_headers(self) -> dict[str, str]:
		return self._HEADERS

	def get_storables_from_result(self, result: DSA) -> list[DSA]:
		raise NotImplementedError
	
	def find_price_matches(self, result: DSA) -> list[DSA]:
		raise NotImplementedError


	def parse_packsize(
			self, result: DSA, product_name: str) -> tuple[int, Number, str]:
		"""
		This method parses all possible methods of finding PACKSIZE and
		decides which one to keep.
		"""
		
		raise NotImplementedError
	

	def _parse_packsize_str(self, packsize: str) -> tuple[int, Number, str]:
		"""
		This method parses an individual PACKSIZE string, to separate values:

		Returns
		----
		tuple[int, float | int, str]:
			*format: (count, size_each, unit)*
			- count: number of items
			- size_each: size of each item formatted to standard unit
			- standard unit used

			**Invalid inputs do not error, they return (0, -1, "")**
		"""

		if (not packsize): return (0, -1, "")
		packsize = packsize.lower() # STANDARD: LOWERCASE

		multi = re.search(regex.PACKSIZE_MULTIPLE, packsize)

		if (multi):
			count, size_each, unit = multi.groups()

			if (unit):
				print("unit", unit)
				# TODO THEY GIVE "2L" OR "8X330".
				# NO UNIT ON MULTIs. IN ADMIN PANEL, WRITE THEM.
				size_each, unit = standardise_packsize(size_each, unit)
				return (int(count), size_each, unit)
			
			return (int(count), float(size_each), "")


		size, unit = split_packsize_str(packsize)
		if (size != -1): return (1, size, unit)

		return (0, -1, "")


	def parse_data(self, data: DSA) -> list[list[DSA]]:
		results: list[DSA] | None
		results = safe_deepget(data, self._path_results_from_resp)

		if (not results): return []

		clean_datas: list[list[DSA]] = []

		for result in results:
			#try:
				clean_datas.append(self.get_storables_from_result(result))
			#except Exception as err:
				#... # TODO LOG, FIGURE LOGGING OUT
			#	print(err,"err")

		return clean_datas

	def process_promos(self, data: DSA):
		gathered_promos: list[DSA] = []

		promotions: list[DSA] = safe_deepget(
			data, self._path_promos_from_result)

		for promo in (promotions or []):
			processor = self.PromoProcessor(data, promo)

			try: promo = processor.process_promo()
			except: pass
			else: gathered_promos.append(promo)
		
		# RUN ENTIRE
		#processor = self.PromoProcessor(data, {})
		#other = processor.run_entire_checks()

		#if (other): gathered_promos = [*gathered_promos, *other]

		return gathered_promos
	

	def _build_storables(
			self, 
			product_name: Optional[str], 
			brand_name: Optional[str], 
			ps_count: Optional[int],
			ps_sizeeach: Optional[Number], 
			ps_unit: Optional[str], 
			thumb: Optional[str], 
			upcs: Optional[list[int]], 
			cin: Optional[int],
			price_pence: Optional[int], 
			is_available: Optional[bool], 
			rating_avg: Optional[float],
			rating_count: Optional[int], 
			category: Optional[str], 
			dept: Optional[str],
			promos: Optional[list[DSA]], 
			labels: Optional[list[DSA]]) -> list[DSA]:
		""" Creates `dict` objects ready for databse storage. """
		
		product = {
			"type": "product",
			"data": {
				"name": product_name,
				"brand_name": brand_name,
				"packsize": {
					"count": ps_count,
					"sizeeach": ps_sizeeach,
					"unit": ps_unit
				}
			}
		}

		image = {
			"type": "image",
			"data": { "url": thumb, "store_name": self.store }
		}

		links = [{
			"type": "link",
			"data": { "upc": upc, "store_name": self.store, "cin": cin }
		} for upc in upcs] if (upcs) else []

		price = {
			"type": "price",
			"data": {
				"price_pence": price_pence,
				"available": is_available,
				"store_name": self.store
			}
		}

		rating = {
			"type": "rating",
			"data": {
				"avg": rating_avg,
				"count": rating_count,
				"store_name": self.store
			}
		}

		cat = {
			"category": category,
			"department": dept,
			"store_name": self.store
		}

		promo_objs = [ { "type": "offer", "data": v } for v in (promos or []) ]
		label_objs = [ { "type": "label", "data": v } for v in (labels or []) ]

		return [
			product, image, price, rating, cat,
			*links, *promo_objs, *label_objs
		]



	async def search(self, query: str, debug: bool = False) -> list[list[DSA]]:
		result = None

		if (self.http_method == "POST"):
			req_body = self.get_postable_search_body(query)

			result = await self._post(body = req_body)
		
		if (self.http_method == "GET"):
			endpoint = self.get_gettable_search_params(query)

			result = await self._get(endpoint)
		#data = result.json(kwds={"ensure_ascii": True}) # ensure_ascii so \u00a3 -> £ !!

		if (result == None):
			raise ValueError("HTTP_METHOD INVALID")
		
		data = None

		try:
			data = self._load_data_from_response(result)
		except Exception as err:
			print("error loading JSON from response", err)

		if (debug):
			with open(
				f"{self.store}DebugResponse_{int(time.time())}j.json", "w"
			) as f: json.dump(data, f)
		
		if (not data): return []

		storables = self.parse_data(data)

		return storables