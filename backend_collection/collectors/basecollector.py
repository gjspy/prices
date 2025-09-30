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