from copy import deepcopy
import re

from backend_collection.collectors.basecollector import BaseCollector
from backend_collection.mytypes import Number, Result
from backend_collection.constants import (
	safe_deepget, int_safe, convert_str_to_pence,
	clean_product_name, regex)


class AlgoliaCollector(BaseCollector):
	def __init__(
			self, env: Result, config: Result, endpoint: str,
			algolia_index_name: str, store: str, results_per_search: int):

		super().__init__() # nothing happens here?

		self.endpoint = endpoint
		self.__HEADERS = {
			"Accept": "*/*",
			"x-algolia-api-key": config["ASDA_ALGOLIA_API_KEY"],
			"x-algolia-application-id": config["ASDA_ALGOLIA_API_APP"]
		}
		self.http_method = "POST"
		self._compute_cfw_e(env)

		self.store = store
		self.results_per_search = results_per_search
		self.algolia_index_name = algolia_index_name
		self._base_search_request = {
			"requests": [
				{
					"query": "[UNSET]",
					"indexName": algolia_index_name, # "ASDA_PRODUCTS"
					"clickAnalytics": False,
					"analytics": False,
					"hitsPerPage": results_per_search,
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
		self.promo_from_result = ["PROMOS", "EN", 0]

		self.image_url = "https://asdagroceries.scene7.com/is/image/asdagroceries/{0}"


	def get_postable_search_body(
			self, query: str) -> Result:
		v = deepcopy(self._base_search_request)
		v["requests"][0]["query"] = query

		return v


	def process_promo(self, result: Result) -> Result:
		prices_data: dict[str, str] | None = safe_deepget(result, self.prices_from_result)

		if (prices_data):
			offer_type = prices_data.get("OFFER")

			if (offer_type and offer_type != "List"): # TODO, ARE THERE MORE THAN ROLLBACK THAT END UP HERE?
				# Rollback, Dropped # TODO, WHAT IS store_given_data, WHERE IS store_given_id?
				return {
					"offer_type": "_Reduction",
					"store_given_data": prices_data["OFFER"],
					"was_price": prices_data["WASPRICE"] * 100
				}
		
		# TODO CAN THEY DO ROLLBACK AND ANY X FOR????
		promo_data: dict[str, str] | None = safe_deepget(result, self.promo_from_result)

		if (not promo_data): return {}
		
		offer_value = promo_data.get("NAME")
		if (not offer_value): return {}

		# IS "Any X for £X"
		match = re.match(regex.ANY_X_FOR_PROMO, offer_value.lower()) # TYPE 15

		if (match):
			groups = match.groups()

			return {
				"offer_type": "_AnyFor",
				"any_count": int(groups[0]),
				"for_price": convert_str_to_pence(groups[1]),
				"store_given_id": promo_data.get("ID") # CAN MIX AND MATCH OTHER PRODUCTS
			}
		
		# TODO: REFER BY TYPE
		# PROMOS.EN.TYPE
		#	= 15 -> Any X
		#	= 12 -> Meal Deal
		
		# TODO: LOG THIS
		return {
			"unknown_offer_type": offer_value + "_" + str(promo_data.get("TYPE")),
			"start_date": promo_data.get("START_DATE"),
			"end_date": promo_data.get("END_DATE"), # TODO: THESE ARE UNIX STAMPS.
			"store_given_id": promo_data.get("ID")
		}


	
	

	def parse_packsize(self, result: Result, product_name: str):
		"""
		algolia provides pack size with the PACK_SIZE field
		AND in the product name now too (sadly.)
		
		RIP to being atomic and beautiful..

		This method parses all possible methods of finding PACKSIZE and
		decides which one to keep.
		"""
		
		# USUALLY TOTAL PACKSIZE. RARELY DOES MULTI HERE.
		packsize_text = result.get("PACK_SIZE") or ""
		pst_count, pst_size_each, pst_unit = self._parse_packsize_str(packsize_text)

		# NOW USUALLY "..NAME.. MULTIxMULTI (TOTAL)"
		n_count, n_size_each, n_unit = self._parse_packsize_str(product_name)

		# TAKE ANY NON-1 VALUE FOR COUNT, WE WANT MULTI IF IT EXISTS.
		# IF n_c == 1, pst_c MUST BE MULTI OR == pst_c IF THAT EXISTS.
		# BASICALLY, ONLY COME BACK FOR n_c IF pst DOESNT EXIST.
		return (
			(n_count, n_size_each, n_unit) if (
				(n_count != 0 and n_count != 1) or (pst_count == 0)
			) else (pst_count, pst_size_each, pst_unit)
		)
	


	def get_storable_from_result(self, result: Result) -> Result:
		brand_name = result.get("BRAND") or ""
		image_id = result.get("IMAGE_ID") or ""

		# ORIGINALLY GAVE SUPER CLEAN,
		# NOW INCLUDES PACKSIZE :(
		# CLEAN IT FOR FUTURE PROOFING
		name = result.get("NAME") or ""

		price_data: dict[str, str] = safe_deepget(result, self.prices_from_result) or {}
		taxonomy: dict[str, str] = result.get("PRIMARY_TAXONOMY") or {}

		count, size_each, unit = self.parse_packsize(result, name)
		
		return {
			"product": {
				"brand_name": brand_name, # CLEANEST, Title Case
				"name": clean_product_name(name, brand_name),
				"packsize": {
					"count": count,
					"sizeeach": size_each,
					"unit": unit
				}
			},
			"image": {
				"url": self.image_url.format(image_id)
				# ASDA IMAGES DO NOT HAVE ICONS!!
			},
			"link": {
				"upc": int_safe(image_id),
				"store": self.store,
				"cin": int_safe(result.get("CIN"))
			},
			"price": {
				"price_pence": convert_str_to_pence(price_data.get("PRICE") or ""),
				"available": result.get("STATUS") == "A" # NOT STOCK LEVELS. THEY'RE PER STORE.
			},
			"offer": self.process_promo(result),
			"rating": {
				"avg": result.get("AVG_RATING"),
				"count": result.get("RATING_COUNT")
			},
			"category": {
				"category": taxonomy.get("CAT_NAME"), # eg Chilled Food
				"department": taxonomy.get("DEPT_NAME") # eg Cheese
				# also has aisle [Cheddar & Regional Cheese]
				# and shelf [Mature Cheese] but thats too granular
			}
		}


	def get_headers(self) -> dict[str, str]:
		return self.__HEADERS # easy here, other places require computation