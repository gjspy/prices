from dbmanager.engine import Table, TableColumn, TableRow
from dbmanager.types import DSA
from typing import Any
from datetime import datetime



class Product(TableRow):
	db_id = TableColumn("PID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	name = TableColumn("PName", "TINYTEXT", str, True)
	brand = TableColumn("BrandID", "INT UNSIGNED", int, True)
	preferred_thumb = TableColumn("PreferredThumbID", "INT UNSIGNED", int)
	packsize_count = TableColumn("PS_Count", "SMALLINT UNSIGNED", int)
	packsize_sizeeach = TableColumn("PS_SizeEach", "FLOAT UNSIGNED", float)
	packsize_unit = TableColumn("PS_Unit", ("VARCHAR", 2), str)


class ProductLink(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	upc = TableColumn("UPC", "BIGINT UNSIGNED", int)
	cin = TableColumn("CIN", "BIGINT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)


class PriceEntry(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	fetched_at = TableColumn("FetchedAt", "TIMESTAMP", datetime) # REQUIRED BUT HAS DEFAULT TODO decide db does it or not?
	price_pence = TableColumn("PricePence", "SMALLINT UNSIGNED", int, True)
	available = TableColumn("Available", "BOOL", bool)

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

	# needs OfferHolder, many[offer] -> many[product]
	# always store offer data in JSON? is fast
	# have field OfferTypeRecognised in SQL, so all offers stored together (error of offer gathered)
	# NO, just have OfferType = 0 (unknown)

	pkeys = ["ID"]

	class OfferHolder
	class Label
"""

class Rating(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	avg = TableColumn("Average", "FLOAT UNSIGNED", float, True)
	count = TableColumn("NVotes", "SMALLINT UNSIGNED", int, True)


class Image(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	src = TableColumn("SourceURL", "TEXT", str, True)


class Brand(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	name = TableColumn("BName", "TINYTEXT", str, True)
	parent = TableColumn("ParentID", "INT UNSIGNED", int)

class Store(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	name = TableColumn("SName", "TINYTEXT", str, True)

Products = Table("Products", Product)
ProductLinks = Table("ProductLinks", ProductLink)
PriceEntries = Table("PriceEntries", PriceEntry)
#Offers = Table("Offers", Offer)
Ratings = Table("Ratings", Rating)
Images = Table("Images", Image)
Brands = Table("Brands", Brand)
Stores = Table("Stores", Store)

Products.row.brand.references = Brands.row.db_id
Products.row.preferred_thumb.references = Images.row.db_id

Brands.row.parent.references = Brands.row.db_id

# CIRCULAR ProductID
Images.row.store.references = Stores.row.db_id

ProductLinks.row.product.references = Products.row.db_id
ProductLinks.row.store.references = Stores.row.db_id

PriceEntries.row.product.references = Products.row.db_id
PriceEntries.row.store.references = Stores.row.db_id

# OFFERS

Ratings.row.store.references = Stores.row.db_id





class Queries:


	@staticmethod
	def get_link_by_ids(upcs: list[int], cin: int, store: int):
		cin_query = (ProductLink.cin == cin) & (ProductLink.store == store)

		if (len(upcs) > 0): return ProductLinks.select(
			where = (ProductLink.upc.in_(upcs)) | cin_query
		)

		return ProductLinks.select(where = cin_query)
			





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