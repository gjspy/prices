from dotenv import dotenv_values
import asyncio

import json
import time

from backend_collection.collectors import algolia, graphql, clusters, akamai
#from backend_collection.constants import StoreNames

import os

config = dotenv_values(".config")
env = dotenv_values(".env")
RESULTS_PER_SEARCH = 100

#asda = algolia.AlgoliaCollector(env, config, ASDA_ENDPOINT, "ASDA_PRODUCTS", StoreNames.asda, RESULTS_PER_SEARCH) # good cfw
tesco = graphql.GQLCollector(env, config, RESULTS_PER_SEARCH) # good cfw
#mor = clusters.ClusterCollector(env, config, MORRISONS_ENDPOINT, StoreNames.morrisons, RESULTS_PER_SEARCH) # good cfw
#sains = akamai.AKMCollector(env, config, SAINSBURYS_ENDPOINT, StoreNames.sainsburys, RESULTS_PER_SEARCH) # bad cfw


import re

print(re.sub("", " ", " Italian Mozzarella Cheese"))

raise
"""async def main():
	#result = await tesco.search("cheese", True)
	
	d = json.load(open("TESCODebugResponse_1765497922j.json","r"))
	result = tesco.parse_data(d)

	with open(f"TestDSA_{int(time.time())}.json", "w") as f:
		json.dump(result, f, indent = 2)

asyncio.run(main())"""

import requests
import time

KEYWORD = "crisps"
N_ITEMS = 60

response = requests.post(
	"https://xapi.tesco.com",
	#data = { "operationName": "Search", "query": KEYWORD, "count": N_ITEMS, ... },
	headers={
		"Accept": "application/json",
		"user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
	}
)

response = requests.get(
	(f"https://www.sainsburys.co.uk/groceries-api/gol-services/product/v1/"
	"product?filter[keyword]={KEYWORD}&page_number=1&page_size={N_ITEMS}"),
	headers={
		"Accept": "application/json",
		"user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
	}
)

with open(f"{time.time()}","wb") as f:
	f.write(response.content)

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

	
eventually want to have //TESCO, //ASDA, //MORRISONS, SAINSBURYS, ALDI.
DECIDE if we want many promos per product. wouldnt be effort?

https://api.aldi.co.uk/v3/product-search?currency=GBP&serviceType=walk-in&q=Milk&limit=30&offset=0&sort=relevance&servicePoint=C092
ALDI REQUESTS DONT SHOW IN FIREFOX DEV TOOLS? LOOK AT CHROME.


ONCE SCRAPED DATA, BEFORE STORING IN DB, HAVE dataType CHECKER WHICH FLAGS INCORRECT VALUES.
THIS CAN BE IN ACCORDANCE TO DB API DECLARATIONS

should i implement collector to handle request of individual item?
streamline where data is stored (talking about having endpoint as a param. if class isnt reused, put endpoint ehre. so then headers, endpoint, EVERYTHIng should be in here. not store name though.)
relationships: ean to multiple products but also multiple products of same store? does 100% happen (sainsburys returns eans: [""]). hwo would i decide which to show?

LOOK INTO HAVING A PROXY (cloudflare worker! keep any eye on usage tho, max 100k/day free..)

"""