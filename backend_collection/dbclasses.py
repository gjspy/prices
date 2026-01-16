from dbmanager.engine import Table, TableColumn, TableRow
from dbmanager.types import DSA
from typing import Any
from datetime import datetime



class Product(TableRow):
	table_name = "Products"

	db_id = TableColumn("PID", "INT", int, autoincrement = True)
	name = TableColumn("PName", "TINYTEXT", str, True)
	brand = TableColumn("BrandID", "INT", int, True)
	preferred_thumb = TableColumn("PreferredThumbID", "INT", int)
	packsize_count = TableColumn("PS_Count", "SMALLINT", int)
	packsize_sizeeach = TableColumn("PS_SizeEach", "FLOAT", float)
	packsize_unit = TableColumn("PS_Unit", "VARCHAR(2)", str)

	pkeys = ["PID"]


class ProductLink(TableRow):
	table_name = "ProductLinks"

	db_id = TableColumn("ID", "INT", int, autoincrement = True)
	product = TableColumn("PID", "INT", int, True)
	upc = TableColumn("UPC", "BIGINT", int)
	cin = TableColumn("CIN", "BIGINT", int, True)
	store = TableColumn("StoreID", "TINYINT", int, True)

	pkeys = ["ID"]


class PriceEntry(TableRow):
	table_name = "Prices"

	db_id = TableColumn("ID", "INT", int, autoincrement = True)
	product = TableColumn("PID", "INT", int, True)
	store = TableColumn("StoreID", "TINYINT", int, True)
	fetched_at = TableColumn("FetchedAt", "TIMESTAMP", datetime) # REQUIRED BUT HAS DEFAULT
	price_pence = TableColumn("PricePence", "SMALLINT", int, True)
	available = TableColumn("Available", "BOOL", bool)

	pkeys = ["EntryID"]

"""
class Offer(TableRow):
	table_name = "Offers"

	db_id = TableColumn("ID", int, autoincrement = True)
	store_given_id = TableColumn("StoreGivenID", int)
	store = TableColumn("Store", str, True)
	offer_type = TableColumn("OfferType", str)
	start_date = TableColumn("StartDate", datetime)
	end_date = TableColumn("EndDate", datetime)
	any_count = TableColumn("AnyFor_Count", int)
	for_price = TableColumn("AnyFor_Price", int)
	was_price = TableColumn("WasPrice", int)

	pkeys = ["ID"]

	class OfferHolder
	class Label
"""

class Rating(TableRow):
	table_name = "Ratings"

	db_id = TableColumn("ID", "INT", int, autoincrement = True)
	product = TableColumn("PID", "INT", int, True)
	store = TableColumn("StoreID", "TINYINT", int, True)
	avg = TableColumn("Average", "FLOAT", float, True)
	count = TableColumn("NVotes", "SMALLINT", int, True)

	pkeys = ["ID"]


class Image(TableRow):
	table_name = "Images"

	db_id = TableColumn("ID", "INT", int, autoincrement = True)
	product = TableColumn("PID", "INT", int, True)
	store = TableColumn("StoreID", "TINYINT", int, True)
	src = TableColumn("SourceURL", "TEXT", str, True)

	pkeys = ["ID"]


class Brand(TableRow):
	table_name = "Brands"

	db_id = TableColumn("ID", "INT", int, autoincrement = True)
	name = TableColumn("BName", "TINYTEXT", str)
	parent = TableColumn("ParentID", "INT", int)

	pkeys = ["ID"]

class NestedBrand(Brand):
	table_name = "2"

class Store(TableRow):
	table_name = "Stores"

	db_id = TableColumn("ID", "INT", int, autoincrement = True)
	name = TableColumn("SName", "TINYTEXT", str)

	pkeys = ["ID"]


ProductLink.product.joins = Product.db_id
PriceEntry.product.joins = Product.db_id
Rating.product.joins = Product.db_id
Image.product.joins = Product.db_id
Brand.parent.joins = Brand.db_id

Products = Table("Products", Product)
ProductLinks = Table("ProductLinks", ProductLink)
PriceEntries = Table("PriceEntries", PriceEntry)
#Offers = Table("Offers", Offer)
Ratings = Table("Ratings", Rating)
Images = Table("Images", Image)
Brands = Table("Brands", Brand)
Stores = Table("Stores", Store)







class Queries:

	@staticmethod
	def get_link_by_upc(upc: int):
		return ProductLinks.select( ProductLink.upc == upc )
	
	@staticmethod
	def get_link_by_cin(cin: int, store: str):
		return ProductLinks.select(
			(ProductLink.cin == cin) & (ProductLink.store == store))
	
	@staticmethod
	def get_link_by_some_id(data: DSA):
		upc: int | None = data.get("upc")

		if (upc): return Queries.get_link_by_upc(upc)

		cin: int | None = data.get("cin")
		store: str | None = data.get("store")
		if (cin and store): return Queries.get_link_by_cin(cin, store)

		# TODO: log
		return

	@staticmethod
	def get_link_by_ids(upcs: list[int], cin: int, store: int):
		cin_query = (ProductLink.cin == cin) & (ProductLink.store == store)

		if (len(upcs) > 0): return ProductLinks.select(
			(ProductLink.upc.in_(upcs)) | cin_query
		)

		return ProductLinks.select(cin_query)
			





"""
CREATE TABLE Products (
	ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    PName TINYTEXT,
    BrandName TINYTEXT,
    PS_Count SMALLINT UNSIGNED,
    PS_SizeEach FLOAT UNSIGNED,
    PS_Unit VARCHAR(2)
);

CREATE TABLE ProductLinks (
	LinkID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    OurProductID INT UNSIGNED NOT NULL,
    UPC INT(13) UNSIGNED,
    CIN INT(13) UNSIGNED NOT NULL,
    Store VARCHAR(20) NOT NULL,
    Unlinked BOOL NOT NULL
);

CREATE TABLE PriceHistories (
	EntryID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    OurProductID INT UNSIGNED NOT NULL,
    Store VARCHAR(20) NOT NULL,
    FetchedAt DATETIME NOT NULL,
    PricePence SMALLINT UNSIGNED NOT NULL,
    OfferId INT UNSIGNED,
    Available BOOL DEFAULT True
);

CREATE TABLE Offers (
	ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    StoreGivenID INT UNSIGNED,
    Store VARCHAR(20) NOT NULL,
    OfferType TINYTEXT,
    StartDate DATETIME,
    EndDate DATETIME,
    AnyFor_Count TINYINT UNSIGNED,
    AnyFor_Price SMALLINT UNSIGNED,
    WasPrice SMALLINT UNSIGNED
);

CREATE TABLE Ratings (
	ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    OurProductID INT UNSIGNED NOT NULL,
    Store VARCHAR(20) NOT NULL,
    Average FLOAT UNSIGNED NOT NULL,
    NVotes INT UNSIGNED NOT NULL
);

CREATE TABLE Images (
	ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    OurProductID INT UNSIGNED NOT NULL,
    Store VARCHAR(20) NOT NULL,
    URL TEXT NOT NULL
);
"""