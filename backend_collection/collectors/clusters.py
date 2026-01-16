from backend_collection.collectors.basecollector import BaseCollector
from backend_collection.types import DSA, Result, SDG_Key
from backend_collection.constants import (
	safe_deepget, int_safe, convert_str_to_pence, clean_product_name,
	StoreNames, regex, OFFER_TYPES, convert_fracorperc_to_perc)
from backend_collection.promo_processor import InterfacePromoKeys, PromoProcessor

class MORPromoKeys(InterfacePromoKeys):
	promo_id = "retailerPromotionId"
	promo_description = "description"
	promo_type = None

	start_date = None
	end_date = None
	requires_membership = None

class MORPromoProcessor(PromoProcessor):
	keys = MORPromoKeys()

	online_exclusive_keyword = "online exclusive"
	pricematch_keyword = "price match"

	# DATA DOES NOT SPECIFY WITH WHOM THE PRICE IS MATCHED
	# MORRISONS WEBSITE: "essentials price matched to Aldi and Lidl"
	pricematching_store = "UnspecificAldiLidl"

	def __init__(self, result: DSA, specific_promo: DSA):
		super().__init__(result, specific_promo)

		self._strapline_checks.append(self.check_pricematch)

	@property
	def promo_online_exclusive(self):
		return self.online_exclusive_keyword in self.strapline.lower()
	

	def check_multibuy(self):
		"""
		Check description for match of "buy [X] for [Y]"
		Check description for match of "any [x] for [y]"

		Check description for match of either of the above,
		where y is an amount and includes
		"cheapest item free" [`multibuy_cheapest_free_keyword`]

		ALSO checks for "Buy [X] Save [Y]%"
		"""
		normal = super().check_multibuy()
		if (normal): return normal

		groups = self._query_regex(regex.MULTIBUY_SAVE, self.strapline)
		if (not groups): return

		return {
			"offer_type": OFFER_TYPES.any_for,
			"any_count": int(groups[0]),
			"save_perc": convert_fracorperc_to_perc(groups[1])
		}



	def check_pricematch(self):
		""" Check for presence of pricematch keyword. """
		if (not self.strapline): return

		if (self.pricematch_keyword in self.strapline.lower()): return {
			"matching_store": self.pricematching_store
		}



class ClusterCollector(BaseCollector):
	PromoProcessor = MORPromoProcessor

	store = StoreNames.morrisons
	endpoint = "https://groceries.morrisons.com/api/webproductpagews/v6/product-pages/search"
	http_method = "GET"

	#_path_results_from_resp = None
	_path_promos_from_result = ["promotions"]

	_path_best_img_res = ["imageConfig", "availableResolutions",-1]
	_path_img_format = ["imageConfig", "availableFormats", 0]
	_path_clean_img = ["imagePaths", -1]
	_path_img_url_fmt = "{path}/{resolution}.{fmt}"

	def __init__(self, env: DSA, config: DSA, results_per_search: int):
		self._HEADERS = {
			"Accept": "application/json"
		}
		self._compute_cfw_e(env)

		self.results_per_search = results_per_search

		
	def get_gettable_search_params(self, query: str):
		return {
			"includeAdditionalPageInfo": False,
			"maxProductsToDecorate": self.results_per_search,
			"maxPageSize": self.results_per_search,
			"q": query
		}


	def parse_packsize(self, result: DSA, product_name: str):
		"""
		This method parses all possible methods of finding PACKSIZE and
		decides which one to keep.

		Simple for this store, as we have a single field for it.
		"""

		packsize_text = result.get("packSizeDescription")
		if (packsize_text):
			return self._parse_packsize_str(packsize_text)
		
		# LAST RESORT
		return self._parse_packsize_str(product_name)
	

	def get_storables_from_result(self, result: DSA) -> list[DSA]:
		name = result.get("name") or ""
		brand_name = result.get("brand") or ""
		count, size_each, unit = self.parse_packsize(result, name)

		img_resolution = safe_deepget(result, self._path_best_img_res)
		img_format = safe_deepget(result, self._path_img_format)
		img_path = safe_deepget(result, self._path_clean_img)
		img = ""

		if (img_resolution and img_format and img_path):
			img = self._path_img_url_fmt.format(
				path = img_path,
				resolution = img_resolution,
				fmt = img_format
			)

		# IN TERMS OF REDUCTION,  result["promoPrice"] GIVES "NOW",
		# result["price"] IS ALWAYS "WAS". WE STORE "WAS".
		price_data: DSA = result.get("price") or {}
		price = price_data.get("amount") 
		if (not price): return []

		# DATA FIELD IS "3.42", or "0.80". DOESNT HAVE £. NEEDED FOR HELPER.
		price_pence = convert_str_to_pence(f"£{price}")

		# CATEGORY GIVEN AS LIST, TAKE FIRST 2
		category_data: list[str] = result.get("categoryPath") or []
		l = len(category_data)

		category = category_data[0] if l >= 1 else ""
		dept = category_data[1] if l >= 2 else ""

		rating_data: DSA = result.get("ratingSummary") or {}

		promos_data = self.process_promos(result)
		price_matches = list(filter(
			lambda x: x.get("matching_store"),
			promos_data))
		
		promos_data = list(filter(
			lambda x: not x.get("matching_store"),
			promos_data))


		return self._build_storables(
			product_name = clean_product_name(name, brand_name),
			brand_name = brand_name,
			ps_count = count,
			ps_sizeeach = size_each,
			ps_unit = unit,
			thumb = img, # BEST SIZE
			upcs = None,
			cin = int_safe(result.get("retailerProductId")),
			price_pence = price_pence,
			is_available = result.get("available") == True, # NOT STOCK LEVELS. THEY'RE PER STORE.
			rating_avg = float(rating_data.get("overallRating") or -1),
			rating_count = int(rating_data.get("count") or -1),
			category = category,
			dept = dept,
			promos = promos_data,
			labels = price_matches
		)

	
	def parse_data(self, data: DSA) -> list[list[DSA]]:
		results: list[list[DSA]] = []

		shelves = data.get("productGroups")
		if (not shelves): return []

		shelf: DSA
		for shelf in shelves:
			products = shelf.get("decoratedProducts")
			if (not products): continue

			product: DSA
			for product in products:
				#try TODO
				results.append(self.get_storables_from_result(product))
				#except Exception as err:
				#... # TODO LOG, FIGURE LOGGING OUT
			#	print(err,"err")

		return results

# CONFIRMED price[price_pence] is BEFORE discount
# CONFIRMED price match offers are created
# CONFIRMED offers work well

"""RESPONSE:
productGroups[0] = decoratedProducts [type="featured"] (Sponsored results.)
productGroups[1] = decoratedProducts [type="personalized"]
each productGroup has a few products, and all seem related. scrolling on morrisons, saw same for first productgroup.
"""