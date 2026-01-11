from copy import deepcopy
import re

from backend_collection.collectors.basecollector import BaseCollector
from backend_collection.mytypes import Number, DSA
from backend_collection.constants import (
	safe_deepget, int_safe, convert_str_to_pence,
	clean_product_name, StoreNames, OFFER_TYPES)
from backend_collection.promo_processor2 import PromoProcessor, InterfacePromoKeys

class ASDPromoKeys(InterfacePromoKeys):
	promo_id = "ID"
	promo_description = "NAME"
	promo_type = "TYPE"

	start_date = "START_DATE"
	end_date = "END_DATE"
	requires_membership = None


class ASDPromoProcessor(PromoProcessor):
	keys = ASDPromoKeys()

	# NOTHING EXTRA. WE PROCESS REDUCTION FOR ASD IN BaseCollector SUBCLASS NOW





class AlgoliaCollector(BaseCollector):
	PromoProcessor = ASDPromoProcessor

	store = StoreNames.asda
	endpoint = "https://8i6wskccnv-dsn.algolia.net/1/indexes/*/queries"
	http_method = "POST"

	_algolia_index_name = "ASDA_PRODUCTS"
	_image_url_fmt = "https://asdagroceries.scene7.com/is/image/asdagroceries/{0}"

	_path_results_from_resp = ["results", 0, "hits"]
	_path_promos_from_result = ["PROMOS", "EN"]
	
	_path_price_from_result = ["PRICES", "EN"]

	def __init__(self, env: DSA, config: DSA, results_per_search: int):
		self._HEADERS = {
			"Accept": "*/*",
			"x-algolia-api-key": config["ASDA_ALGOLIA_API_KEY"],
			"x-algolia-application-id": config["ASDA_ALGOLIA_API_APP"]
		}
		self._compute_cfw_e(env)

		self.results_per_search = results_per_search
		self._base_search_request = {
			"requests": [
				{
					"query": "[UNSET]",
					"indexName": self._algolia_index_name,
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
						#"STOCK.4565",
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


	def get_postable_search_body(
			self, query: str) -> DSA:
		v = deepcopy(self._base_search_request)
		v["requests"][0]["query"] = query

		return v

	def parse_packsize(self, result: DSA, product_name: str):
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

		# GET FROM NAME, NOW USUALLY "{NAME} MULTIxMULTI (TOTAL)"
		n_count, n_size_each, n_unit = self._parse_packsize_str(product_name)

		# TAKE ANY NON-1 VALUE FOR COUNT, WE WANT MULTI IF IT EXISTS.
		# IF n_c == 1, pst_c MUST BE MULTI OR == pst_c IF THAT EXISTS.
		# BASICALLY, ONLY COME BACK FOR n_c IF pst DOESNT EXIST.
		return (
			(n_count, n_size_each, n_unit) if (
				(n_count != 0 and n_count != 1) or (pst_count == 0)
			) else (pst_count, pst_size_each, pst_unit)
		)
	
	def promo_check_reduction(self, sale_data: DSA):
		"""
		Basic reductions ["Rollback", "Dropped"] are described
		in price field, not as a promotion entry.
		"""
		
		offer = sale_data.get("OFFER")
		if (offer == None or offer == "List"): return

		return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"was_price": convert_str_to_pence(sale_data.get("WASPRICE") or ""),
			"reduced_price": convert_str_to_pence(sale_data["PRICE"])
		}
	

	def get_storables_from_result(self, result: DSA) -> list[DSA]:
		brand_name = result.get("BRAND") or ""
		image_id = result.get("IMAGE_ID") or "" # ALSO UPC

		name = result.get("NAME") or ""

		sale_data: dict[str, str] = safe_deepget(
			result, self._path_price_from_result, {})
		price = sale_data.get("WASPRICE") or sale_data.get("PRICE")
		if (not price): return []

		taxonomy: dict[str, str] = result.get("PRIMARY_TAXONOMY") or {}

		count, size_each, unit = self.parse_packsize(result, name)

		promos_data = self.process_promos(result)

		reduction = self.promo_check_reduction(sale_data)
		if (reduction): promos_data.append(reduction)

		labels: list[DSA] = [] # NOTHIGN TO PUT HERE? NO PRICE MATCHES? (TODO CHECK)

		upc = int_safe(image_id)

		return self._build_storables(
			product_name = clean_product_name(name, brand_name),
			brand_name = brand_name,
			ps_count = count,
			ps_sizeeach = size_each,
			ps_unit = unit,
			thumb = self._image_url_fmt.format(image_id),
			upcs = [upc] if upc else None,
			cin = int_safe(result.get("CIN")),
			price_pence = convert_str_to_pence(price),
			is_available = result.get("STATUS") == "A",
			rating_avg = result.get("AVG_RATING"),
			rating_count = result.get("RATING_COUNT"),
			category = taxonomy.get("CAT_NAME"),
			dept = taxonomy.get("DEPT_NAME"),
			promos = promos_data,
			labels = labels
		)

# CONFIRMED price[price_pence] IS BEFORE DISCOUNT
# CONFIRMED offers work well (DOES CHEAPEST PRODUCT FREE EXIST?)