from dotenv import dotenv_values
from os import path
import asyncio

from backend.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores, Offers, OfferHolders, Keywords, Labels, Store, Brand, Product, ProductLink)
from dbmanager.engine import Database
from dbmanager.process import DBThread

config = dotenv_values(".config")
env = dotenv_values(".env")

import sshtunnel # type: ignore

from backend.log_handler import get_logger
logger = get_logger("collectiontest", path.join("state/teststate.json"))



async def example_1(DB_PROCESS: DBThread):
	# Example 1: Regular flow, not affected by locks. Would run
	# without these being implemented.

	select1_1 = ProductLinks.select(
		where = (ProductLinks.row.upc == 5000295148154)
	)
	resp1_1 = await DB_PROCESS.query_withlock(select1_1, ProductLinks)
	lock_1: int = resp1_1["lock_id"]

	results: list[ProductLink] = resp1_1.get("fetchall") or []

	if (len(results) > 0): # FOUND!
		DB_PROCESS.close_lock(lock_1) # close lock as no other query will.
		return results[0].product.ref_value(Product).db_id.plain_value

	new_product = Products.row.from_dict({
		"name": "Extra Mature Cheddar Cheese",
		"packsize_count": 1,
		"packsize_sizeeach": 550.0,
		"packsize_unit": "g"
	}, False)

	new_product.brand.ref_value(Brand).db_id.value = 1879 # 'Cathedral City'

	create1_1 = Products.insert(new_product)

	# lock is not needed here, as lock is only on ProductLinks table.
	# Products is free to be queried on, always, because ProductLinks
	# always has to be accessed first (during collection)

	# is fine to run .query, not .query_withlock, as the entire purpose
	# of the lock is to yield select1_1 until the lock is free. therefore
	# create1_1 cannot ever happen before the lock is released.
	resp1_2 = await DB_PROCESS.query(create1_1)

	new_link = ProductLinks.row.from_dict({
		"upc": 5000295148154,
		"cin": 6594606
	})
	
	new_link.product.ref_value(Product).db_id.value = resp1_2["lastrowid"]
	new_link.store.ref_value(Store).db_id.value = 2

	create2_2 = ProductLinks.insert(new_link)

	# back to needing the lock, as we're inserting into ProductLinks.
	# 'lock_id' is in some way a password, which we provide to prove
	# it is our turn to access the table.
	# This is the last query in this process, so close the lock.
	resp1_3 = await DB_PROCESS.query_withlock(
		create2_2, lock_id = lock_1, close_lock_after_query = True)
	
	logger.progress(f"Found Product ID {resp1_2["lastrowid"]}")
	


	''' RELEVANT collection.log RESULTS:
	06-02-26 14:41:14 - PROGRESS IN MainThread           :  Connected: True
	06-02-26 14:41:18 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 14:41:18 - INFO     IN DBThread             :  Completed #0 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 0 ON ProductLinks. Success: True. Todo: 0
	06-02-26 14:41:21 - DEBUG    IN DBThread             :  INSERT INTO Products (BrandID, EntryCreatedDate, PName, PS_Count, PS_SizeEach, PS_Unit, DetailsVerified) VALUES (%s, %s, %s, %s, %s, %s, %s); < (1879, None, 'Extra Mature Cheddar Cheese', 1, 550.0, 'g', False) < []
	06-02-26 14:41:21 - INFO     IN DBThread             :  Completed #1 (INSERT 1x Product), 2 results returned. Success: True. Todo: 1
	06-02-26 14:41:24 - DEBUG    IN DBThread             :  INSERT INTO ProductLinks (CIN, PID, StoreID, UPC) VALUES (%s, %s, %s, %s); < (6594606, 1191, 2, 5000295148154) < []
	06-02-26 14:41:24 - INFO     IN DBThread             :  Completed #2 (INSERT 1x ProductLink), 2 results returned. CLOSED LOCK 0. Success: True. Todo: 0
	06-02-26 14:41:24 - PROGRESS IN DBThread             :  Found Product ID 1191
	06-02-26 14:41:54 - PROGRESS IN MainThread           :  disconnect
	
	# Correct! we can see lock was created by ProductLink SELECT, ignored by Product INSERT, and closed by ProductLink INSERT.

	06-02-26 14:42:59 - PROGRESS IN MainThread           :  Connected: True
	06-02-26 14:43:04 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 14:43:04 - INFO     IN DBThread             :  Completed #0 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 0 ON ProductLinks. Success: True. Todo: 0
	06-02-26 14:43:04 - PROGRESS IN MainThread           :  Found Product ID 1191
	06-02-26 14:43:07 - INFO     IN DBThread             :  Completed #0 URGENT ACTION (no SQL), 0 results returned. CLOSED LOCK 0. Success: True. Todo: 0
	06-02-26 14:43:37 - PROGRESS IN MainThread           :  disconnect

	# Correct! we can see lock was created by ProductLink SELECT, and closed individually as PID was found.

	Now we need to make sure something can execute on ProductLinks after a lock is closed.
	'''


