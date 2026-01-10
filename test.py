from dotenv import dotenv_values
import asyncio

import json
import time

from backend_collection.collectors import algolia, graphql, clusters, akamai
from backend_collection.constants import ASDA_ENDPOINT, MORRISONS_ENDPOINT, SAINSBURYS_ENDPOINT, StoreNames

import os
print(os.getcwd())

config = dotenv_values(".config")
env = dotenv_values(".env")
RESULTS_PER_SEARCH = 100

#asda = algolia.AlgoliaCollector(env, config, ASDA_ENDPOINT, "ASDA_PRODUCTS", StoreNames.asda, RESULTS_PER_SEARCH) # good cfw
tesco = graphql.GQLCollector(env, config, RESULTS_PER_SEARCH) # good cfw
#mor = clusters.ClusterCollector(env, config, MORRISONS_ENDPOINT, StoreNames.morrisons, RESULTS_PER_SEARCH) # good cfw
#sains = akamai.AKMCollector(env, config, SAINSBURYS_ENDPOINT, StoreNames.sainsburys, RESULTS_PER_SEARCH) # bad cfw

"""a = algolia.AlgoliaCollector({"ASDA_ALGOLIA_API_KEY":"", "ASDA_ALGOLIA_API_APP": ""}, "", "", "ASDA", 1)
print(a.parse_packsize({
					"ID": "1000226920906",
					"STATUS": "A",
					"PHARMACY_RESTRICTED": False,
					"CIN": "6744532",
					"START_DATE": 1588680000.0,
					"END_DATE": 1924948800.0,
					"NAME": "Milk Chocolate & Toffee Dessert 4 x 65g",
					"CS_YES": False,
					"SHOW_PRICE_CS": True,
					"SALES_TYPE": "Each",
					"IMAGE_ID": "3023290045282",
					"BRAND": "Rolo",
					"IS_BWS": False,
					"IS_FROZEN": False,
					"IS_SPONSORED": False,
					"LABEL": "",
					"PRICES": {
						"EN": {
							"OFFER": "List",
							"PRICE": 2.68,
							"PRICEPERUOM": 1.03077,
							"PRICEPERUOMFORMATTED": "�1.03/100GR"
						}
					},
					"PRIMARY_TAXONOMY": {
						"CAT_ID": "1215660378320",
						"CAT_NAME": "Chilled Food",
						"DEPT_ID": "1215341888021",
						"DEPT_NAME": "Yogurts & Desserts",
						"AISLE_ID": "910000975612",
						"AISLE_NAME": "Desserts",
						"SHELF_ID": "1215639170517",
						"SHELF_NAME": "Chocolate & Caramel Desserts"
					},
					"IS_FTO": False,
					"PRODUCT_TYPE": "STANDARD",
					"AVG_RATING": 4.5641,
					"RATING_COUNT": 78.0,
					"ICONS": [
						{
							"ID": "51000002",
							"ICON_NAME": "801_NoShellfish",
							"CLICKABLE": False,
							"IMAGE_URL": "https://ui.assets-asda.com/dm/_000_Icon?&$Icon-wapp$",
							"START_DATE": 1551700800,
							"END_DATE": 1551873600,
							"PRIORITY": 10440.0
						},
						{
							"ID": "55200007",
							"ICON_NAME": "Rainforest Alliance",
							"CLICKABLE": True,
							"IMAGE_URL": "https://ui.assets-asda.com/dm/Rainforest-Alliance-Seal-Icon?$Icon-wapp$&$Icon-wapp$&$Icon-wapp2x$",
							"PRIORITY": 540.0
						}
					],
					"PACK_SIZE": "4X65G",
					"STOCK": {
						"4565": 999
					},
					"MAX_QTY": 10,
					"objectID": "6744532",
					"_highlightDSA": {
						"ID": {
							"value": "1000226920906",
							"matchLevel": "none",
							"matchedWords": []
						},
						"CIN": {
							"value": "6744532",
							"matchLevel": "none",
							"matchedWords": []
						},
						"NAME": {
							"value": "Milk Chocolate & Toffee Dessert 4 x 65g",
							"matchLevel": "none",
							"matchedWords": []
						},
						"KEYWORDS": {
							"value": "pots of joy",
							"matchLevel": "none",
							"matchedWords": []
						},
						"BRAND": {
							"value": "Rolo",
							"matchLevel": "none",
							"matchedWords": []
						},
						"PRIMARY_TAXONOMY": {
							"AISLE_NAME": {
								"value": "<em>Desserts</em>",
								"matchLevel": "full",
								"fullyHighlighted": True,
								"matchedWords": [
									"cheese"
								]
							},
							"SHELF_NAME": {
								"value": "Chocolate & Caramel <em>Desserts</em>",
								"matchLevel": "full",
								"fullyHighlighted": False,
								"matchedWords": [
									"cheese"
								]
							}
						}
					}
				}))

print("\n\n\n")
print(a.parse_packsize({
					"ID": "910002366368",
					"STATUS": "A",
					"PHARMACY_RESTRICTED": False,
					"CIN": "5400878",
					"START_DATE": 1454932800.0,
					"END_DATE": 1924948800.0,
					"NAME": "Cheese & Onion Rolls 6 x 60g (360g)",
					"CS_YES": False,
					"SHOW_PRICE_CS": True,
					"SALES_TYPE": "Each",
					"IMAGE_ID": "5054781056386",
					"BRAND": "ASDA",
					"IS_BWS": False,
					"IS_FROZEN": False,
					"IS_SPONSORED": False,
					"LABEL": "",
					"PRICES": {
						"EN": {
							"OFFER": "List",
							"PRICE": 1.74,
							"PRICEPERUOM": 0.48333,
							"PRICEPERUOMFORMATTED": "48.3p/100GR"
						}
					},
					"PRIMARY_TAXONOMY": {
						"CAT_ID": "1215660378320",
						"CAT_NAME": "Chilled Food",
						"DEPT_ID": "1215661251124",
						"DEPT_NAME": "Party Food, Pies, Salads & Dips",
						"AISLE_ID": "1215663358403",
						"AISLE_NAME": "Sausage Rolls & Cocktail Sausages",
						"SHELF_ID": "1215685642832",
						"SHELF_NAME": "Cheese & Vegetarian Rolls"
					},
					"IS_FTO": False,
					"PRODUCT_TYPE": "STANDARD",
					"AVG_RATING": 4.3667,
					"RATING_COUNT": 30.0,
					"ICONS": [
						{
							"ID": "45100001",
							"ICON_NAME": "Freezable",
							"CLICKABLE": True,
							"IMAGE_URL": "https://ui.assets-asda.com/dm/icon_text?$text=Freezable",
							"END_DATE": 1684238400,
							"PRIORITY": 1085.0
						},
						{
							"ID": "51000002",
							"ICON_NAME": "801_NoShellfish",
							"CLICKABLE": False,
							"IMAGE_URL": "https://ui.assets-asda.com/dm/_000_Icon?&$Icon-wapp$",
							"START_DATE": 1551700800,
							"END_DATE": 1551873600,
							"PRIORITY": 10440.0
						},
						{
							"ID": "59600047",
							"ICON_NAME": "Typically fresh for 6 days",
							"CLICKABLE": True,
							"IMAGE_URL": "https://ui.assets-asda.com/dm/produce-6-days-icon?",
							"START_DATE": 1625227200,
							"END_DATE": 1914408000,
							"PRIORITY": 23.0
						},
						{
							"ID": "59600339",
							"ICON_NAME": "Follow Air Fryer Manufacturer�s Instructions for Cooking Guidelines",
							"CLICKABLE": True,
							"IMAGE_URL": "https://ui.assets-asda.com/dm/Air-Fryer-Online-Icon?&$Icon-wapp$",
							"START_DATE": 1667390400,
							"END_DATE": 1924948800,
							"PRIORITY": 288.0
						}
					],
					"PACK_SIZE": "360G",
					"STOCK": {
						"4565": 999
					},
					"MAX_QTY": 10,
					"objectID": "5400878",
					"_highlightDSA": {
						"ID": {
							"value": "910002366368",
							"matchLevel": "none",
							"matchedWords": []
						},
						"CIN": {
							"value": "5400878",
							"matchLevel": "none",
							"matchedWords": []
						},
						"NAME": {
							"value": "<em>Cheese</em> & Onion Rolls 6 x 60g (360g)",
							"matchLevel": "full",
							"fullyHighlighted": False,
							"matchedWords": [
								"cheese"
							]
						},
						"BRAND": {
							"value": "ASDA",
							"matchLevel": "none",
							"matchedWords": []
						},
						"PRIMARY_TAXONOMY": {
							"AISLE_NAME": {
								"value": "Sausage Rolls & Cocktail Sausages",
								"matchLevel": "none",
								"matchedWords": []
							},
							"SHELF_NAME": {
								"value": "<em>Cheese</em> & Vegetarian Rolls",
								"matchLevel": "full",
								"fullyHighlighted": False,
								"matchedWords": [
									"cheese"
								]
							}
						}
					}
				},))
"""

#print(tesco._parse_packsize_str("Castello Extra Creamy Brie Cheese 200g  g"))

async def main():
	#result = await tesco.search("cheese", True)
	#result = await sains.search("cheese", True)
	#print(result)
	
	d = json.load(open("TESCODebugResponse_1765497922j.json","r"))
	result = tesco.parse_data(d)

	with open(f"TestDSA_{int(time.time())}.json", "w") as f:
		json.dump(result, f, indent = 2)

asyncio.run(main())

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