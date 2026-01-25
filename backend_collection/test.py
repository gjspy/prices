from collectors.basecollector import AlgoliaCollector
from dotenv import dotenv_values
import asyncio
import logging
from dotenv import load_dotenv
from datetime import datetime
import sshtunnel
import os, sys

sys.path.insert(0, r"C:\Users\ABC\CThings\prices")

from dbmanager.engine import Database
from dbmanager.process import DBThread
import dbclasses as objs
from collectors.storagemanager import StorageManager

# TODO: CLEAN NAMES BEFORE PUTTING INTO DB. REMOVE PACKSIZE AND BRANDNAME FROM TITLE, ETC.

load_dotenv()

SSH_USER = os.getenv("SSH_USER")
SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = os.getenv("SSH_PORT")
SSH_KEY = os.getenv("SSH_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_SCHM = os.getenv("DB_SCHM")

assert (
	SSH_USER and SSH_HOST and SSH_PORT and SSH_KEY and DB_HOST
	and DB_PORT and DB_USER and DB_PASS and DB_SCHM)


logger = logging.getLogger("main-logger") # GETS OR CREATES
logger.setLevel(logging.DEBUG)

console = logging.StreamHandler()
logger.addHandler(console)


# TODO: categories !!!!!!!
# TODO: logging and error catching
# TODO: check todos
# TODO: look at more product cases, see how code responds, different offer types
# TODO: check stability
# TODO: PARTIAL DB OBJECTS
# TODO: typechecking errors around Product().name = "hi", how does this work btw?
# TODO fix joins
# TODO add print statements useful for debugging and leave them in (TESTING)
# TODO: update CFW
# TODO: add logger to collectors.
# TODO: another addmin action: "return id_ if (id_ is not None) else self._store_data[StoreNames.unknown]" Price STORE is UNKNOWn?
# TODO: igs to interrogate, where price is old. to define old: last price was over 1 week ago? dont try again?
# -> for website user search, use available on latest price. tell user last time price was grabbed.
"""
class Product(TableRow):
	product_id = tablecol..

Product.product = Product.product_id.joins ? or smth?

"""


CONFIG = dotenv_values(".config")


async def main(tunnel: sshtunnel.SSHTunnelForwarder):
	db = Database(
		DB_HOST, tunnel.local_bind_port, DB_SCHM, DB_USER, DB_PASS, logger # type: ignore
	)

	db.declare_table_row_models(
		objs.Product, objs.ProductLink, objs.PriceEntry, objs.Offer,
		objs.Rating, objs.Image
	)

	db.connect()
	print("connected:", db.is_connected)

	DB_PROCESS = DBThread(logger, db, asyncio.get_event_loop())
	DB_PROCESS.start()

	this_manager = StorageManager(DB_PROCESS, {
		"link": {
			"upc": 1010101
		}
	})

	await this_manager.query_product_exists()

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
	
	"""
	print(db.config)

	db.connect()

	print("connected:", db.is_connected)


	result = db.execute_payload(select)
	print(vars(result[-1]))
	print(vars(result[-1].most_recent_transaction))
	print(vars(result[-1].most_recent_transaction.user))
	print(result[-1].most_recent_transaction.user.is_partial())

	# select and objectify works now.
	# test everything one last time then complete, write this cleanly and start
	# actual work.
	
	db.disconnect()

	response = db.execute_payload(creation_payload)

	print(response)

	new_transaction = Transaction.from_dict({
		"user": response[0],
		"cost": 3.21
	})

	creation2 = Transactions.insert(new_transaction)
	print(creation2)
	
	response2 = db.execute_payload(creation2)
	print(response2)
	new_user.set_autoincrement_value("ID", response[0]) # TODO: automate this
	new_transaction.set_autoincrement_value("ID", response2[0])


	new_user.most_recent_transaction = response2[0]
	print(new_user.get_changes())

	update = Users.update(new_user)
	print(update)

	repsonse3 = db.execute_payload(update)
	print(repsonse3)

	db.disconnect()

	"""