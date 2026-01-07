from dbmanager.engine import Table, TableColumn, TableRow
from typing import Any
from datetime import datetime



class Product(TableRow):
	table_name = "Products"

	db_id = TableColumn("ID", int, autoincrement = True)
	name = TableColumn("PName", str) # TODO MAX LEN 255 CHARS
	brand_name = TableColumn("BrandName", str)
	packsize_count = TableColumn("PS_Count", int)
	packsize_sizeeach = TableColumn("PS_SizeEach", float)
	packsize_unit = TableColumn("PS_Unit", str) # max len 2
	# TODO storeGatheredDataFrom? dateGatheredData?

	pkeys = ["ID"]


class ProductLink(TableRow):
	table_name = "ProductLinks"

	db_id = TableColumn("LinkID", int, autoincrement = True)
	product_id = TableColumn("OurProductID", int, True)
	upc = TableColumn("UPC", int)
	cin = TableColumn("CIN", int, True)
	store = TableColumn("Store", str, True)
	unlinked = TableColumn("Unlinked", bool, True)

	pkeys = ["LinkID"]


class PriceEntry(TableRow):
	table_name = "PriceHistories"

	db_id = TableColumn("EntryID", int, autoincrement = True)
	product_id = TableColumn("OurProductID", int, True)
	store = TableColumn("Store", str, True)
	fetched_at = TableColumn("FetchedAt", datetime, True)
	price_pence = TableColumn("PricePence", int, True)
	offer_id = TableColumn("OfferID", int)
	available = TableColumn("Available", bool)

	pkeys = ["EntryID"]
	fkeys = ["OfferID"] # ? CONSTRAINT FOREIGN KEY in CREATE TABLE


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


class Rating(TableRow): # TODO: query if this exists before creating new, update if so.
	table_name = "Ratings"

	db_id = TableColumn("ID", int, autoincrement = True)
	product_id = TableColumn("OurProductID", int, True)
	store = TableColumn("Store", str, True)
	avg = TableColumn("Average", float, True)
	count = TableColumn("NVotes", int, True)

	pkeys = ["ID"]


class Image(TableRow):
	table_name = "Images"

	db_id = TableColumn("ID", int, autoincrement = True)
	product_id = TableColumn("OurProductID", int, True)
	store = TableColumn("Store", str, True)
	src = TableColumn("URL", str, True)




ProductLink.product_id.joins = Product.db_id
PriceEntry.product_id.joins = Product.db_id
PriceEntry.offer_id.joins = Offer.db_id
Rating.product_id.joins = Product.db_id
Image.product_id.joins = Product.db_id


Products = Table("Products", Product)
ProductLinks = Table("ProductLinks", ProductLink)
PriceEntries = Table("PriceEntries", PriceEntry)
Offers = Table("Offers", Offer)
Ratings = Table("Ratings", Rating)
Images = Table("Images", Image)








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