async def example_2(DB_PROCESS: DBThread):
	# Example 2: Non-clashing flow, moderated by locks. Would run
	# fine without them, but here they impede processing to handle one
	# by one.

	async def thread2():
		select2_1 = ProductLinks.select(
			where = (ProductLinks.row.upc == 5057172404735) # DIFFERENT UPC
		)

		resp2_1 = await DB_PROCESS.query_withlock(select2_1, ProductLinks)
		lock_2: int = resp2_1["lock_id"]

		results: list[ProductLink] = resp2_1.get("fetchall") or []

		if (len(results) > 0): # FOUND!
			DB_PROCESS.close_lock(lock_2) # close lock as no other query will.
			pid = results[0].product.ref_value(Product).db_id.plain_value

			logger.progress(f"Thread2 Found Product ID {pid}")
			return pid

		new_product = Products.row.from_dict({ # DIFFERENT PRODUCT
			"name": "British Mild Cheddar",
			"packsize_count": 1,
			"packsize_sizeeach": 400.0,
			"packsize_unit": "g"
		}, False)

		new_product.brand.ref_value(Brand).db_id.value = 1880 # 'ASDA' (own-brand)

		create2_1 = Products.insert(new_product)

		# again, lock is not needed here as we yielded in the selects.
		# we have full control.
		resp2_2 = await DB_PROCESS.query(create2_1)

		new_link = ProductLinks.row.from_dict({
			"upc": 5057172404735,
			"cin": 6793870
		})

		new_link.product.ref_value(Product).db_id.value = resp2_2["lastrowid"]
		new_link.store.ref_value(Store).db_id.value = 2

		create2_2 = ProductLinks.insert(new_link)

		# use lock to write last Link, then close for the next processor.
		resp2_3 = await DB_PROCESS.query_withlock(
			create2_2, lock_id = lock_2, close_lock_after_query = True)
		
		logger.progress(f"Thread2 Found Product ID {resp2_2["lastrowid"]}")


	# THREAD 1:

	select1_1 = ProductLinks.select(
		where = (ProductLinks.row.upc == 5000295148154)
	)
	resp1_1 = await DB_PROCESS.query_withlock(select1_1, ProductLinks)
	lock_1: int = resp1_1["lock_id"]


	asyncio.create_task(thread2()) # SIMULATE CONCURRENT WRITER (thread2)

	await asyncio.sleep(1) # EXTRA DELAY SO thead2 STAGES FIRST.

	results: list[ProductLink] = resp1_1.get("fetchall") or []

	if (len(results) > 0): # FOUND!
		DB_PROCESS.close_lock(lock_1) # close lock as no other query will.
		pid = results[0].product.ref_value(Product).db_id.plain_value

		logger.progress(f"Thread1 Found Product ID {pid}")
		return pid

	new_product = Products.row.from_dict({
		"name": "Extra Mature Cheddar Cheese",
		"packsize_count": 1,
		"packsize_sizeeach": 550.0,
		"packsize_unit": "g"
	}, False)

	new_product.brand.ref_value(Brand).db_id.value = 1879 # 'Cathedral City'

	create1_1 = Products.insert(new_product)

	# again, lock not needed here as we are the only ones with control
	# over ProductLinks. PL control is required to be able to write
	# to Products, so nothing clashing can happen.
	resp1_2 = await DB_PROCESS.query(create1_1)

	new_link = ProductLinks.row.from_dict({
		"upc": 5000295148154,
		"cin": 6594606
	})

	new_link.product.ref_value(Product).db_id.value = resp1_2["lastrowid"]
	new_link.store.ref_value(Store).db_id.value = 2

	create1_2 = ProductLinks.insert(new_link)

	# use the lock to write new link, and close it.
	# this allows thread2 to begin.
	resp1_3 = await DB_PROCESS.query_withlock(
		create1_2, lock_id = lock_1, close_lock_after_query = True)
	
	logger.progress(f"Thread1 Found Product ID {resp1_2["lastrowid"]}")

	''' RELEVANT collection.log RESULTS
	06-02-26 15:19:27 - PROGRESS IN MainThread           :  Connected: True
	06-02-26 15:19:31 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 15:19:31 - INFO     IN DBThread             :  Completed #0 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 0 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:19:34 - INFO     IN DBThread             :  Skipping #1 due to lock. (SELECT from ProductLinks)
	06-02-26 15:19:34 - DEBUG    IN DBThread             :  INSERT INTO Products (BrandID, EntryCreatedDate, PName, PS_Count, PS_SizeEach, PS_Unit, DetailsVerified) VALUES (%s, %s, %s, %s, %s, %s, %s); < (1879, None, 'Extra Mature Cheddar Cheese', 1, 550.0, 'g', False) < []
	06-02-26 15:19:34 - INFO     IN DBThread             :  Completed #2 (INSERT 1x Product), 2 results returned. Success: True. Todo: 1
	06-02-26 15:19:37 - INFO     IN DBThread             :  Skipping #1 due to lock. (SELECT from ProductLinks)
	06-02-26 15:19:37 - DEBUG    IN DBThread             :  INSERT INTO ProductLinks (CIN, PID, StoreID, UPC) VALUES (%s, %s, %s, %s); < (6594606, 1200, 2, 5000295148154) < []
	06-02-26 15:19:37 - INFO     IN DBThread             :  Completed #3 (INSERT 1x ProductLink), 2 results returned. CLOSED LOCK 0. Success: True. Todo: 1
	06-02-26 15:19:37 - PROGRESS IN MainThread           :  Thread1 Found Product ID 1200
	06-02-26 15:19:40 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5057172404735] < []
	06-02-26 15:19:40 - INFO     IN DBThread             :  Completed #1 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 1 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:19:43 - DEBUG    IN DBThread             :  INSERT INTO Products (BrandID, EntryCreatedDate, PName, PS_Count, PS_SizeEach, PS_Unit, DetailsVerified) VALUES (%s, %s, %s, %s, %s, %s, %s); < (1880, None, 'British Mild Cheddar', 1, 400.0, 'g', False) < []
	06-02-26 15:19:43 - INFO     IN DBThread             :  Completed #4 (INSERT 1x Product), 2 results returned. Success: True. Todo: 0
	06-02-26 15:19:46 - DEBUG    IN DBThread             :  INSERT INTO ProductLinks (CIN, PID, StoreID, UPC) VALUES (%s, %s, %s, %s); < (6793870, 1201, 2, 5057172404735) < []
	06-02-26 15:19:46 - INFO     IN DBThread             :  Completed #5 (INSERT 1x ProductLink), 2 results returned. CLOSED LOCK 1. Success: True. Todo: 0
	06-02-26 15:19:46 - PROGRESS IN MainThread           :  Thread2 Found Product ID 1201
	06-02-26 15:20:16 - PROGRESS IN MainThread           :  disconnect

	# Correct! we can see lock was created by ProductLinks SELECT, which blocks Thread2's ProductLinks SELECT.
	# Thread1 continues normally until it found (created) Product ID 1200, and removes it's lock (0)
	# This allows Thread2's ProductLinks SELECT to run, and that processes normally.


	06-02-26 15:27:42 - PROGRESS IN MainThread           :  Connected: True
	06-02-26 15:27:46 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 15:27:46 - INFO     IN DBThread             :  Completed #0 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 0 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:27:47 - PROGRESS IN MainThread           :  Thread1 Found Product ID 1202
	06-02-26 15:27:49 - INFO     IN DBThread             :  Completed #0 URGENT ACTION (no SQL), 0 results returned. CLOSED LOCK 0. Success: True. Todo: 1
	06-02-26 15:27:52 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5057172404735] < []
	06-02-26 15:27:52 - INFO     IN DBThread             :  Completed #1 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 1 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:27:55 - DEBUG    IN DBThread             :  INSERT INTO Products (BrandID, EntryCreatedDate, PName, PS_Count, PS_SizeEach, PS_Unit, DetailsVerified) VALUES (%s, %s, %s, %s, %s, %s, %s); < (1880, None, 'British Mild Cheddar', 1, 400.0, 'g', False) < []
	06-02-26 15:27:55 - INFO     IN DBThread             :  Completed #2 (INSERT 1x Product), 2 results returned. Success: True. Todo: 0
	06-02-26 15:27:58 - DEBUG    IN DBThread             :  INSERT INTO ProductLinks (CIN, PID, StoreID, UPC) VALUES (%s, %s, %s, %s); < (6793870, 1203, 2, 5057172404735) < []
	06-02-26 15:27:58 - INFO     IN DBThread             :  Completed #3 (INSERT 1x ProductLink), 2 results returned. CLOSED LOCK 1. Success: True. Todo: 0
	06-02-26 15:27:58 - PROGRESS IN MainThread           :  Thread2 Found Product ID 1203
	06-02-26 15:28:28 - PROGRESS IN MainThread           :  disconnect

	# Correct! we can see lock was created by ProductLinks SELECT, almost immediately closed as
	# this returned the existing PID we wanted. Then Thread2 was allowed to commence, and processed normally.
	'''
	
	




