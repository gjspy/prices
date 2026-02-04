from dotenv import dotenv_values
import asyncio

import json
import copy
import time

from backend_collection.collectors import algolia, graphql, clusters, akamai, aldi
from backend_collection.constants import regex, StoreNames, clean_string
from backend_collection.storer import Writer
from backend_collection.state import State
from backend_collection.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores, Offers, OfferHolders, Keywords, Labels, Store, Brand, Product, ProductLink)
from dbmanager.engine import Database, LOWER, NOT
from dbmanager.process import DBThread

from backend_collection.types import DSA
import os
import re

config = dotenv_values(".config")
env = dotenv_values(".env")
RESULTS_PER_SEARCH = 100

print(os.getcwd())

import sshtunnel

from backend_collection.log_handler import get_logger
logger = get_logger()

SSH_USER = env["SSH_USER"]
SSH_HOST = env["SSH_HOST"]
SSH_PORT = env["SSH_PORT"]
SSH_KEY = env["SSH_KEYY"]
DB_HOST = env["DB_HOST"]
DB_PORT = env["DB_PORT"]
DB_USER = env["DB_USER"]
DB_PASS = env["DB_PASS"]
DB_SCHM = env["DB_SCHM"]

from dbmanager import misc

"""
asda = algolia.AlgoliaCollector(env, config, RESULTS_PER_SEARCH) # good cfw
tesco = graphql.GQLCollector(env, config, RESULTS_PER_SEARCH) # good cfw
mor = clusters.ClusterCollector(env, config, RESULTS_PER_SEARCH) # good cfw
sains = akamai.AKMCollector(env, config, RESULTS_PER_SEARCH) # bad cfw
ald = aldi.ALDCollector(env, config, 60) # "Page limit must be equal to some of there values: [12,16,24,30,32,48,60]"
"""
#c = (Products.row.brand == 12) | ((Products.row.db_id == 1) & (Products.row.name == "hello"))
#print(c)


#print(re.sub(r"h=\d+&w=\d+", "h=1250&w=1250", "https://digitalcontent.api.tesco.com/v2/media/ghs/020b73bb-fb75-45d6-aced-00bd39f357b1/7d8f014f-d9fa-4df0-92ab-922dea766b5e.jpeg?h=225&w=225"))
"""TODO:::::::::::::::::::::::::::::::::::::::
image sizing for asda, sains, ald
QUERY BY UPC DOESNT WORK? DOESNT EVER PUT IN_?
THEN RUN AGAIN.
REMOVE IMG CFW FOR SAINS.


"""
"""
async def main():
	result = await tesco.search("cheese", True)


	with open(f"TestResult_{int(time.time())}.json", "w") as f:
		json.dump(result, f, indent = 2)

asyncio.run(main())

raise"""
#print(bool(set([2,3]) - set([1,2,3])))
#raise

#print(Brands.row.parent._references)
#print(Brands.row.new().parent._references)
#print(Brands.row.parent._references)

#print(id(Brands.row.parent), id(Brands.row.new().parent))
"""v = Ratings.row.new()
v.avg.value = 1
v.count.value = 10

q=Ratings.insert(v, on_duplicate_key_update=True)

print(q)
"""
#print("." + clean_string(" Mature Cheese( ), ") + ".")
#raise

#print(id(Brands.row.parent.references), id(Brand.parent.references),id(Brands.row.new().parent.references))
#print(id(ProductLinks.row.store.references), id(ProductLink.store.references),id(ProductLinks.row.new().store.references))

