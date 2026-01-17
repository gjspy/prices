from dbmanager2.engine import *
from copy import deepcopy




class Product(TableRow):
	db_id = TableColumn("PID", "INT", int)
	name = TableColumn("PName", "TINYTEXT", str, True)
	brand = TableColumn("BrandID", "INT", int, True)
	preferred_thumb = TableColumn("PreferredThumbID", "INT", int)
	packsize_count = TableColumn("PS_Count", "SMALLINT", int)
	packsize_sizeeach = TableColumn("PS_SizeEach", "FLOAT", float)
	packsize_unit = TableColumn("PS_Unit", "VARCHAR(2)", str)



class Brand(TableRow):
	db_id = TableColumn("ID", "INT", int, primary_key = True)
	name = TableColumn("BName", "TINYTEXT", str)
	parent = TableColumn("ParentID", "INT", int)
	best_product = TableColumn("BestProductID", "INT", int)



Brands = Table("Brands", Brand)
Products = Table("Products", Product)

#Brand.best_product.references = Products.row.db_id
#Brands.row.best_product.references = Products.row.db_id both do it
Brands.row.best_product.references = Products.row.db_id

"""
Table.row.TableColumn.references = .. works because
id(TableRow.TableColumn) == id(TableRow().TableColumn)
thats the whole reason we rewrote, so use it to our advantage.


Table.row.new().TableColumn.references = .. does not work because
.new() creates new instance of TableRow and TableColumns, so ids are different.

TableRow.TableColumn.references = .. does not work because
instantiation of TableRow applies table, _row_instantiated, _row_template.

"""

#Brand.name.value = "test" # errors, correct
#Brands.row.name.value = "test" # errors, correct

Brands.row.new().name.value = "test" # no error, COrRECT
Brands.row.name._value == None # True, CORRECT
print(Brands.select(join_all=True))