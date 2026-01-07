import requests
import time
import uuid
from dotenv import dotenv_values

trk = str(uuid.uuid4())#"a4d2f5be-cd48-4591-a9c1-32c9b95ed715"
trc = str(uuid.uuid4())##"dcb28470-e239-44b1-b709-5405b700c075"#"40a7198d-6b3b-466b-80b2-b4cca313e798"
apik = dotenv_values(".config")["TESCO_XAPI_KEY"]
traceid = trk + ":" + trc
print(traceid)

a = requests.request(
	method = "POST",
	url = "https://xapi.tesco.com/",
	headers = {
		"Accept": "application/json",
		"content-type": "application/json",
		"x-apikey": apik,
		"trkid": trk,
		"traceid": traceid
	},

	json = [{"operationName":"Search","variables":{"page":1,"includeRestrictions":True,"includeVariations":True,"showDepositReturnCharge":False,"showPopularFilter":True,"showExpandedDSAs":False,"query":"cheese","count":24,"configs":[{"featureKey":"dynamic_filter","params":[{"name":"enable","value":"true"}]}],"filterCriteria":[{"name":"0","values":["groceries"]},{"name":"inputType","values":["suggested"]}],"appliedFacetArgs":[],"sortBy":"relevance"},"extensions":{"mfeName":"mfe-plp"},"query":"query Search($query: String!, $page: Int = 1, $count: Int, $sortBy: String, $offset: Int, $facet: ID, $favourites: Boolean, $filterCriteria: [filterCriteria], $configs: [ConfigArgType], $includeRestrictions: Boolean = true, $includeVariations: Boolean = true, $config: BrowseSearchConfig, $showDepositReturnCharge: Boolean = false, $showPopularFilter: Boolean = true, $appliedFacetArgs: [AppliedFacetArgs], $showExpandedDSAs: Boolean = false) {\n  search(\n    query: $query\n    page: $page\n    count: $count\n    sortBy: $sortBy\n    offset: $offset\n    facet: $facet\n    favourites: $favourites\n    filterCriteria: $filterCriteria\n    configs: $configs\n    config: $config\n    appliedFacetArgs: $appliedFacetArgs\n  ) {\n    pageInformation: info {\n      ...PageInformation\n      __typename\n    }\n    results {\n      node {\n        ... on MPProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on FNFProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on ProductType {\n          ...ProductItem\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    expandedDSAs @include(if: $showExpandedDSAs) {\n      node {\n        ... on MPProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on FNFProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on ProductType {\n          ...ProductItem\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    facetLists: facetGroups {\n      ...FacetLists\n      __typename\n    }\n    popularFilters: popFilters @include(if: $showPopularFilter) {\n      ...PopFilters\n      __typename\n    }\n    facets {\n      ...facet\n      __typename\n    }\n    options {\n      sortBy\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ProductItem on ProductInterface {\n  typename: __typename\n  ... on ProductType {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  sellers(type: TOP, limit: 1, offset: 0) {\n    ...Sellers\n    __typename\n  }\n  ... on MPProduct {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    seller {\n      id\n      name\n      __typename\n    }\n    variations {\n      ...Variation @include(if: $includeVariations)\n      __typename\n    }\n    __typename\n  }\n  ... on FNFProduct {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    variations {\n      priceRange {\n        minPrice\n        maxPrice\n        __typename\n      }\n      ...Variation @include(if: $includeVariations)\n      __typename\n    }\n    __typename\n  }\n  id\n  tpnb\n  tpnc\n  gtin\n  adId\n  baseProductId\n  title\n  brandName\n  shortDescription\n  defaultImageUrl\n  superDepartmentId\n  media {\n    defaultImage {\n      aspectRatio\n      __typename\n    }\n    __typename\n  }\n  quantityInBasket\n  superDepartmentName\n  departmentId\n  departmentName\n  aisleId\n  aisleName\n  shelfId\n  shelfName\n  displayType\n  productType\n  charges @include(if: $showDepositReturnCharge) {\n    ... on ProductDepositReturnCharge {\n      __typename\n      amount\n    }\n    __typename\n  }\n  averageWeight\n  bulkBuyLimit\n  maxQuantityAllowed: bulkBuyLimit\n  groupBulkBuyLimit\n  bulkBuyLimitMessage\n  bulkBuyLimitGroupId\n  timeRestrictedDelivery\n  restrictedDelivery\n  isInFavourites\n  isNew\n  isRestrictedOrderAmendment\n  maxWeight\n  minWeight\n  increment\n  details {\n    components {\n      ...Competitors\n      ...AdditionalInfo\n      __typename\n    }\n    __typename\n  }\n  catchWeightList {\n    price\n    weight\n    default\n    __typename\n  }\n  restrictions @include(if: $includeRestrictions) {\n    type\n    isViolated\n    message\n    __typename\n  }\n  reviews {\n    stats {\n      noOfReviews\n      overallRating\n      overallRatingRange\n      __typename\n    }\n    __typename\n  }\n  modelMetadata {\n    name\n    version\n    __typename\n  }\n}\n\nfragment Competitors on CompetitorsInfo {\n  competitors {\n    id\n    priceMatch {\n      isMatching\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment AdditionalInfo on AdditionalInfo {\n  isLowEverydayPricing\n  __typename\n}\n\nfragment Variation on VariationsType {\n  products {\n    id\n    baseProductId\n    variationAttributes {\n      attributeGroup\n      attributeGroupData {\n        name\n        value\n        attributes {\n          name\n          value\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment Sellers on ProductSellers {\n  __typename\n  results {\n    id\n    __typename\n    isForSale\n    status\n    seller {\n      id\n      name\n      logo {\n        url\n        __typename\n      }\n      __typename\n    }\n    price {\n      price: actual\n      unitPrice\n      unitOfMeasure\n      actual\n      __typename\n    }\n    promotions {\n      id\n      promotionType\n      startDate\n      endDate\n      description\n      unitSellingInfo\n      price {\n        beforeDiscount\n        afterDiscount\n        __typename\n      }\n      attributes\n      __typename\n    }\n    fulfilment(deliveryOptions: BEST) {\n      __typename\n      ... on ProductDeliveryType {\n        end\n        charges {\n          value\n          __typename\n        }\n        __typename\n      }\n    }\n  }\n}\n\nfragment FacetLists on ProductListFacetsType {\n  __typename\n  category\n  categoryId\n  facets {\n    facetId: id\n    facetName: name\n    binCount: count\n    isSelected: selected\n    __typename\n  }\n}\n\nfragment PageInformation on ListInfoType {\n  totalCount: total\n  pageNo: page\n  pageId\n  count\n  pageSize\n  matchType\n  offset\n  query {\n    searchTerm\n    actualTerm\n    queryPhase\n    __typename\n  }\n  __typename\n}\n\nfragment PopFilters on ProductListFacetsType {\n  category\n  categoryId\n  facets {\n    facetId: id\n    facetName: name\n    binCount: count\n    isSelected: selected\n    __typename\n  }\n  __typename\n}\n\nfragment facet on FacetInterface {\n  __typename\n  id\n  name\n  type\n  ... on FacetListType {\n    id\n    name\n    listValues: values {\n      name\n      value\n      isSelected\n      count\n      __typename\n    }\n    multiplicity\n    metadata {\n      description\n      footerText\n      linkText\n      linkUrl\n      __typename\n    }\n    __typename\n  }\n  ... on FacetMultiLevelType {\n    id\n    name\n    multiLevelValues: values {\n      children {\n        count\n        name\n        value\n        isSelected\n        __typename\n      }\n      appliedValues {\n        isSelected\n        name\n        value\n        __typename\n      }\n      __typename\n    }\n    multiplicity\n    metadata {\n      description\n      footerText\n      linkText\n      linkUrl\n      __typename\n    }\n    __typename\n  }\n  ... on FacetBooleanType {\n    booleanValues: values {\n      count\n      isSelected\n      value\n      name\n      __typename\n    }\n    __typename\n  }\n}\n"}]
)