async def main(tunnel: sshtunnel.SSHTunnelForwarder):
	env["DB_PORT"] = tunnel.local_bind_port # type: ignore
	print(env["DB_PORT"])
	
	db = Database.from_env(env, logger)
	db.declare_tables(
		Products, ProductLinks, PriceEntries, Ratings, Images, Brands, Stores,
		Offers, Keywords, OfferHolders, Labels)
	
	succ = db.connect()
	print(succ, "connected:", db.is_connected)

	DB_PROCESS = DBThread(logger, db, asyncio.get_event_loop(), "state/state.json")
	DB_PROCESS.start()

	raise

	s = State()
	s.store_names = {
		StoreNames.unknown: 0,
		StoreNames.tesco: 1,
		StoreNames.asda: 2,
		StoreNames.morrisons: 3,
		StoreNames.sainsburys: 4,
		StoreNames.aldi: 5
	}

	w = Writer(env, logger, DB_PROCESS, s)

	"""c = (ProductLinks.row.upc.in_([5057753934453, 5000436510826, 5057967013944])) | ((ProductLinks.row.cin == 1) & (ProductLinks.row.store == 2))
	print(c)
	print(c.safe())
	
	a = ProductLinks.select(where = c)
	print(a)

	r = await DB_PROCESS.query(a)
	print(r)

	time.sleep(10)

	db.disconnect()"""

	#d = json.load(open("TESCODebugResponse_1769611222j.json","r"))
	#with open("ASDADebugResponse_1770057833j copy.json","r") as f:
	#with open("TESCODebugResponse_1770120473j.json","r") as f:
	#with open("ALDIDebugResponse_1770157574j.json","r") as f:
	with open("SAINSBURYSDebugResponse_1770163260j.json","r") as f:
		d = json.load(f)

	#result = tesco.parse_data(d)
	#result = asda.parse_data(d)
	#result = ald.parse_data(d)
	result = sains.parse_data(d)
	#result = await mor.search("bread", True)
	#result = await asda.search("cheese", True)
	#result = await tesco.search("cheese", True)
	#result = await ald.search("cheese", True)
	#result = await mor.search("cheese", True)
	#result = await sains.search("cheese", True)


	t = time.time()
	last = t
	for i, v in enumerate(result):
		#print(i, v)
		if (i <= 4): continue

		await w.write_storable_group(v, 1)#1770155790/60/60/24

		this = time.time()
		print(i, "this took", this - last)
		last = this
		break
	
	print("done omg, all", len(result), "in", time.time() - t)

	#try: time.sleep(100) # THIS IS BLOCKING db_thread. TODO ENSURE USING asyncio.sleep()
	#except: pass
	try: await asyncio.sleep(1000)
	except: pass

	db.disconnect()
	print("disconnect")
	#r = await w.get_image_data("")
	#print(r)
	#with open("test.png", "wb") as f:
	#	f.write(r.content)
	"""q = Brands.select([LOWER(Brands.row.name)], objectify_results=False)
	print(q)
	a = await DB_PROCESS.query(q)
	print(a)
"""

	return
	#s = Stores.row.new()
	#s.name.value = "tesco"
	#store_id = await DB_PROCESS.query(Stores.insert(s))
	#print(store_id[0])


	db_row = Images.row.new()
	db_row.product_id.plain_value = 1
	db_row.store.ref_value(Store).db_id.value = 2

	db_row.src.value = "url"

	resp = await DB_PROCESS.query(Images.insert(db_row))
	print("RESP", resp)





	"""b = Brands.row.new()
	b.name.value = "CAT"
	b.parent.value = 1
	q = Brands.insert(b)
	brand_id = await DB_PROCESS.query(q)
	print(brand_id)"""

	#b = Brands.row.new()
	#b.parent.value = Stores.row.new()


	return

	q = Brands.select(where = Brands.row.db_id == 2) # (2 CAT 1) b.parent.value.is_partial() = True
	#q = Brands.select(where = Brands.row.db_id == 2, join_all=True) # (2 CAT 1)
	print(q)
	b: Brand = (await DB_PROCESS.query(q))[0]
	print(b.to_storable(False), b.parent.ref_value.db_id.value, b.parent.value.is_partial())

