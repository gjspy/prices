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
			self, env: Result, config: Result, endpoint: str,
			store: str, results_per_search: int):
		
		super().__init__()

		self.endpoint = endpoint
		self.__HEADERS = {
			"Accept": "application/json"
		}
		self.http_method = "GET"
		self._compute_cfw_e(env)

		self.store = store
		self.results_per_search = results_per_search

		self.best_img_res_path = ["imageConfig", "availableResolutions",-1]
		self.img_format_path = ["imageConfig", "availableFormats", 0]
		self.clean_img_path = ["imagePaths", -1]
		self.image_url = "{path}/{resolution}.{fmt}"

		self.price_match_keyword = "price match"

	def get_headers(self):
		return self.__HEADERS
		
	def get_gettable_search_params(self, query: str):
		return {
			"includeAdditionalPageInfo": False,
			"maxProductsToDecorate": self.results_per_search,
			"maxPageSize": self.results_per_search,
			"q": query
		}
	

	def process_promo(self, result: Result) -> Result:
		promotions = result.get("promotions")
		if (not promotions): return {}

		promo: Result = promotions[0] # NEVER SEEN MORE THAN ONE ANYWHERE
		promo_id = promo.get("retailerPromotionId")
		promo_description: str | None = promo.get("description")

		if ((not promo_id) or (not promo_description)): return {}

		if (self.price_match_keyword in promo_description.lower()):
			# PROMO_ID IS NOT INT. DON'T CARE ABOUT IT
			# NO promoPrice, SO CAN'T GET "was_price".

			return {
				"offer_type": "_PriceMatch"
			}

		# REDUCTION
		reduction_match = re.match(regex.MOR_REDUCTION, promo_description.lower())

		if (reduction_match):
			groups = reduction_match.groups()

			return {
				"offer_type": "_Reduction",
				"store_given_data": promo_description,
				"was_price": convert_str_to_pence(groups[1]),
				"store_given_id": promo_id
			}
		
		# MULTIBUY
		multibuy_match = re.match(regex.MOR_MULTIBUY, promo_description.lower())

		if (multibuy_match):
			groups = multibuy_match.groups()

			return {
				"offer_type": "_AnyFor",
				"any_count": int(groups[0]),
				"for_price": convert_str_to_pence(groups[1]),
				"store_given_id": promo_id
			}
		

		return {
			"unknown_offer_type": promo_description,
			"store_given_id": promo_id
		}



	def parse_packsize(self, result: Result, product_name: str):
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
	

	def get_storable_from_result(self, result: Result) -> Result:
		name = result.get("name") or ""
		brand_name = result.get("brand") or ""
		count, size_each, unit = self.parse_packsize(result, name)

		img_resolution = safe_deepget(result, self.best_img_res_path)
		img_format = safe_deepget(result, self.img_format_path)
		img_path = safe_deepget(result, self.clean_img_path)
		img = ""

		if (img_resolution and img_format and img_path):
			img = self.image_url.format(
				path = img_path,
				resolution = img_resolution,
				fmt = img_format
			)

		price_data: Result = result.get("price") or {}
		promo_price_data: Result | None = result.get("promoPrice")
		rating_data: Result = result.get("ratingSummary") or {}
		category_data: list[str] = result.get("categoryPath") or []

		price = price_data.get("amount") 
		if (promo_price_data):
			promo_price = promo_price_data.get("amount")
			price = promo_price or price
		
		price_pence = -1
		# DATA FIELD IS "3.42", or "0.80". DOESNT HAVE £. NEEDED FOR HELPER.
		if (price): price_pence = convert_str_to_pence(f"£{price}")

		cat_len = len(category_data) # ensure has 2+ so no errors later :)
		if (cat_len < 2):
			for _ in range(2 - cat_len):
				category_data.append("")

		return {
			"product": {
				"brand_name": brand_name,
				"name": clean_product_name(name, brand_name),
				"packsize": {
					"count": count,
					"sizeeach": size_each,
					"unit": unit
				}
			},
			"image": {
				"url": img
			},
			"link": {
				#"upc": ,
				"store": self.store,
				"cin": int_safe(result.get("retailerProductId"))
			},
			"price": {
				"price_pence": price_pence,
				"available": result.get("available") == True # NOT STOCK LEVELS. THEY'RE PER STORE.
			},
			"offer": self.process_promo(result),
			"rating": {
				"avg": float(rating_data.get("overallRating") or -1),
				"count": int(rating_data.get("count") or -1)
			},
			"category": {
				"category": category_data[0], # eg Chilled Food
				"department": category_data[1] # eg Cheese
				# also has aisle [Cheddar & Regional Cheese]
				# and shelf [Mature Cheese] but thats too granular
			}
		}

	
	def parse_data(self, data: Result) -> list[list[Result]]:
		results: list[list[Result]] = []

		shelves = data.get("productGroups")
		if (not shelves): return []

		shelf: Result
		for shelf in shelves:
			products = shelf.get("decoratedProducts")
			if (not products): continue

			product: Result
			for product in products:
				#try TODO
				results.append(self.get_storables_from_result(product))
				#except Exception as err:
				#... # TODO LOG, FIGURE LOGGING OUT
			#	print(err,"err")

		return results



"""RESPONSE:
productGroups[0] = decoratedProducts [type="featured"] (Sponsored results.)
productGroups[1] = decoratedProducts [type="personalized"]
each productGroup has a few products, and all seem related. scrolling on morrisons, saw same for first productgroup.



"""