print(a.content)

with open(f"{time.time()}.json", "wb") as f:
	f.write(a.content)

print("#######")
print(a.json())











"""json = [
		{
			"operationName": "Search",
			"variables": {
				"page": 1,
				"includeRestrictions": True,
				"includeVariations": True,
				"showDepositReturnCharge": False,
				"showPopularFilter": True,
				"showExpandedDSAs": False,
				"query": "grated cheese",
				"count": 24,
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
			"query": "query Search($query: String!, $page: Int = 1, $count: Int, $sortBy: String, $offset: Int, $facet: ID, $favourites: Boolean, $filterCriteria: [filterCriteria], $configs: [ConfigArgType], $includeRestrictions: Boolean = true, $includeVariations: Boolean = true, $config: BrowseSearchConfig, $showDepositReturnCharge: Boolean = false, $showPopularFilter: Boolean = true, $appliedFacetArgs: [AppliedFacetArgs], $showExpandedDSAs: Boolean = false) {\n  search(\n    query: $query\n    page: $page\n    count: $count\n    sortBy: $sortBy\n    offset: $offset\n    facet: $facet\n    favourites: $favourites\n    filterCriteria: $filterCriteria\n    configs: $configs\n    config: $config\n    appliedFacetArgs: $appliedFacetArgs\n  ) {\n    pageInformation: info {\n      ...PageInformation\n      __typename\n    }\n    results {\n      node {\n        ... on MPProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on FNFProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on ProductType {\n          ...ProductItem\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    expandedDSAs @include(if: $showExpandedDSAs) {\n      node {\n        ... on MPProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on FNFProduct {\n          ...ProductItem\n          __typename\n        }\n        ... on ProductType {\n          ...ProductItem\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    facetLists: facetGroups {\n      ...FacetLists\n      __typename\n    }\n    popularFilters: popFilters @include(if: $showPopularFilter) {\n      ...PopFilters\n      __typename\n    }\n    facets {\n      ...facet\n      __typename\n    }\n    options {\n      sortBy\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ProductItem on ProductInterface {\n  typename: __typename\n  ... on ProductType {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  sellers(type: TOP, limit: 1, offset: 0) {\n    ...Sellers\n    __typename\n  }\n  ... on MPProduct {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    seller {\n      id\n      name\n      __typename\n    }\n    variations {\n      ...Variation @include(if: $includeVariations)\n      __typename\n    }\n    __typename\n  }\n  ... on FNFProduct {\n    context {\n      type\n      ... on ProductContextOfferType {\n        linkTo\n        offerType\n        __typename\n      }\n      __typename\n    }\n    variations {\n      priceRange {\n        minPrice\n        maxPrice\n        __typename\n      }\n      ...Variation @include(if: $includeVariations)\n      __typename\n    }\n    __typename\n  }\n  id\n  tpnb\n  tpnc\n  gtin\n  adId\n  baseProductId\n  title\n  brandName\n  shortDescription\n  defaultImageUrl\n  superDepartmentId\n  media {\n    defaultImage {\n      aspectRatio\n      __typename\n    }\n    __typename\n  }\n  quantityInBasket\n  superDepartmentName\n  departmentId\n  departmentName\n  aisleId\n  aisleName\n  shelfId\n  shelfName\n  displayType\n  productType\n  charges @include(if: $showDepositReturnCharge) {\n    ... on ProductDepositReturnCharge {\n      __typename\n      amount\n    }\n    __typename\n  }\n  averageWeight\n  bulkBuyLimit\n  maxQuantityAllowed: bulkBuyLimit\n  groupBulkBuyLimit\n  bulkBuyLimitMessage\n  bulkBuyLimitGroupId\n  timeRestrictedDelivery\n  restrictedDelivery\n  isInFavourites\n  isNew\n  isRestrictedOrderAmendment\n  maxWeight\n  minWeight\n  increment\n  details {\n    components {\n      ...Competitors\n      ...AdditionalInfo\n      __typename\n    }\n    __typename\n  }\n  catchWeightList {\n    price\n    weight\n    default\n    __typename\n  }\n  restrictions @include(if: $includeRestrictions) {\n    type\n    isViolated\n    message\n    __typename\n  }\n  reviews {\n    stats {\n      noOfReviews\n      overallRating\n      overallRatingRange\n      __typename\n    }\n    __typename\n  }\n  modelMetadata {\n    name\n    version\n    __typename\n  }\n}\n\nfragment Competitors on CompetitorsInfo {\n  competitors {\n    id\n    priceMatch {\n      isMatching\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment AdditionalInfo on AdditionalInfo {\n  isLowEverydayPricing\n  __typename\n}\n\nfragment Variation on VariationsType {\n  products {\n    id\n    baseProductId\n    variationAttributes {\n      attributeGroup\n      attributeGroupData {\n        name\n        value\n        attributes {\n          name\n          value\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment Sellers on ProductSellers {\n  __typename\n  results {\n    id\n    __typename\n    isForSale\n    status\n    seller {\n      id\n      name\n      logo {\n        url\n        __typename\n      }\n      __typename\n    }\n    price {\n      price: actual\n      unitPrice\n      unitOfMeasure\n      actual\n      __typename\n    }\n    promotions {\n      id\n      promotionType\n      startDate\n      endDate\n      description\n      unitSellingInfo\n      price {\n        beforeDiscount\n        afterDiscount\n        __typename\n      }\n      attributes\n      __typename\n    }\n    fulfilment(deliveryOptions: BEST) {\n      __typename\n      ... on ProductDeliveryType {\n        end\n        charges {\n          value\n          __typename\n        }\n        __typename\n      }\n    }\n  }\n}\n\nfragment FacetLists on ProductListFacetsType {\n  __typename\n  category\n  categoryId\n  facets {\n    facetId: id\n    facetName: name\n    binCount: count\n    isSelected: selected\n    __typename\n  }\n}\n\nfragment PageInformation on ListInfoType {\n  totalCount: total\n  pageNo: page\n  pageId\n  count\n  pageSize\n  matchType\n  offset\n  query {\n    searchTerm\n    actualTerm\n    queryPhase\n    __typename\n  }\n  __typename\n}\n\nfragment PopFilters on ProductListFacetsType {\n  category\n  categoryId\n  facets {\n    facetId: id\n    facetName: name\n    binCount: count\n    isSelected: selected\n    __typename\n  }\n  __typename\n}\n\nfragment facet on FacetInterface {\n  __typename\n  id\n  name\n  type\n  ... on FacetListType {\n    id\n    name\n    listValues: values {\n      name\n      value\n      isSelected\n      count\n      __typename\n    }\n    multiplicity\n    metadata {\n      description\n      footerText\n      linkText\n      linkUrl\n      __typename\n    }\n    __typename\n  }\n  ... on FacetMultiLevelType {\n    id\n    name\n    multiLevelValues: values {\n      children {\n        count\n        name\n        value\n        isSelected\n        __typename\n      }\n      appliedValues {\n        isSelected\n        name\n        value\n        __typename\n      }\n      __typename\n    }\n    multiplicity\n    metadata {\n      description\n      footerText\n      linkText\n      linkUrl\n      __typename\n    }\n    __typename\n  }\n  ... on FacetBooleanType {\n    booleanValues: values {\n      count\n      isSelected\n      value\n      name\n      __typename\n    }\n    __typename\n  }\n}\n"
		}
	]
)"""