from dbmanager.engine import Database

from backend.log_handler import get_logger, CustomLogger
from backend.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores, Offers, OfferHolders, Labels, Keywords,

	Store)

from backend.api.constants import SortOption




async def get_by_query():
	...










def build_search_query(query: str, page: int, sort_mode: SortOption):
	
