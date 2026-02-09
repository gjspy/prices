from functools import partial
from requests import Response
import requests
import time
import json
import re
import os


from backend.types import Any, Optional, Number, DSA
from backend.collector.promo_processor import PromoProcessor
from backend.log_handler import CustomLogger
from backend.constants import (
	safe_deepget, regex, standardise_packsize,
	stringify_query, async_executor, DATE_FMT, utcnow)


class BaseCollector:
	DEBUG_FILE_DIR = "debug"
	_HEADERS: dict[str, str] = {}

	PromoProcessor: type[PromoProcessor]

	endpoint: str
	store: str
	http_method: str

	# FOR HTTP "GET", WHEN CREATING STRING QUERY PARAMS, WHETHER TO HAVE
	# "q='cheese'&limit=60" OR "q=cheese&limit=60"
	_get_query_remove_quotes = False 

	_path_results_from_resp: list[Any]
	_path_promos_from_result: list[Any]

	def __init__(
			self, logger: CustomLogger, env: DSA,
			config: DSA, results_per_search: int):

		self._logger = logger
		self.results_per_search = results_per_search
		self._compute_cfw_e(env)

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
		
		self._logger.add_to_stats(f"NETWORKREQ{self.store}")
		
		result = await async_executor(f)
		return result


	async def _get(
			self, query_params: dict[str, str] = {}) -> Response:
		
		r = await self.__request({
			"m": "GET",
			"h": self.get_headers(),
			"p": stringify_query(query_params, self._get_query_remove_quotes)
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
	

	def _parse_packsize_str(self, packsize: Optional[str]) -> tuple[int, Number, str]:
		"""
		This method parses an individual PACKSIZE string, to separate values:

		Returns
		----
		tuple[int, float | int, str]:
			*format: (count, size_each, unit)*
			- count: number of items
			- size_each: size of each item formatted to standard unit
			- standard unit used

			**Invalid inputs do not error, they return (0, 0, "")**
		"""
		if (not packsize): return (0, 0, "")
		packsize = packsize.replace(",", "")

		multi = re.search(regex.PACKSIZE_MULTI, packsize, flags = re.IGNORECASE)

		if (multi):
			groups = multi.groups()

			data: DSA = {}

			for i, k in enumerate(regex.PACKSIZE_MULTI_GROUPS):
				if (k == "_"): continue
				if (data.get(k) is not None): continue

				data[k] = groups[i]
			
			count = data.get("c") or 0
			size_each = data.get("s") or 0
			unit = data.get("u")

			if (unit):
				size_each, unit = standardise_packsize(size_each, unit)
				return (int(count), size_each, unit)
			
			return (int(count), float(size_each), "")

		match = re.search(regex.PACKSIZE_SINGLE, packsize, flags = re.IGNORECASE)
		if (not match): return (0, 0, "")

		size_, unit_ = match.groups()
		if (not size_ or not unit_): return (0, 0, "")
		
		size, unit = standardise_packsize(size_, unit_)
		if (size != 0): return (1, size, unit)

		return (0, 0, "")


	def parse_data(self, data: DSA) -> list[list[DSA]]:
		results: Optional[list[DSA]]
		results = safe_deepget(data, self._path_results_from_resp)

		if (not results): return []

		clean_datas: list[list[DSA]] = []

		for result in results:
			try:
				clean_datas.append(self.get_storables_from_result(result))
			except:
				self._logger.exception(
					f"COULD NOT GATHER PRODUCT DATA. {self.store}. "
					f"Continuing with parse_data for {self.store}, "
					"this has been caught.")

		return clean_datas

	def process_promos(self, data: DSA):
		gathered_promos: list[DSA] = []

		promotions: list[DSA] = safe_deepget(
			data, self._path_promos_from_result)

		for promo in (promotions or []):
			processor = self.PromoProcessor(data, promo)

			try:
				promo = processor.process_promo()
			except Exception as e: 
				self._logger.error(f"ERROR GETTING PROMO DATA {promo} / {e}")
			else: 
				gathered_promos.append(promo)

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
				"packsize_count": ps_count,
				"packsize_sizeeach": ps_sizeeach,
				"packsize_unit": ps_unit
			}
		}

		image = {
			"type": "image",
			"data": { "url": thumb }
		}

		links = [{
			"type": "link",
			"data": { "upc": upc, "store_name": self.store, "cin": cin }
		} for upc in upcs] if (upcs) else [{
			"type": "link",
			"data": { "store_name": self.store, "cin": cin }
		}]

		price = {
			"type": "price",
			"data": {
				"price_pence": price_pence,
				"available": is_available
			}
		}

		rating = {
			"type": "rating",
			"data": {
				"avg": rating_avg,
				"count": rating_count
			}
		}

		kwrd = category if (category is not None) else ""
		if (dept is not None): kwrd += f" {dept}"

		kwrds = [{
			"type": "keywords",
			"data": { "value": kwrd }
		}] if (kwrd) else []

		promo_objs = [ { "type": "offer", "data": v } for v in (promos or []) ]
		label_objs = [ { "type": "label", "data": v } for v in (labels or []) ]

		return [
			product, image, price, rating,
			*links, *promo_objs, *label_objs, *kwrds
		]



	async def search(self, query: str, debug: bool = False) -> list[list[DSA]]:
		result = None

		if (self.http_method == "POST"):
			req_body = self.get_postable_search_body(query)

			result = await self._post(body = req_body)
		
		if (self.http_method == "GET"):
			params = self.get_gettable_search_params(query)

			result = await self._get(params)

		if (result == None): raise ValueError("HTTP_METHOD INVALID")
		
		data = None

		try:
			data = self._load_data_from_response(result)
		except:
			self._logger.exception("COULD NOT LOAD JSON FROM RESP")

		now = utcnow().strftime(DATE_FMT)

		if (debug):
			path = os.path.join(self.DEBUG_FILE_DIR,
				f"{now}_{self.store}_SEARCH_{query}.json" )

			with open(path, "w") as f: json.dump(data, f, default = str)
		
		if (not data): return []

		storables = self.parse_data(data)

		if (debug):
			path = os.path.join(self.DEBUG_FILE_DIR,
				f"{now}_{self.store}_SEARCH_{query}_GATHERED.json")
			
			with open(path, "w") as f: json.dump(storables, f, default = str)

		return storables