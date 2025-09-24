#from dbmanager.DBManager.engine import Database, Table, TableRow, TableColumn
#from dbmanager.DBManager.process import DBThread
import logging
from dotenv import load_dotenv
from datetime import datetime
import sshtunnel
import os, sys

sys.path.insert(0, r"C:\Users\ABC\CThings\prices")

from dbmanager.engine import TableRow, TableColumn, Database, Table
from dbmanager.misc import flatten

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

class Transaction(TableRow):
	table_name = "Transactions"

	db_id = TableColumn("ID", int, autoincrement = True)
	user = TableColumn("UID", int, True)
	cost = TableColumn("Cost", float, True)

	pkeys = ["ID"]


class User(TableRow):
	table_name = "Test"

	db_id = TableColumn("ID", int, autoincrement = True)
	name = TableColumn("UName", str, True)
	age = TableColumn("Age", int, True)
	balance = TableColumn("BankBalance", float)
	created = TableColumn("AccountCreated", datetime)
	most_recent_transaction = TableColumn("MostRecentTransaction", int)

	pkeys = ["ID"]


User.most_recent_transaction.joins = Transaction.db_id
Transaction.user.joins = User.db_id


Users = Table("Test", User)
Transactions = Table("Transactions", Transaction)


new_user: User = User.from_dict({
	"name": "Bob",
	"age": 12,
	"balance": 1.1,
	"created": datetime(2025, 7, 1)
})


creation_payload = Users.insert(new_user)

print(creation_payload)

select = Users.select(
	((User.db_id == 1) & (User.name == "Bob")) | (User.created >= datetime(2025, 6, 2)),
	True, limit = 5000,
	order_by = [User.age, User.created.ascending]
) # TODO: TEST THIS SELECT, THEN CLEAN IT? THEN DONE?

print(select)


with sshtunnel.SSHTunnelForwarder(
		(SSH_HOST, int(SSH_PORT)), ssh_username = SSH_USER, ssh_pkey = SSH_KEY,
		remote_bind_address = (DB_HOST, int(DB_PORT))) as tunnel:
	print("tunnel active: ", tunnel and tunnel.is_active)
	
	db = Database(
		DB_HOST, tunnel.local_bind_port, DB_SCHM, DB_USER, DB_PASS, logger
	)

	db.declare_table_row_model(User)
	db.declare_table_row_model(Transaction)

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







#from sshtunnel import SSHTunnelForwarder

# OBJECT DEFINITIONS
"""class Product(TableRow):
	table_name = "PRODUCTS"

	db_id = TableColumn("ID", str)
	pname = TableColumn("NAME", str)
	weight = TableColumn("WEIGHT", float)

	pkeys = ["ID"]

print(type(Product()).__name__)

Products = Table("PRODUCTS", Product)

logger = Logger("new")

engine = Database(
	"127.0.0.1", 3306, "maindb", "dbnonadmin", "asdkasgnsg",
	logger
)

thread = DBThread(logger, engine)


















"""