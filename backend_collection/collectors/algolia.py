from copy import deepcopy
from typing import Any
import re


from basecollector import BaseCollector
from constants import safe_deepget, int_safe, convert_str_to_pence, split_packsize


class AlgoliaCollector(BaseCollector):
	def __init__(self, config: dict[str, str], algolia_index_name: str, store: str):

		super().__init__(config)

		self.endpoint = "https://8i6wskccnv-dsn.algolia.net/1/indexes/*/queries"
		self.headers = {
			"Accept": "*/*",
			"x-algolia-api-key": config["ASDA_ALGOLIA_API_KEY"],
			"x-algolia-application-id": config["ASDA_ALGOLIA_API_APP"]
		}

		self.store = store
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


	def process_promo(self, result: dict[str, Any]) -> dict[str, Any]:
		prices_data: dict[str, str] | None = safe_deepget(result, self.prices_from_result)

		if (prices_data):
			offer_type = prices_data.get("OFFER")

			if (offer_type and offer_type != "List"):
				# Rollback, Dropped
				return {
					"offer_type": prices_data["OFFER"],
					"was_price": prices_data["WASPRICE"] * 100
				}
		
		# TODO CAN THEY DO ROLLBACK AND ANY X FOR????
		promo_data: dict[str, str] | None = safe_deepget(result, self.promo_from_result)

		if (not promo_data): return {}
		
		offer_value = promo_data["NAME"]

		# IS "Any X for £X"
		match = re.match(r"Any (\d+) for ((?:£\d+\.\d+)|(?:£\d+)|(?:\d+p))", offer_value) # TYPE 15

		if (match):
			groups = match.groups()

			return {
				"offer_type": "_AnyFor",
				"any_count": int(groups[0]),
				"for_price": convert_str_to_pence(groups[1]),
				"store_given_id": promo_data["ID"] # CAN MIX AND MATCH OTHER PRODUCTS
			}
		
		# TODO: REFER BY TYPE
		# PROMOS.EN.TYPE
		#	= 15 -> Any X
		#	= 12 -> Meal Deal
		
		# TODO: LOG THIS
		return {
			"offer_type": offer_value,
			"start_date": promo_data.get("START_DATE"),
			"end_date": promo_data.get("END_DATE"), # TODO: THESE ARE UNIX STAMPS.
			"store_given_id": promo_data.get("ID")
		}


	def parse_packsize(self, packsize: str) -> tuple[int, int | float, str]:
		packsize = packsize.upper()

		multi = re.search(r"([\d\.]+)X([\d\.]+)([A-z]*)", packsize)
		if (multi):
			count, size_each, unit = multi.groups()

			if (unit): # TODO THEY GIVE "2L" OR "8X330". NO UNIT ON MULTIs. IN ADMIN PANEL, WRITE THEM.
				size_, unit_ = split_packsize(size_each, unit)
				return (int(count), size_, unit_)
			
			return (int(count), float(size_each), "")


		size, unit = split_packsize(packsize)
		if (size != -1): return (1, size, unit)

		return (0, -1, "")
	


	def get_storable_from_result(self, result: dict[str, Any]) -> dict[str, Any]:
		count, size_each, unit = self.parse_packsize(result["PACKSIZE"])
		image_id = result["IMAGE_ID"]

		return {
			"product": {
				"brand_name": result["BRAND"],
				"name": result["NAME"],
				"packsize": {
					"count": count,
					"sizeeach": size_each,
					"unit": unit
				}
			},
			"image": {
				"url": f"https://asdagroceries.scene7.com/is/image/asdagroceries/{image_id}"
				# ASDA IMAGES DO NOT HAVE ICONS!!
			},
			"link": {
				"upc": int_safe(image_id),
				"store": self.store,
				"cin": int_safe(result["CIN"])
			},
			"price": {
				"price_pence": int(result["PRICES"]["EN"]["PRICE"]) * 100,
				#"was_price": result["PRICES"]["EN"].get("WASPRICE"), now in offer
				"available": result["STATUS"] == "A" # NOT STOCK LEVELS. THEY'RE PER STORE.
			},
			"offer": self.process_promo(result),
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
		print(results,"RESIL")
		if (not results): return []

		clean_datas: list[dict[str, Any]] = []

		for result in results:
			#try:
				clean_datas.append(self.get_storable_from_result(result))
			#except Exception as err:
				#... # LOG, FIGURE LOGGING OUT
			#	print(err,"err")
			
		return clean_datas





	async def search(self, query: str) -> list[dict[str, Any]]:
		req_body = self.get_sendable_search_request(query)

		result = await self._post(body = req_body)
		data = result.json()
		print(data)

		storables = self.parse_data(data)

		return storables
