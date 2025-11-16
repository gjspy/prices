from copy import deepcopy
import urllib
import re


from backend_collection.collectors.basecollector import BaseCollector
from backend_collection.mytypes import Result
from backend_collection.constants import (
	safe_deepget, int_safe, convert_str_to_pence, dict_add_values, 
	clean_product_name, standardise_packsize, regex)


class ClusterCollector(BaseCollector):
	def __init__(
			self, config: Result, endpoint: str,
			store: str, results_per_search: int):
		
		super().__init__()

		self.endpoint = endpoint
		self.__HEADERS = {
			"Accept": "application/json"
		}
		self.http_method = "GET"

		self.store = store
		self.results_per_search = results_per_search
		
	def get_gettable_search_params(self, query: str):
		return {
			"includeAdditionalPageInfo": "false",
			"maxProductsToDecorate": self.results_per_search,
			"q": query
		}
	

	def process_promo(self, result: Result) -> Result:...


	def parse_packsize(self, result: Result, product_name: str):...

	def get_storable_from_result(self, result: Result) -> Result:...