from dotenv import dotenv_values
import asyncio

import json
import copy
import time

from backend_collection.collectors import algolia, graphql, clusters, akamai, aldi
from backend_collection.constants import regex
from backend_collection.storer import Writer
from backend_collection.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores, Store, Brand)
from dbmanager.engine import Database
from dbmanager.process import DBThread

import os
print(os.getcwd())

config = dotenv_values(".config")
env = dotenv_values(".env")
RESULTS_PER_SEARCH = 100

import sshtunnel
import logging

from backend_collection.log_handler import logger

SSH_USER = env["SSH_USER"]
SSH_HOST = env["SSH_HOST"]
SSH_PORT = env["SSH_PORT"]
SSH_KEY = env["SSH_KEY"]
DB_HOST = env["DB_HOST"]
DB_PORT = env["DB_PORT"]
DB_USER = env["DB_USER"]
DB_PASS = env["DB_PASS"]
DB_SCHM = env["DB_SCHM"]

from dbmanager import misc



#print(Brands.row.parent._references)
#print(Brands.row.new().parent._references)
#print(Brands.row.parent._references)

#print(id(Brands.row.parent), id(Brands.row.new().parent))


async def main(tunnel: sshtunnel.SSHTunnelForwarder):
	env["DB_PORT"] = tunnel.local_bind_port # type: ignore
	
	db = Database.from_env(env, logger)
	db.declare_tables(
		Products, ProductLinks, PriceEntries, Ratings, Images, Brands, Stores)
	
	succ = db.connect()
	print(succ, "connected:", db.is_connected)

	DB_PROCESS = DBThread(logger, db, asyncio.get_event_loop())
	DB_PROCESS.start()

	#s = Stores.row.new()
	#s.name.value = "tesco"
	#store_id = await DB_PROCESS.query(Stores.insert(s))
	#print(store_id[0])



	"""b = Brands.row.new()
	b.name.value = "CAT"
	b.parent.value = 1
	q = Brands.insert(b)
	brand_id = await DB_PROCESS.query(q)
	print(brand_id)"""

	b = Brands.row.new()
	b.parent.value = Stores.row.new()

	q = Brands.select(where = Brands.row.db_id == 2) # (2 CAT 1) b.parent.value.is_partial() = True
	#q = Brands.select(where = Brands.row.db_id == 2, join_all=True) # (2 CAT 1)
	print(q)
	b: Brand = (await DB_PROCESS.query(q))[0]
	print(b.to_storable(False), b.parent.ref_value.db_id.value, b.parent.value.is_partial())

# MAKE IT SO ALWAYS USE TableRow.TableCOlumn.value.TableColumn.value, and the 2nd tablecolumn may be "partial" if not laoded form db.
	#p = Products.row.new()
	#p.name.value = "mature cheese"



	return

	await manager.write_storable_group([
    {
      "type": "product",
      "data": {
        "name": "Mature Cheddar Cheese",
        "brand_name": "CATHEDRAL CITY",
        "packsize_count": 1,
        "packsize_sizeeach": 350.0,
        "packsize_unit": "g"
      }
    },
    {
      "type": "image",
      "data": {
        "url": "https://dm.emea.cms.aldi.cx/is/image/aldiprodeu/product/jpg/scaleWidth/1500/a3a42a2b-c96f-447c-8b7a-336fa01778b2/",
        "store_name": "ALDI"
      }
    },
    {
      "type": "price",
      "data": {
        "price_pence": 339,
        "available": True,
        "store_name": "ALDI"
      }
    },
    {
      "type": "rating",
      "data": {
        "avg": None,
        "count": None,
        "store_name": "ALDI"
      }
    },
    {
      "category": "Chilled Food",
      "department": "Cheese",
      "store_name": "ALDI"
    },
    {
      "type": "link",
      "data": {
        "store_name": "ALDI",
        "cin": 482344002
      }
    }
  ])
	db.disconnect()

	return

	collector = AlgoliaCollector(CONFIG, "ASDA_PRODUCTS", "ASDA", 100)

	storables = await this.search("cheese")
	print("res",storables)

	print("\n\n\n\n")

	for r in storables:
		print(r)







with sshtunnel.SSHTunnelForwarder(
		(SSH_HOST, int(SSH_PORT)), ssh_username = SSH_USER, ssh_pkey = SSH_KEY,
		remote_bind_address = (DB_HOST, int(DB_PORT))) as tunnel:

	assert tunnel
	print("tunnel active: ", tunnel and tunnel.is_active)

	asyncio.run(main(tunnel))









raise





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
asyncio.run(main())

#ata = json.load(open("test.json","r"))
#print(data, data.get("url"))

# TODO: IN STORAGE WRITER, DEAL WITH "NOT NULL". ALDI: RATINGS_COUNT AND AVG DO NOT EXIST, BUT STILL CREATE STORABLE.

# TODO: verify UPC, ensure is x digits, incase any change (ASDA IMAGE_ID stress)
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

	check TODOS. theres quite a few :)

	
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