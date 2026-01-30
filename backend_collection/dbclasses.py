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

	entry_created = TableColumn("EntryCreatedDate", "TIMESTAMP", datetime) # required false as db default
	verified = TableColumn("DetailsVerified", "BOOL", bool, default_value = False)


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
	
	fetched_time = TableColumn("FetchedAt", "TIMESTAMP", datetime) # DB handles default CURRENT_TIMESTAMP
	fetched_date = TableColumn("FetchedDate", "DATE", datetime) # DB handles default CURRENT_DATE

	price_pence = TableColumn("PricePence", "SMALLINT UNSIGNED", int, True)
	available = TableColumn("Available", "BOOL", bool) # DB handles default True


class Offer(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	store_given_id = TableColumn("StoreGivenID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	offer_type = TableColumn("OfferType", "TINYINT UNSIGNED", int, default_value = 0) # QUERY "error: true" BY type = 0
	start_date = TableColumn("StartDate", "DATETIME", datetime)
	end_date = TableColumn("EndDate", "DATETIME", datetime)
	
	requires_membership = TableColumn("RequiresMembership", "BOOL", bool)
	online_exclusive = TableColumn("OnlineExclusive", "BOOL", bool)


class OfferHolder(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	offer = TableColumn("OfferID", "INT UNSIGNED", int, True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)


class Label(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)

	entry_created = TableColumn("CreatedDate", "TIMESTAMP", datetime)
	entry_verified = TableColumn("VerifiedDate", "TIMESTAMP", datetime)

	label_type = TableColumn("LabelType", "TINYINT UNSIGNED", int, True, 0)
	param1 = TableColumn("Param1", "TEXT", str, True)


class Rating(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	avg = TableColumn("Average", "FLOAT UNSIGNED", float, True)
	count = TableColumn("NVotes", "SMALLINT UNSIGNED", int, True)


class Image(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product_id = TableColumn("PID", "INT UNSIGNED", int, True) # NO .reference AS CREATES CIRCULAR REF.
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	src = TableColumn("SourceURL", "TEXT", str, True)


class Brand(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	brand_name = TableColumn("BName", "TINYTEXT", str, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	parent = TableColumn("ParentID", "INT UNSIGNED", int)

class Store(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	name = TableColumn("SName", "TINYTEXT", str, True)


Products = Table("Products", Product)
ProductLinks = Table("ProductLinks", ProductLink)
PriceEntries = Table("Prices", PriceEntry)
Offers = Table("Offers", Offer)
OfferHolders = Table("OfferHolders", OfferHolder)
Labels = Table("Labels", Label)
Ratings = Table("Ratings", Rating)
Images = Table("Images", Image)
Brands = Table("Brands", Brand)
Stores = Table("Stores", Store)

Products.row.brand.references = Brands.row.db_id
Products.row.preferred_thumb.references = Images.row.db_id

Brands.row.store.references = Stores.row.db_id
Brands.row.parent.references = Brands.row.db_id

Images.row.store.references = Stores.row.db_id

ProductLinks.row.product.references = Products.row.db_id
ProductLinks.row.store.references = Stores.row.db_id

PriceEntries.row.product.references = Products.row.db_id
PriceEntries.row.store.references = Stores.row.db_id

Offers.row.store.references = Stores.row.db_id

OfferHolders.row.offer.references = Offers.row.db_id
OfferHolders.row.product.references = Products.row.db_id

Labels.row.product.references = Products.row.db_id
Labels.row.store.references = Stores.row.db_id

Ratings.row.product.references = Products.row.db_id
Ratings.row.store.references = Stores.row.db_id





class Queries:


	@staticmethod
	def get_link_by_ids(upcs: list[int], cin: int, store: int):
		cin_query = (ProductLinks.row.cin == cin) & (ProductLinks.row.store == store)

		if (len(upcs) > 0): return ProductLinks.select(
			where = (ProductLinks.row.upc.in_(upcs)) | cin_query
		)

		return ProductLinks.select(where = cin_query)
	
	@staticmethod
	def get_offer_by_store_data(store_id: int, store_given_id: int):
		return Offers.select(
			where = (
				(Offers.row.store == store_id) &
				(Offers.row.store_given_id == store_given_id))
		)
			





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