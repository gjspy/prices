from backend_collection.collectors import basecollector

import asyncio

this = basecollector.AlgoliaCollector({}, "ASDA_PRODUCTS")




async def main():
	res = this.search("cheese")
	print(res)




asyncio.run(main)