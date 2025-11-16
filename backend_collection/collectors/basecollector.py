from concurrent.futures import ThreadPoolExecutor as TPE
from asyncio import get_running_loop
from functools import partial
from typing import Any
from requests import Response
import requests
import urllib
import time
import json
import re

from backend_collection.mytypes import Number, Result
from backend_collection.constants import (
	safe_deepget, regex, split_packsize_str, standardise_packsize)

async def async_executor(func: partial[Any]):
	loop = get_running_loop()

	with TPE() as pool:
		result = await loop.run_in_executor(pool, func)

	return result


class BaseCollector:
	def __init__(self):
		self.endpoint: str = NotImplemented
		self.results_path = NotImplemented
		self.store = NotImplemented

		self.http_method = NotImplemented


	async def _get(
			self, query_params: dict[str, str] = {}) -> Response:

		func = partial(requests.request,
			method = "GET",
			url = self.endpoint,
			params = query_params,
			headers = self.get_headers())

		result = await async_executor(func)

		return result


	async def _post(
			self, query_params: dict[str, str] = {},
			body: Result = {}) -> Response:

		func = partial(requests.request,
			method = "POST",
			url = self.endpoint,
			json = body,
			params = query_params,
			headers = self.get_headers())

		result = await async_executor(func)

		return result
	

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
		raise NotImplementedError

	def get_storable_from_result(self, result: Result) -> Result:
		raise NotImplementedError


	def parse_packsize(self, result: Result, product_name: str) -> tuple[int, Number, str]:
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


	def parse_data(self, data: Result) -> list[Result]:
		results: list[Result] | None
		results = safe_deepget(data, self.results_path)

		if (not results): return []

		clean_datas: list[Result] = []

		for result in results:
			#try:
				clean_datas.append(self.get_storable_from_result(result))
			#except Exception as err:
				#... # TODO LOG, FIGURE LOGGING OUT
			#	print(err,"err")
			
		return clean_datas
	

	async def search(self, query: str, debug: bool = False) -> list[Result]:
		result = None

		if (self.http_method == "POST"):
			req_body = self.get_postable_search_body(query)

			result = await self._post(body = req_body)
		
		if (self.http_method == "GET"):
			endpoint = self.get_sendable_search_params(query)

			result = await self._get()
		#data = result.json(kwds={"ensure_ascii": True}) # ensure_ascii so \u00a3 -> £ !!
		data = self._load_data_from_response(result)

		if (debug):
			with open(
				f"{self.store}DebugResponse_{int(time.time())}b.json", "wb"
			) as f: f.write(result.content)

			with open(
				f"{self.store}DebugResponse_{int(time.time())}t.json", "w"
			) as f: f.write(result.text)

			with open(
				f"{self.store}DebugResponse_{int(time.time())}j.json", "w"
			) as f: json.dump(data, f)

		storables = self.parse_data(data)

		return storables