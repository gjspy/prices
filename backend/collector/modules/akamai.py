from backend.collector.modules.basecollector import BaseCollector
from backend.log_handler import CustomLogger
from backend.types import DSA, Optional
from backend.constants import (
	safe_deepget, convert_str_to_pence, clean_product_name,
	regex, OFFER_TYPES, StoreNames, convert_fracorperc_to_perc, clean_string)
from backend.collector.promo_processor import InterfacePromoKeys, PromoProcessor

import re

class SAIPromoKeys(InterfacePromoKeys):
	promo_id = "promotion_uid"
	promo_description = "strap_line"
	promo_type = "promo_type"

	start_date = "start_date"
	end_date = "end_date"
	requires_membership = "is_nectar"
	online_exclusive = None

class SAIPromoProcessor(PromoProcessor):
	keys = SAIPromoKeys()

	datetime_fmt = "%Y-%m-%dT%H:%M:%SZ"


	def check_reduction(self):
		"""
		Check description for match of "now [X], was [Y]"

		ALSO checks for "Save [X]%", "Save [X]/[Y]"
		"""

		normal = super().check_reduction()
		if (normal): return normal

		groups = self._query_regex(regex.SAVE, self.strapline)
		if (not groups): return

		was = self.promo_data.get("original_price")

		return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"was_price": convert_str_to_pence(f"£{was}"),
			"save_perc": convert_fracorperc_to_perc(groups[0])
		}


	def check_multibuy(self):
		"""
		Check description for match of "buy [X] for [Y]"
		Check description for match of "any [x] for [y]"

		Check description for match of either of the above,
		where y is an amount and includes
		"cheapest item free" [`multibuy_cheapest_free_keyword`]

		ALSO converts dumb "Buy 1 for [X]" to REDUCTION instead of AF.
		"""

		data =  super().check_multibuy()
		if (not data): return
		
		was = self.promo_data.get("original_price")

		if (data["any_count"] == 1): return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"was_price": convert_str_to_pence(f"£{was}"),
			"reduced_price": data["for_price"]
		}

		return data


	def _process_by_type(self):
		match self.promo_type:
			case "SIMPLE_FIXED_PRICE":
				return (self.check_reduction() or self.check_multibuy())
			
			case "MULTIBUY_BUY_X_OF_VARIABLE_PRICE_FOR_Y":
				return self.check_multibuy()
			
			case _: pass




class AKMCollector(BaseCollector):
	PromoProcessor = SAIPromoProcessor

	store = StoreNames.sainsburys
	endpoint = "https://www.sainsburys.co.uk/groceries-api/gol-services/product/v1/product"
	http_method = "GET"

	_path_results_from_resp = ["products"]
	_path_promos_from_result = ["promotions"]

	_path_brandname_from_result = ["attributes", "brand", 0]

	pricematch_keyword = "price match"


	def __init__(
			self, logger: CustomLogger, env: DSA,
			config: DSA, results_per_search: int):
		super().__init__(logger, env, config, results_per_search)

		self._HEADERS = {
			"Accept": "application/json",
			"User-Agent": "Chrome/143.0.0.0"
		}
		self._cfwt = False # akamai IS API SECURITY ORG. BLOCKS CF.


	def get_gettable_search_params(self, query: str):
		return {
			"filter[keyword]": query,
			"page_size": self.results_per_search,
		}


	def parse_packsize(self, result: DSA, product_name: str):
		"""
		This method parses all possible methods of finding PACKSIZE and
		decides which one to keep.

		No field here, so just name.
		"""

		return self._parse_packsize_str(product_name)
	

	def check_pricematch(self, result: DSA):
		""" Check for pricematch in labels. """

		labels: list[DSA] = result.get("labels") or []
		matches: list[DSA] = []

		for l in labels:
			uid: Optional[str] = l.get("label_uid")
			if (not uid): continue
			if (not self.pricematch_keyword in uid.lower()): continue

			store_name = clean_string(re.sub(
				self.pricematch_keyword, "", uid, flags = re.IGNORECASE))

			matches.append({
				"matching_store": store_name
			})
		
		return matches


	def get_storables_from_result(self, result: DSA) -> list[DSA]:
		brand_name = safe_deepget(result, self._path_brandname_from_result, "")
		name = result.get("name") or ""
		img = result.get("image") or ""

		rating_data: DSA = result.get("reviews") or {}

		count, size_each, unit = self.parse_packsize(result, name)

		# result["retail_price"] IS DISCOUNTED. NEED TO DIG FOR ORIGINAL.
		sale_data: DSA = result.get("retail_price") or {}
		price = sale_data.get("price")
		if (not price): return []
		price = round(price * 100)

		promos_data = self.process_promos(result)
		for promo in promos_data:
			was = promo.get("was_price")
			if (not was): continue

			price = was
			break

		price_matches = self.check_pricematch(result)

		return self._build_storables(
			product_name = clean_product_name(name, brand_name),
			brand_name = brand_name, # NOT PERFECT BUT ITS SOMETHING
			ps_count = count, # ONLY IN TITLE.
			ps_sizeeach = size_each,
			ps_unit = unit,
			thumb = img,
			upcs = result.get("eans"),
			cin = result.get("product_uid"),
			price_pence = price,
			is_available = result.get("is_available") == True,
			rating_avg = rating_data.get("average_rating"),
			rating_count = rating_data.get("total"),
			category = None, # NOT WORTH OUR TIME
			dept = None,
			promos = promos_data,
			labels = price_matches
		)

# CONFIRMED price[price_pence] is BEFORE discount
# CONFIRMED price match offers are created
# CONFIRMED offers work well


"""
unused code for headers. they don't need trace values, just wanted a user-agent :)

		Need to generate trace values for this store!

		trace fields follow W3C Trace Context: 
		- traceparent: "version-traceid-parentid-flags"
		- tracestate: more vague, vendor-specific flags, we don't care


		traceparent_trace = uuid4().hex
		traceparent_parent = uuid4().hex[:16]
		
		headers["traceparent"] = self.headers_traceparent_format.format(
			traceid = traceparent_trace,
			parent = traceparent_parent)
		
		headers["tracestate"] = self.headers_tracestate_format.format(
			parent = traceparent_parent,
			timestamp = int(time.time() * 1000))s

"""