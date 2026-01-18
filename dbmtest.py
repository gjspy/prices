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
#Brands.row.best_product.references = Products.row.new().db_id
#a = Brands.row
"""
Table.row.TableColumn.references = .. works because
id(TableRow.TableColumn) == id(TableRow().TableColumn)
thats the whole reason we rewrote, so use it to our advantage.


Table.row.new().TableColumn.references = .. does not work because
.new() creates new instance of TableRow and TableColumns, so ids are different.

TableRow.TableColumn.references = .. does not work because
instantiation of TableRow applies table, _row_instantiated, _row_template.
cannot use metaclass because we need to give Table to TableColumns, we don't know that there
and we need it to be flexible (SELF REFERENTIAL), so its easier to get every time.
"""

#Brand.name.value = "test" # errors, correct
#Brands.row.name.value = "test" # errors, correct

#Brands.row.new().name.value = "test" # no error, COrRECT
#Brands.row.name._value == None # True, CORRECT

class a:
	this = 1

print(a.this) # 1
a.this = 2
print(a.this) # 2
print(a().this) # 2

b = a()
a.this = 3
print(b.this) # 2

b.this = 4
print(a.this) # 3

#Brands2 = Brands.as_alias("brands2")
#Brands.row.parent.references = Brands2.row.db_id
#Brands.row.parent.references = Brands.row.db_id


Brands.row.best_product.references = Products.row.db_id # WORKS
print(Brands.select(join_all=True))