async def example_3(DB_PROCESS: DBThread):
	# Example 3: Clashing flow, controlled by locks. Would cause
	# issues without them, this is the entire reason for implementing.

	async def thread2():
		select2_1 = ProductLinks.select(
			where = (ProductLinks.row.upc == 5000295148154) # SAME UPC
		)

		# **NOTICE** how UPC we're searching for in thread2 is the
		# same as in thread1. if we didn't have locks, this would cause
		# the following:

		#	1) select1_1
		# 	2) select2_2
		#	3) create1_1
		# 	4) create2_1 # 2 PRODUCT ROWS NOW CREATED FOR SAME UPC
		#	5) create1_2
		#	6) create2_2 # IntegrityError: DUPLICATE KEY violates UNIQUE(UPC)
		# this is a mess that's *impossible* to clean up.
		# we could try to delete create2_1 and use create1_1's PID, but
		# what if, before deleting create2_1, another (thread3) queries for
		# UPC and finds it? (this only could happen with multiple, see blue pen)

		# This SELECT query will yield until the entirety of thread1
		# has finished. Because of this, the process described above will
		# not occur. Instead, select2_1 will return a PID, preventing
		# the creation of any unwanted Links.
		resp2_1 = await DB_PROCESS.query_withlock(select2_1, ProductLinks)
		lock_2: int = resp2_1["lock_id"]

		results: list[ProductLink] = resp2_1.get("fetchall") or []

		if (len(results) > 0): # FOUND!
			DB_PROCESS.close_lock(lock_2) # close lock as no other query will.
			pid = results[0].product.ref_value(Product).db_id.plain_value

			logger.progress(f"Thread2 Found Product ID {pid}")
			return pid

		new_product = Products.row.from_dict({
			"name": "Extra Mature Cheddar Cheese",
			"packsize_count": 1,
			"packsize_sizeeach": 550.0,
			"packsize_unit": "g"
		}, False)
		
		new_product.brand.ref_value(Brand).db_id.value = 1879 # 'Cathedral City'

		create2_1 = Products.insert(new_product)

		resp2_2 = await DB_PROCESS.query(create2_1)

		new_link = ProductLinks.row.from_dict({
			"upc": 5000295148154,
			"cin": 6594606
		})
		
		new_link.product.ref_value(Product).db_id.value = resp2_2["lastrowid"]
		new_link.store.ref_value(Store).db_id.value = 2

		create2_2 = ProductLinks.insert(new_link)

		# use lock to write last Link, then close for the next processor.
		resp2_3 = await DB_PROCESS.query_withlock(
			create2_2, lock_id = lock_2, close_lock_after_query = True)
		
		logger.progress(f"Thread2 Found Product ID {resp2_2["lastrowid"]}")


	# THREAD 1:

	select1_1 = ProductLinks.select(
		where = (ProductLinks.row.upc == 5000295148154)
	)
	resp1_1 = await DB_PROCESS.query_withlock(select1_1, ProductLinks)
	lock_1: int = resp1_1["lock_id"]


	asyncio.create_task(thread2()) # SIMULATE CONCURRENT WRITER (thread2)

	await asyncio.sleep(1) # EXTRA DELAY SO thead2 STAGES FIRST.

	results: list[ProductLink] = resp1_1.get("fetchall") or []

	if (len(results) > 0): # FOUND!
		DB_PROCESS.close_lock(lock_1) # close lock as no other query will.
		pid = results[0].product.ref_value(Product).db_id.plain_value

		logger.progress(f"Thread1 Found Product ID {pid}")
		return pid

	new_product = Products.row.from_dict({
		"name": "Extra Mature Cheddar Cheese",
		"packsize_count": 1,
		"packsize_sizeeach": 550.0,
		"packsize_unit": "g"
	}, False)

	new_product.brand.ref_value(Brand).db_id.value = 1879 # 'Cathedral City'

	create1_1 = Products.insert(new_product)

	resp1_2 = await DB_PROCESS.query(create1_1)

	new_link = ProductLinks.row.from_dict({
		"upc": 5000295148154,
		"cin": 6594606
	})

	new_link.product.ref_value(Product).db_id.value = resp1_2["lastrowid"]
	new_link.store.ref_value(Store).db_id.value = 2

	create1_2 = ProductLinks.insert(new_link)

	# use the lock to write new link, and close it.
	# this allows thread2 to begin.
	resp1_3 = await DB_PROCESS.query_withlock(
		create1_2, lock_id = lock_1, close_lock_after_query = True)
	
	logger.progress(f"Thread1 Found Product ID {resp1_2["lastrowid"]}")


	''' RELEVANT  collection.log RESULTS
	06-02-26 15:33:49 - PROGRESS IN MainThread           :  Connected: True
	06-02-26 15:33:53 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 15:33:53 - INFO     IN DBThread             :  Completed #0 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 0 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:33:56 - INFO     IN DBThread             :  Skipping #1 due to lock. (SELECT from ProductLinks)
	06-02-26 15:33:56 - DEBUG    IN DBThread             :  INSERT INTO Products (BrandID, EntryCreatedDate, PName, PS_Count, PS_SizeEach, PS_Unit, DetailsVerified) VALUES (%s, %s, %s, %s, %s, %s, %s); < (1879, None, 'Extra Mature Cheddar Cheese', 1, 550.0, 'g', False) < []
	06-02-26 15:33:56 - INFO     IN DBThread             :  Completed #2 (INSERT 1x Product), 2 results returned. Success: True. Todo: 1
	06-02-26 15:33:59 - INFO     IN DBThread             :  Skipping #1 due to lock. (SELECT from ProductLinks)
	06-02-26 15:33:59 - DEBUG    IN DBThread             :  INSERT INTO ProductLinks (CIN, PID, StoreID, UPC) VALUES (%s, %s, %s, %s); < (6594606, 1204, 2, 5000295148154) < []
	06-02-26 15:33:59 - INFO     IN DBThread             :  Completed #3 (INSERT 1x ProductLink), 2 results returned. CLOSED LOCK 0. Success: True. Todo: 1
	06-02-26 15:33:59 - PROGRESS IN MainThread           :  Thread1 Found Product ID 1204
	06-02-26 15:34:02 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 15:34:02 - INFO     IN DBThread             :  Completed #1 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 1 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:34:02 - PROGRESS IN MainThread           :  Thread2 Found Product ID 1204
	06-02-26 15:34:05 - INFO     IN DBThread             :  Completed #0 URGENT ACTION (no SQL), 0 results returned. CLOSED LOCK 1. Success: True. Todo: 0
	06-02-26 15:34:35 - PROGRESS IN MainThread           :  disconnect
	
	# Correct! We see lock was created in thread1, which creates the new product, then releases the lock.
	# Thread2 then commences and the created product in thread1 is found. Congratulations, we have now
	# eliminated the risk of lone products caused by duplicate UPCs.

	06-02-26 15:37:47 - PROGRESS IN MainThread           :  Connected: True
	06-02-26 15:37:51 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 15:37:51 - INFO     IN DBThread             :  Completed #0 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 0 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:37:52 - PROGRESS IN MainThread           :  Thread1 Found Product ID 1204
	06-02-26 15:37:54 - INFO     IN DBThread             :  Completed #0 URGENT ACTION (no SQL), 0 results returned. CLOSED LOCK 0. Success: True. Todo: 1
	06-02-26 15:37:57 - DEBUG    IN DBThread             :  SELECT ProductLinks.CIN AS 'ProductLinks.CIN', ProductLinks.ID AS 'ProductLinks.ID', ProductLinks.PID AS 'ProductLinks.PID', ProductLinks.StoreID AS 'ProductLinks.StoreID', ProductLinks.UPC AS 'ProductLinks.UPC' FROM ProductLinks WHERE (ProductLinks.UPC=%s) LIMIT 1000; < [5000295148154] < []
	06-02-26 15:37:57 - INFO     IN DBThread             :  Completed #1 (SELECT from ProductLinks), 1 results returned. CREATED LOCK 1 ON ProductLinks. Success: True. Todo: 0
	06-02-26 15:37:57 - PROGRESS IN MainThread           :  Thread2 Found Product ID 1204
	06-02-26 15:38:00 - INFO     IN DBThread             :  Completed #1 URGENT ACTION (no SQL), 0 results returned. CLOSED LOCK 1. Success: True. Todo: 0
	06-02-26 15:38:22 - PROGRESS IN MainThread           :  disconnect

	# Correct! The product already existed, so was found by thread1, which still held back thread2 until it was done.
	'''




