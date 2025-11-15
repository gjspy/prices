from copy import deepcopy
import re
from uuid import uuid4


from backend_collection.collectors.basecollector import BaseCollector
from backend_collection.mytypes import Result
from backend_collection.constants import (
	safe_deepget, int_safe, convert_str_to_pence, dict_add_values, 
	clean_product_name, standardise_packsize, regex)


class GQLCollector(BaseCollector):
	def __init__(
			self, config: Result, endpoint: str,
			store: str, results_per_search: int):

		super().__init__() # nothing happens here?

		self.endpoint = endpoint
		self.__HEADERS = {
			"Accept": "application/json",
			"x-apikey": config["TESCO_XAPI_KEY"]
		}

		self.store = store
		#self.algolia_index_name = algolia_index_name
		self._base_search_request: list[Result] = [
			{
				"operationName": "Search",
				"variables": {
					"page": 1,
					"includeRestrictions": True,
					"includeVariations": True,
					"showDepositReturnCharge": False,
					"showPopularFilter": True,
					"showExpandedResults": False,
					"query": "[UNSET]",
					"count": results_per_search,
					"configs": [
						{
							"featureKey": "dynamic_filter",
							"params": [
								{
									"name": "enable",
									"value": "true"
								}
							]
						}
					],
					"filterCriteria": [
						{
							"name": "0",
							"values": [
								"groceries"
							]
						},
						{
							"name": "inputType",
							"values": [
								"free text"
							]
						}
					],
					"appliedFacetArgs": [],
					"sortBy": "relevance"
				},
				"extensions": {
					"mfeName": "mfe-plp"
				},
				"query": "query Search($query: String!, $page: Int = 1, $count: Int, $sortBy: String, $offset: Int, $facet: ID, $favourites: Boolean, $filterCriteria: [filterCriteria], $configs: [ConfigArgType], $includeRestrictions: Boolean = true, $includeVariations: Boolean = true, $config: BrowseSearchConfig, $showDepositReturnCharge: Boolean = false, $showPopularFilter: Boolean = true, $appliedFacetArgs: [AppliedFacetArgs], $showExpandedResults: Boolean = false) {\n  search(\n    query: $query\n    page: $page\n    count: $count\n    sortBy: $sortBy\n    offset: $offset\n    facet: $facet\n    favourites: $favourites\n    filterCriteria: $filterCriteria\n    configs: $configs\n    config: $config\n    appliedFacetArgs: $appliedFacetArgs\n  ) {\n    pageInformation: info {\n      ...PageInformation\n      __typename\n    }\n    results {\n      node {\n        ... on MPProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on FNFProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on ProductType {\n          ...ProductItem\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    expandedResults @include(if: $showExpandedResults) {\n      node {\n        ... on MPProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on FNFProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on ProductType {\n          ...ProductItem\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    facetLists: facetGroups {\n      ...FacetLists\n      __typename\n    }\n    popularFilters: popFilters @include(if: $showPopularFilter) {\n      ...PopFilters\n      __typename\n    }\n    facets {\n      ...facet\n      __typename\n    }\n    options {\n      sortBy\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ProductItem on ProductInterface {\n  typename: __typename\n  ... on ProductType {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  sellers(type: TOP, limit: 1, offset: 0) {\n    ...Sellers\n    __typename\n  }\n  ... on MPProduct {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    seller {\n      id\n      name\n      __typename\n    }\n    variations {\n      ...Variation @include(if: $includeVariations)\n      __typename\n    }\n    __typename\n  }\n  ... on FNFProduct {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    variations {\n      priceRange {\n        minPrice\n        maxPrice\n        __typename\n      }\n      ...Variation @include(if: $includeVariations)\n      __typename\n    }\n    __typename\n  }\n  id\n  tpnb\n  tpnc\n  gtin\n  adId\n  baseProductId\n  title\n  brandName\n  shortDescription\n  defaultImageUrl\n  superDepartmentId\n  media {\n    defaultImage {\n      aspectRatio\n      __typename\n    }\n    __typename\n  }\n  quantityInBasket\n  superDepartmentName\n  departmentId\n  departmentName\n  aisleId\n  aisleName\n  shelfId\n  shelfName\n  displayType\n  productType\n  charges @include(if: $showDepositReturnCharge) {\n    ... on ProductDepositReturnCharge {\n      __typename\n      amount\n    }\n    __typename\n  }\n  averageWeight\n  bulkBuyLimit\n  maxQuantityAllowed: bulkBuyLimit\n  groupBulkBuyLimit\n  bulkBuyLimitMessage\n  bulkBuyLimitGroupId\n  timeRestrictedDelivery\n  restrictedDelivery\n  isInFavourites\n  isNew\n  isRestrictedOrderAmendment\n  maxWeight\n  minWeight\n  increment\n  details {\n    components {\n      ...Competitors\n      ...AdditionalInfo\n      __typename\n    }\n    __typename\n  }\n  catchWeightList {\n    price\n    weight\n    default\n    __typename\n  }\n  restrictions @include(if: $includeRestrictions) {\n    type\n    isViolated\n    message\n    __typename\n  }\n  reviews {\n    stats {\n      noOfReviews\n      overallRating\n      overallRatingRange\n      __typename\n    }\n    __typename\n  }\n  modelMetadata {\n    name\n    version\n    __typename\n  }\n}\n\nfragment Competitors on CompetitorsInfo {\n  competitors {\n    id\n    priceMatch {\n      isMatching\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment AdditionalInfo on AdditionalInfo {\n  isLowEverydayPricing\n  __typename\n}\n\nfragment Variation on VariationsType {\n  products {\n    id\n    baseProductId\n    variationAttributes {\n      attributeGroup\n      attributeGroupData {\n        name\n        value\n        attributes {\n          name\n          value\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment Sellers on ProductSellers {\n  __typename\n  results {\n    id\n    __typename\n    isForSale\n    status\n    seller {\n      id\n      name\n      logo {\n        url\n        __typename\n      }\n      __typename\n    }\n    price {\n      price: actual\n      unitPrice\n      unitOfMeasure\n      actual\n      __typename\n    }\n    promotions {\n      id\n      promotionType\n      startDate\n      endDate\n      description\n      unitSellingInfo\n      price {\n        beforeDiscount\n        afterDiscount\n        __typename\n      }\n      attributes\n      __typename\n    }\n    fulfilment(deliveryOptions: BEST) {\n      __typename\n      ... on ProductDeliveryType {\n        end\n        charges {\n          value\n          __typename\n        }\n        __typename\n      }\n    }\n  }\n}\n\nfragment FacetLists on ProductListFacetsType {\n  __typename\n  category\n  categoryId\n  facets {\n    facetId: id\n    facetName: name\n    binCount: count\n    isSelected: selected\n    __typename\n  }\n}\n\nfragment PageInformation on ListInfoType {\n  totalCount: total\n  pageNo: page\n  pageId\n  count\n  pageSize\n  matchType\n  offset\n  query {\n    searchTerm\n    actualTerm\n    queryPhase\n    __typename\n  }\n  __typename\n}\n\nfragment PopFilters on ProductListFacetsType {\n  category\n  categoryId\n  facets {\n    facetId: id\n    facetName: name\n    binCount: count\n    isSelected: selected\n    __typename\n  }\n  __typename\n}\n\nfragment facet on FacetInterface {\n  __typename\n  id\n  name\n  type\n  ... on FacetListType {\n    id\n    name\n    listValues: values {\n      name\n      value\n      isSelected\n      count\n      __typename\n    }\n    multiplicity\n    metadata {\n      description\n      footerText\n      linkText\n      linkUrl\n      __typename\n    }\n    __typename\n  }\n  ... on FacetMultiLevelType {\n    id\n    name\n    multiLevelValues: values {\n      children {\n        count\n        name\n        value\n        isSelected\n        __typename\n      }\n      appliedValues {\n        isSelected\n        name\n        value\n        __typename\n      }\n      __typename\n    }\n    multiplicity\n    metadata {\n      description\n      footerText\n      linkText\n      linkUrl\n      __typename\n    }\n    __typename\n  }\n  ... on FacetBooleanType {\n    booleanValues: values {\n      count\n      isSelected\n      value\n      name\n      __typename\n    }\n    __typename\n  }\n}\n"
			}
		]

		self.results_path = [0, "data", "search", "results"]
		self.price_from_result = ["sellers", "results", 0]
		self.promo_from_result = ["promotions", 0]
		self.reviews_from_result = ["reviews", "stats"]
		self.first_attribute_from_promo = ["attributes", 0]
		self.membership_price_promo_keyword = "Clubcard Price"


	def get_sendable_search_request(
			self, query: str) -> list[Result]:
		v = deepcopy(self._base_search_request)
		v[0]["variables"]["query"] = query

		return v


	def process_promo(self, result: Result) -> Result:		
		promo_data: dict[str, str] | None = safe_deepget(result, self.promo_from_result)

		if (not promo_data): return {}
		
		offer_value = promo_data.get("description") or ""
		requires_membership = safe_deepget(
			promo_data, self.first_attribute_from_promo) == "CLUBCARD_PRICING"

		formatted_data = {
			"start_date": promo_data.get("startDate"), # TODO: datetime string format
			"end_date": promo_data.get("endDate"), # datetime string format
			"requires_membership": requires_membership,
			"store_given_id": promo_data.get("id") # ANY X.. CAN MIX AND MATCH OTHER PRODUCTS
		}

		# IS "Any X for £X"
		match = re.match(regex.ANY_X_FOR_PROMO, offer_value.lower())

		if (match):
			groups = match.groups()

			return dict_add_values(
				formatted_data,
				any_count = int(groups[0]),
				for_price = convert_str_to_pence(groups[1])
			)
		
		

		# THIS MUST BE THE LAST EVALUATION
		# AS OTHERS LIKE "ANY FOR" INCLUDE THE KEYWORD.
		if (self.membership_price_promo_keyword in offer_value):
			price_found = re.match(regex.ANY_PRICE, offer_value.lower())
			if (not price_found): return {}

			price_str = price_found.group(0)
			if (not price_str): return {}

			return dict_add_values(
				formatted_data,
				member_reduced_price = convert_str_to_pence(price_str)
			)

		
		# TODO: LOG THIS
		formatted_data["unknown_offer_type"] = offer_value
		return formatted_data
	
	def parse_packsize(self, result: Result, product_name: str):
		"""
		Tesco GQL does not provide a PACKSIZE attribute.
		We scrape it from the name instead.

		For GQL provide seller's price data through result, not the entire node.

		This method parses all possible methods of finding PACKSIZE and
		decides which one to keep.
		"""

		name_data = self._parse_packsize_str(product_name)

		# CAN'T EVER GET BETTER DATA FROM THE OTHER CRUMBS
		# THAN DATA PRESENT IN THE PRODUCT NAME.
		# ONLY USE CRUMBS IF NO NAME DATA.
		if (name_data[0] != 0): return name_data

		# CRUMBS TO FIND INFO
		size_each = -1

		try: size_each = round(int(result["price"]) / int(result["unitPrice"]))
		except: pass

		unit = result.get("unitOfMeasure") or ""

		if (size_each == -1): return (-1, 0, "")
		size_each, unit = standardise_packsize(size_each, unit)

		return (1, size_each, unit)

	def get_storable_from_result(self, result: Result) -> Result:
		data: Result | None = result.get("node")
		if (not data): return {}

		# TODO: filter list for marketplace?
		sale_data: Result = safe_deepget(data, self.price_from_result, {})
		price: Result | None = sale_data.get("price")
		if (not price): return {}

		rating_data: Result = safe_deepget(data, self.reviews_from_result, {})

		brand_name = data.get("brandName") or ""
		name = data.get("title") or ""

		count, size_each, unit = self.parse_packsize(price, name)
		print(sale_data.get("isForSale"))

		return {
			"product": {
				"brand_name": brand_name, # ALL CAPS, "BABYBEL"
				"name": clean_product_name(name, brand_name), # UNCLEAN, HAS BRAND AND PACKSIZE.
				"packsize": {
					"count": count, # ONLY IN TITLE.
					"sizeeach": size_each,
					"unit": unit
				}
			},
			"image": {
				"url": data.get("defaultImageUrl") # HAS ICONS :( # TODO: STANDARDISE IMAGE SIZE. TESCO HAVE ?h=x&w=x, ASDA?
			},
			"link": {
				"upc": int_safe(data.get("gtin")),
				"store": self.store,
				"cin": int_safe(data.get("tpnc")) # TSC PROD NUM C, A AND B EXIST, B GIVEN, C = WEBSITE PAGE ID.
			},
			"price": {
				"price_pence": round(float(price.get("price") or -1) * 100),
				"available": sale_data.get("isForSale") == True # NOT STOCK LEVELS. THEY'RE PER STORE.
			},
			"offer": self.process_promo(sale_data),
			"rating": {
				"avg": rating_data.get("overallRating"),
				"count": rating_data.get("noOfReviews")
			},
			"category": {
				"category": data.get("superDepartmentName"), # eg Fresh Food
				"department": data.get("departmentName") # eg Cheese
				# also has aisle [Cheese Snacking & Lunchbox]
				# and shelf [Cheese Snacking & Minis] but thats too granular
			}
		}


	def get_headers(self) -> dict[str, str]:
		"""
		uuids could potentially be ok being the same each request?
		help against tracking if they are different.
		"""
		headers = self.__HEADERS
		
		trkid, trcid = str(uuid4()), str(uuid4())

		headers["trkid"] = trkid
		headers["traceid"] = trkid + ":" + trcid

		return headers


		



