from dbmanager.engine import Table, TableColumn, TableRow
from datetime import datetime



class Store(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	name = TableColumn("SName", "TINYTEXT", str, True)

Stores = Table("Stores", Store)


class Brand(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	brand_name = TableColumn("BName", "TINYTEXT", str, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	parent = TableColumn("ParentID", "INT UNSIGNED", int)

Brands = Table("Brands", Brand)

Brands.row.store.references = Stores.row.db_id
Brands.row.parent.references = Brands.row.db_id


class Product(TableRow):
	db_id = TableColumn("PID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	name = TableColumn("PName", "TINYTEXT", str, True)
	brand = TableColumn("BrandID", "INT UNSIGNED", int, True)
	packsize_count = TableColumn("PS_Count", "SMALLINT UNSIGNED", int)
	packsize_sizeeach = TableColumn("PS_SizeEach", "FLOAT UNSIGNED", float)
	packsize_unit = TableColumn("PS_Unit", ("VARCHAR", 2), str)

	entry_created = TableColumn("EntryCreatedDate", "TIMESTAMP", datetime) # required false as db default
	verified = TableColumn("DetailsVerified", "BOOL", bool, default_value = False)

Products = Table("Products", Product)

Products.row.brand.references = Brands.row.db_id


class ProductLink(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	upc = TableColumn("UPC", "BIGINT UNSIGNED", int)
	cin = TableColumn("CIN", "BIGINT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)

ProductLinks = Table("ProductLinks", ProductLink)

ProductLinks.row.product.references = Products.row.db_id
ProductLinks.row.store.references = Stores.row.db_id


class PriceEntry(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	
	fetched_time = TableColumn("FetchedAt", "TIMESTAMP", datetime) # DB handles default CURRENT_TIMESTAMP
	fetched_session = TableColumn("FetchedSession", "INT UNSIGNED", int)

	price_pence = TableColumn("PricePence", "SMALLINT UNSIGNED", int, True)
	available = TableColumn("Available", "BOOL", bool) # DB handles default True

PriceEntries = Table("Prices", PriceEntry)

PriceEntries.row.product.references = Products.row.db_id
PriceEntries.row.store.references = Stores.row.db_id


class Offer(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	store_given_id = TableColumn("StoreGivenID", "BIGINT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	offer_type = TableColumn("OfferType", "TINYINT UNSIGNED", int, default_value = 0) # QUERY "error: true" BY type = 0
	start_date = TableColumn("StartDate", "DATETIME", datetime)
	end_date = TableColumn("EndDate", "DATETIME", datetime)
	
	requires_membership = TableColumn("RequiresMembership", "BOOL", bool)
	online_exclusive = TableColumn("OnlineExclusive", "BOOL", bool)

Offers = Table("Offers", Offer)

Offers.row.store.references = Stores.row.db_id


class OfferHolder(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	offer = TableColumn("OfferID", "INT UNSIGNED", int, True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)

OfferHolders = Table("OfferHolders", OfferHolder)

OfferHolders.row.offer.references = Offers.row.db_id
OfferHolders.row.product.references = Products.row.db_id


class Label(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)

	entry_created = TableColumn("CreatedDate", "TIMESTAMP", datetime)
	updated_date = TableColumn("UpdatedDate", "TIMESTAMP", datetime)

	label_type = TableColumn("LabelType", "TINYINT UNSIGNED", int, True, 0)
	param1 = TableColumn("Param1", "TEXT", str, True)

Labels = Table("Labels", Label)

Labels.row.product.references = Products.row.db_id
Labels.row.store.references = Stores.row.db_id


class Keyword(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	data = TableColumn("PData", "TINYTEXT", str, True)

Keywords = Table("Keywords", Keyword)

Keywords.row.product.references = Products.row.db_id
Keywords.row.store.references = Stores.row.db_id


class Image(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True) # NO .reference AS CREATES CIRCULAR REF.
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	src = TableColumn("SourceURL", "TEXT", str, True)
	preferred = TableColumn("IsPreferred", "BOOL", bool, default_value = False)

Images = Table("Images", Image)

Images.row.product.references = Products.row.db_id
Images.row.store.references = Stores.row.db_id


class Rating(TableRow):
	db_id = TableColumn("ID", "INT UNSIGNED", int, primary_key = True, autoincrement = True)
	product = TableColumn("PID", "INT UNSIGNED", int, True)
	store = TableColumn("StoreID", "TINYINT UNSIGNED", int, True)
	avg = TableColumn("Average", "FLOAT UNSIGNED", float, True)
	count = TableColumn("NVotes", "SMALLINT UNSIGNED", int, True)

Ratings = Table("Ratings", Rating)

Ratings.row.product.references = Products.row.db_id
Ratings.row.store.references = Stores.row.db_id



class Queries:


	@staticmethod
	def get_link_by_ids(upcs: list[int], cin: int, store: int):
		cin_query = (ProductLinks.row.cin == cin) & (ProductLinks.row.store == store)

		if (len(upcs) > 0): return ProductLinks.select(
			where = (ProductLinks.row.upc.in_(upcs)) | cin_query
		)

		return ProductLinks.select(
			[ProductLinks.row.product],
			where = cin_query)

	@staticmethod
	def get_offer_by_store_data(store_id: int, store_given_id: int):
		return Offers.select(
			[Offers.row.db_id, Offers.row.end_date],
			where = (
				(Offers.row.store == store_id) &
				(Offers.row.store_given_id == store_given_id)))