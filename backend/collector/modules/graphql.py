from copy import deepcopy
from uuid import uuid4
import re

from backend.collector.modules.basecollector import BaseCollector
from backend.log_handler import CustomLogger
from backend.types import DSA, Optional
from backend.constants import (
	safe_deepget, int_safe, convert_str_to_pence, 
	clean_product_name, standardise_packsize, regex, OFFER_TYPES, StoreNames)
from backend.collector.promo_processor import InterfacePromoKeys, PromoProcessor


class TSCPromoKeys(InterfacePromoKeys):
	promo_id = "id"
	promo_description = "description"
	promo_type = None

	start_date = "startDate"
	end_date = "endDate"
	requires_membership = None
	online_exclusive = None


class TSCPromoProcessor(PromoProcessor):
	keys = TSCPromoKeys()

	membership_price_promo_keyword = "clubcard price"
	multibuy_cheapest_free_keyword = "cheapest product free"

	datetime_fmt = "%Y-%m-%dT%H:%M:%SZ"

	def __init__(self, result: DSA, specific_promo: DSA):
		super().__init__(result, specific_promo)

		self._strapline_checks.append(self.check_membership_price)


	@property
	def promo_requires_membership(self):
		promo_attributes = self.promo_data.get("attributes")
		return (promo_attributes and "CLUBCARD_PRICING" in promo_attributes)


	def check_membership_price(self) -> DSA:
		"""
		Check match for "[X] Clubcard price"
		MUST BE LAST, AS other promos may include the keyword.
		"""
		if (not self.strapline): return {}
		if (not self.membership_price_promo_keyword in self.strapline.lower()):
			return {}

		# DO NOT USE PRICE_FLEX, AS THEY COULD HAVE "£1 SAVE 1/3 Clubcard Price"
		price = self._query_regex(regex.PRICE, self.strapline)
		if (not price): return {}

		return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"reduced_price": convert_str_to_pence(price[0])
		}




class GQLCollector(BaseCollector):
	PromoProcessor = TSCPromoProcessor

	store = StoreNames.tesco
	endpoint = "https://xapi.tesco.com"
	http_method = "POST"

	image_size = 1250
	_image_pattern = r"h=\d+&w=\d+"
	_image_sub = f"h={image_size}&w={image_size}"
	
	_path_results_from_resp = [0, "data", "search", "results"]
	_path_promos_from_result = ["sellers", "results", 0, "promotions"]

	_path_price_from_result = ["sellers", "results", 0]
	_path_reviews_from_result = ["reviews", "stats"]
	_path_competitors_from_result = [
		"details", "components",
		{"__typename": "CompetitorsInfo"}, "competitors"]
	

	def __init__(
			self, logger: CustomLogger, env: DSA,
			config: DSA, results_per_search: int):
		super().__init__(logger, env, config, results_per_search)
		
		self._HEADERS = {
			"Accept": "application/json",
			"x-apikey": config["TESCO_XAPI_KEY"]
		}

		self._base_search_request: list[DSA] = [
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


	def get_postable_search_body(
			self, query: str) -> list[DSA]:
		v = deepcopy(self._base_search_request)
		v[0]["variables"]["query"] = query

		return v

	def check_pricematch(self, result: DSA) -> list[DSA]:
		""" Check for pricematch with competitors. """

		competitors = safe_deepget(result, self._path_competitors_from_result)
		if (not competitors): return []

		return [
			{"matching_store": competitor["id"]}
			for competitor in competitors if competitor.get("id")
		]


	def parse_packsize(self, result: DSA, product_name: str):
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
		size_each = 0

		try: size_each = round(int(result["price"]) / int(result["unitPrice"]))
		except: pass

		unit = result.get("unitOfMeasure") or ""

		if (size_each == 0): return (0, 0, "")
		size_each, unit = standardise_packsize(size_each, unit)

		return (1, size_each, unit)

	def get_storables_from_result(self, result: DSA) -> list[DSA]:
		if (not result.get("node")): return []
		result = result["node"]

		# WARNING ABOUT MARKETPLACE ITEMS. QPs FILTER OUT.
		sale_data: DSA = safe_deepget(
			result, self._path_price_from_result, {})
		price_data: Optional[DSA] = sale_data.get("price")
		if (not price_data): return []

		price = price_data.get("price")
		if (not price): return []

		rating_data: DSA = safe_deepget(
			result, self._path_reviews_from_result, {})

		brand_name = result.get("brandName") or ""
		name = result.get("title") or ""

		count, size_each, unit = self.parse_packsize(price_data, name)

		promos_data = self.process_promos(result)
		price_matches = self.check_pricematch(result)

		upc = int_safe(result.get("gtin"))

		img = result.get("defaultImageUrl") or ""
		img = re.sub(self._image_pattern, self._image_sub, img)

		return self._build_storables(
			product_name = clean_product_name(name, brand_name),
			brand_name = brand_name, # NOT PERFECT BUT ITS SOMETHING
			ps_count = count, # ONLY IN TITLE.
			ps_sizeeach = size_each,
			ps_unit = unit,
			thumb = img, # HAS ICONS :(
			upcs = [upc] if upc else None,
			cin = int_safe(result.get("tpnc")), # TSC PROD NUM C, A AND B EXIST, B GIVEN, C = WEBSITE PAGE ID.
			price_pence = round(float(price) * 100),
			is_available = sale_data.get("isForSale") == True, # NOT STOCK LEVELS. THEY'RE PER STORE.
			rating_avg = rating_data.get("overallRating"),
			rating_count = rating_data.get("noOfReviews"),
			category = result.get("superDepartmentName"), # eg Fresh Food
			dept = result.get("departmentName"), # eg Cheese
			promos = promos_data,
			labels = price_matches
		)


	def get_headers(self) -> dict[str, str]:
		"""
		uuids could potentially be ok being the same each request?
		help against tracking if they are different.
		"""
		headers = self._HEADERS
		
		trkid, trcid = str(uuid4()), str(uuid4())

		headers["trkid"] = trkid
		headers["traceid"] = trkid + ":" + trcid

		return headers


# CONFIRMED price[price_pence] is BEFORE discount
# CONFIRMED price match offers are created
# CONFIRMED offers work well -> CHEAPEST PRODUCT FREE WORKS.


