from dbmanager2 import engine

class Book(engine.TableRow):
	db_id = engine.TableColumn("ID", "INT UNSIGNED", int, primary_key = True)
	name = engine.TableColumn("BookName", "MEDIUMTEXT", str, required = True)
	author = engine.TableColumn("AuthorID", "INT UNSIGNED", int, required = True)
	category = engine.TableColumn("Category", "MEDIUMTEXT", str)
 
class Author(engine.TableRow):
	db_id = engine.TableColumn("ID", "INT UNSIGNED", int, primary_key = True)
	name = engine.TableColumn("AuthorName", "MEDIUMTEXT", str, required = True)
 
Books = engine.Table("Books", Book)
Authors = engine.Table("Authors", Author)
 
Books.row.author.references = Authors.row.db_id
 
print(Books.select(
	where = Books.row.category == "Fiction",
	join_all = True,
	limit = 10))