from enum import Enum

class SortOption(str, Enum):
	relevance = "relevance"
	pricelth = "price-lth"
	pricehtl = "price-htl"
	# TODO: rating?