# MAKE IT SO ALWAYS USE TableRow.TableCOlumn.value.TableColumn.value, and the 2nd tablecolumn may be "partial" if not laoded form db.
	#p = Products.row.new()
	#p.name.value = "mature cheese"





logger.critical("MUST RECREATE TABLES BEFORE DEPLOY, FK DELETED IN Images, NO FKS IN Keywords")


with sshtunnel.SSHTunnelForwarder(
		(SSH_HOST, int(SSH_PORT)), ssh_username = SSH_USER, ssh_pkey = SSH_KEY,
		remote_bind_address = (DB_HOST, int(DB_PORT))) as tunnel:

	assert tunnel
	print("tunnel active: ", tunnel and tunnel.is_active)

	asyncio.run(main(tunnel))

logger.critical("MUST ADD CATEGORIES")








"""

# TODO: MEAL DEAL MULTIBUY, STORE "main", "side", "snack", "dessert", "drink"


asda = algolia.AlgoliaCollector(env, config, RESULTS_PER_SEARCH) # good cfw
tesco = graphql.GQLCollector(env, config, RESULTS_PER_SEARCH) # good cfw
mor = clusters.ClusterCollector(env, config, RESULTS_PER_SEARCH) # good cfw
sains = akamai.AKMCollector(env, config, RESULTS_PER_SEARCH) # bad cfw
ald = aldi.ALDCollector(env, config, 60) # "Page limit must be equal to some of there values: [12,16,24,30,32,48,60]"

async def main():
	#result = await ald.search("cheese", True)
	#print(result)
	
	d = json.load(open("ALDIDebugResponse_1768250557j.json","r"))
	result = ald.parse_data(d)

	with open(f"TestResult_{int(time.time())}.json", "w") as f:
		json.dump(result, f, indent = 2)
##
#asyncio.run(main())

#ata = json.load(open("test.json","r"))
#print(data, data.get("url"))"""


"""from urllib import parse

print(parse.unquote("https&#58;&#47;&#47;errors&#46;edgesuite&#46;net&#47;18&#46;cc61002&#46;1765401432&#46;82c9e435"))


import requests

response = requests.get(
	"https://www.sainsburys.co.uk/groceries-api/gol-services/product/v1/product?filter[keyword]=pepsi&citrus_max_number_ads=5&page_number=1&page_size=60&sort_order=FAVOURITES_FIRST&salesWindow=1",
	headers={
		"Accept": "application/json",
		"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
	}#sains.get_headers()
)

print(response)

with open(f"{time.time()}","wb") as f:
	f.write(response.content)"""




"""
HAPPENING NOW:
ASDA and TESCO seem complete:
	-need to inspect for more offer types
	-does "Any x for x" correctly, rollbacks correctlys
	-packsize works

	
eventually want to have //TESCO, //ASDA, //MORRISONS, //SAINSBURYS, //ALDI.
//DECIDE if we want many promos per product. wouldnt be effort?

https://api.aldi.co.uk/v3/product-search?currency=GBP&serviceType=walk-in&q=Milk&limit=30&offset=0&sort=relevance&servicePoint=C092
ALDI REQUESTS DONT SHOW IN FIREFOX DEV TOOLS? LOOK AT CHROME.


ONCE SCRAPED DATA, BEFORE STORING IN DB, HAVE dataType CHECKER WHICH FLAGS INCORRECT VALUES.
THIS CAN BE IN ACCORDANCE TO DB API DECLARATIONS

should i implement collector to handle request of individual item?
streamline where data is stored (talking about having endpoint as a param. if class isnt reused, put endpoint ehre. so then headers, endpoint, EVERYTHIng should be in here. not store name though.)
relationships: ean to multiple products but also multiple products of same store? does 100% happen (sainsburys returns eans: [""]). hwo would i decide which to show?

LOOK INTO HAVING A PROXY (cloudflare worker! keep any eye on usage tho, max 100k/day free..)

"""