async def main(tunnel: sshtunnel.SSHTunnelForwarder):
	env["DB_PORT"] = tunnel.local_bind_port # type: ignore
	
	db = Database.from_env(env, logger)
	db.declare_tables(
		Products, ProductLinks, PriceEntries, Ratings, Images, Brands, Stores,
		Offers, Keywords, OfferHolders, Labels)
	
	succ = db.connect()
	logger.progress(f"Connected: {succ}")

	DB_PROCESS = DBThread(logger, db, asyncio.get_event_loop(), "state/queue.txt")
	DB_PROCESS.start()

	
	await example_3(DB_PROCESS)

	await asyncio.sleep(30)


	db.disconnect()
	logger.progress("disconnect")


ssh_port = env["SSH_PORT"]
ssh_host = env["SSH_HOST"]
ssh_user = env["SSH_USER"]
ssh_keyy = env["SSH_KEYY"]
db__host = env["DB_HOST"]
db__port = env["DB_PORT"]

assert (
	ssh_port and ssh_host and ssh_user and
	ssh_keyy and db__host and db__port )

ssh_port = int(ssh_port)
db__port = int(db__port)

with sshtunnel.SSHTunnelForwarder(
		ssh_address_or_host = (ssh_host, ssh_port),
		ssh_username = ssh_user,
		ssh_pkey = ssh_keyy,
		remote_bind_address = (db__host, db__port) ) as tunnel:

	assert tunnel
	logger.debug(f"SSH TUNNEL ACTIVE: {tunnel.is_active}")

	env["DB_PORT"] = tunnel.local_bind_port # type: ignore

	asyncio.run(main(tunnel)) # MUST DO THIS INSIDE "WITH" TO MAINTAIN TUNNEL
