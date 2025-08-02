#from dbmanager.DBManager.engine import Database, Table, TableRow, TableColumn
#from dbmanager.DBManager.process import DBThread
from logging import Logger
from dotenv import load_dotenv

import os
load_dotenv()
print(os.getenv("SSH_USER"))



import dbmanager



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