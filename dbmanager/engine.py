"""
# DBManager #
Python Package to connect to a MySQL database with ORM.

### Example Usage ###
>>> from dbmanager import engine
>>> 
>>> class Book(engine.TableRow):
>>> 	db_id = engine.TableColumn("ID", "INT UNSIGNED", int, primary_key = True)
>>> 	name = engine.TableColumn("BookName", "MEDIUMTEXT", str, required = True)
>>> 	author = engine.TableColumn("AuthorID", "INT UNSIGNED", int, required = True)
>>> 	category = engine.TableColumn("Category", "MEDIUMTEXT", str)
>>> 
>>> class Author(engine.TableRow):
>>> 	db_id = engine.TableColumn("ID", "INT UNSIGNED", int, primary_key = True)
>>> 	name = engine.TableColumn("AuthorName", "MEDIUMTEXT", str, required = True)
>>> 
>>> Books = engine.Table("Books", Book)
>>> Authors = engine.Table("Authors", Author)
>>> 
>>> Books.row.author.references = Authors.row.db_id
>>> 
>>> Books.select(
>>> 	where = Books.row.category == "Fiction",
>>> 	join_all = True,
>>> 	limit = 10)
"""
import mysql.connector
from mysql.connector import Error as MySQLError

from mysql.connector.abstracts import (
	MySQLConnectionAbstract, MySQLCursorAbstract)
from mysql.connector.types import RowType as MySQLRowType
from mysql.connector.pooling import PooledMySQLConnection

from datetime import datetime
from functools import wraps
from logging import Logger
from os import getenv


from dbmanager.types import (
	Generic, Type, T, Any, Optional, Literal, Union, overload, TypeVar, Self,
	Callable,
	DSS, DSA, QueryParams)
from dbmanager.misc import (
	Errors, ExecutionException, ASCENDING_SQL, DESCENDING_SQL, uid)

TableRowType = TypeVar("TableRowType", bound = "TableRow")
EH = TypeVar("EH", bound = Callable[..., Any])




FATAL_ERROR_CODES: list[int] = [2006, 2013, 2055]
MAX_IDLE_TIME: int = 30 # TICKS
SQL_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


# ERROR CATCHING FOR VARIOUS DB METHODS, TO SAVE REWRITING TRY/EXCEPT
# EVERY TIME.
def error_handling(
		self: "Database", e: Exception | MySQLError, rethrow: bool = False):
	"""
	HANDLES ERRORS FOR DB METHODS
	PREVENTS WRITING TRY/EXCEPT AROUND EVERY EXECUTION
	
	AUTOMATICALLY CLOSES CURSORS AND ROLLS BACK CONNECTIONS.
	"""
	is_fatal: bool = type(e) == MySQLError and e.errno in FATAL_ERROR_CODES
	fatal_str: str = "[FATAL] " if is_fatal else ""

	connection: MySQLConnectionAbstract | None = None

	try: connection = getattr(self, "connection")
	except: pass

	if (connection and connection.in_transaction):
		self.logger.exception(
			f"{fatal_str}EXCEPTION WITH DB WHILE TRANSACTING")
		connection.rollback()
		self.close_cursor()

	else: self.logger.exception(f"{fatal_str}EXCEPTION WITH DB")

	#if (is_fatal):
	#	self.disconnect()

	if (rethrow): raise ExecutionException(e, is_fatal)


def db_error_safe_catcher(func: EH) -> EH:
	"""
	Wrapper to catch exceptions raised by various DB methods.

	Handler automatically closes cursors, and rolls back connections.

	This method does not re-raise, just fails after logging.
	"""

	@wraps(func)
	def wrapper(self: "Database", *args: Any, **kwargs: Any) -> Any:

		try:
			return func(self, *args, **kwargs)

		except Exception as e: # CATCH ERROR CAUSED BY func, HANDLE IT NOW.
			error_handling(self, e)

	return wrapper # type: ignore[reportReturnType]


def db_error_catcher_rethrows(func: EH) -> EH:
	"""
	Wrapper to catch exceptions raised by various DB methods.

	Handler automatically closes cursors, and rolls back connections.

	This method re-raises the exception, for later functions to deal with.
	"""

	@wraps(func)
	def wrapper(self: "Database", *args: Any, **kwargs: Any) -> Any:

		try:
			return func(self, *args, **kwargs)

		except Exception as e: # CATCH ERROR CAUSED BY func, HANDLE IT NOW.
			error_handling(self, e, True)

	return wrapper # type: ignore[reportReturnType]






class Validator():
	def __init__(self, db_type: str | tuple[str, int], value: Any):
		if (type(db_type) == str):
			self.db_type = db_type.replace(" UNSIGNED", "")
			self.size = 0
			
		elif (type(db_type) == tuple):
			self.db_type = db_type[0]
			self.size = db_type[1]

		self.value = value
		self.unsigned = "UNSIGNED" in db_type
	

	def CHAR(self): return type(self.value) == str and len(self.value) == self.size
	def VARCHAR(self, size: int = 0):
		return type(self.value) == str and len(self.value) <= self.size or size

	def TINYTEXT(self): return self.VARCHAR(255) # 2 ** 8
	def TEXT(self): return self.VARCHAR(65_535) # 2 ** 16
	def MEDIUMTEXT(self): return self.VARCHAR(16_777_215) # 2**24
	def LONGTEXT(self): return self.VARCHAR(4_294_967_295) # 2**32

	def _NUMBER(self, signed_max_exc: int):
		if (not type(self.value) in [int, float]): return False

		if (self.unsigned): return self.value < (signed_max_exc * 2)
		else: return self.value >= -signed_max_exc and self.value < signed_max_exc
	
	def TINYINT(self): return self._NUMBER(128) # 2 ** 7
	def SMALLINT(self): return self._NUMBER(32_768) # 2 ** 15
	def MEDIUMINT(self): return self._NUMBER(8_388_608) # 2 ** 24
	def INT(self): return self._NUMBER(2_147_483_648) # 2 ** 31
	def BIGINT(self): return self._NUMBER(9223372036854775808) # 2 ** 63

	def FLOAT(self): return type(self.value) == float # I DON'T UNDERSTAND IT SO JUST SAY YES
	def BOOL(self): return type(self.value) == bool

	def TIMESTAMP(self): return type(self.value) == str # TODO: make match fmt

	TYPES_CHECKING = Literal[
		"CHAR", "VARCHAR", "TINYTEXT", "MEDIUMTEXT", "TEXT", "LONGTEXT",
		"TINYINT", "TINYINT UNSIGNED", "SMALLINT", "SMALLINT UNSIGNED",
		"MEDIUMINT", "MEDIUMINT UNSIGNED", "INT", "INT UNSIGNED",
		"BIGINT", "BIGINT UNSIGNED", "FLOAT", "FLOAT UNSIGNED", "BOOL",
		"TIMESTAMP"]
	
	def is_valid(self):
		try: return getattr(self, self.db_type)()
		except:
			print("DB TYPE", self.db_type, "NOT RECOGNISED")
			return None
	
	def make_valid(self, py_type: type[Any]):
		if (py_type == datetime):
			return datetime.strftime(self.value, SQL_DATETIME_FMT)
		
		try: return py_type(self.value)
		except: return None






class CMP():
	"""
	Class used to help define query statements.

	Internal, shouldn't usually be created manually outside of dbmanager
	"""

	def __init__(self, a: Any, b: Any, symbol: str):
		self.a = a
		self.b = b
		self.symbol = symbol
	
	def _convert_to_str(self, v: Union[Any, "TableColumn[Any]"]) -> str:
		if (isinstance(v, datetime)):
			v = f"{v.strftime(SQL_DATETIME_FMT)}"
		
		if (not isinstance(v, TableColumn) and not isinstance(v, CMP)):
			v = f"\'{v}\'" # MUST RUN FOR DATETIME TOO.
		
		if (not isinstance(v, str)): # int, str, float, TableColumn
			v = str(v) # type: ignore
		
		return v
	

	def __str__(self):
		a = self._convert_to_str(self.a)
		b = self._convert_to_str(self.b)

		
		return f"({a}{self.symbol}{b})"


	# BITWISE OPERATIONS BEING OVERWRITTEN!
	# DO THIS SO CAN WRITE Table1.uid == Table2.uid & Table1.name != "Jim"
	def __and__(self, value: object):
		return CMP(self, value, " AND ")

	def __or__(self, value: object):
		return CMP(self, value, " OR ")
	
	def __invert__(self):
		return NOT(self)

class METHOD(CMP):
	method = ""

	def __init__(self, value: Any):
		self.a = value
	
	def __str__(self):
		a = self._convert_to_str(self.a)

		return f"{self.method}({a})"

	def __eq__(self, value: object) -> CMP: # type: ignore[incompatibleMethodOverride]
		return CMP(self, value, "=")
	
	def __ne__(self, value: object) -> CMP: # type: ignore[incompatibleMethodOverride]
		return CMP(self, value, "<>")

class NOT(METHOD): method = "NOT"
class UPPER(METHOD): method = "UPPER"
class LOWER(METHOD): method = "LOWER"




class Join():
	"""
	Use this class to define a JOIN statement.
	
	This may be created manually, but also happens automatically when
	`join_all` is true in `Table.select()`
	"""

	def __init__(
			self, joining_table: "Table[Any]",
			condition: CMP | str, join_type: str = "LEFT"):
		"""
		Define a JOIN statement.

		Args
		--------
		joining_table: Table
			type object of the TableRow of the table
			you're joining into this statement.

		condition: CMP | str
			Query str to define how the joined table relates to this.
			Usually linking primary / foreign keys.

		join_type: str
			Optional, can be INNER, LEFT, RIGHT, CROSS.
			Default is LEFT
		"""

		self.join_type = join_type
		self.joining_table = joining_table
		self.condition = condition



	def __str__(self):
		join_type: str = self.join_type
		if (join_type): join_type += " "

		return f"{join_type}JOIN {self.joining_table.id_statement()} ON {self.condition}"








# USE _row_instantiated BCS OTHERWISE, IF SET .value, WOULD BE SAME FOR ALL
# INSTANCES AND CLASS.
# id(TableColumn.attribute) == id(TableColumn().attribute)!!!!!



# row_instantiated = False always, unless TableColumn accessed by Table.row.new().TableColumn

class TableColumn(Generic[T]):
	"""
	Class to describe a field/column of a database.

	TableColumn is never used uninstantiated.

	Three types of TableColumn:
	1) **Child of uninstantiated TableRow**
		- This is in the TableRow subclass definition
		- Never apply anything to this instance, as it only receives
		required information (such as parent Table) upon TableRow initialisation.
	2) **Child of instantiated TableRow, template**
		- This is accessed through Table.row
		- Apply references (joins) to this instance so they are replicated
		to future instances
		- Do not apply values, as these should be individual and would be
		copied to any future instances.
	3) **Child of instantiated TableRow, value holder**
		- This is accessed through Table.row.new()
		- Do not apply references as these would not be given to other
		Table.row.new() instances
		- Apply values, as these will be individual.
	
		
	You may not subclass this, as that will break its logic. (.duplicate())
	"""

	def __init__(
			self,
			db_field: str,
			db_type: Validator.TYPES_CHECKING | tuple[Validator.TYPES_CHECKING, int],
			py_type: type[T],
			required: bool = False,
			default_value: Optional[T] = None,
			primary_key: bool = False,
			reference: Optional["TableColumn[Any]"] = None,
			autoincrement: bool = False,
			_row_instantiated: bool = False,
			_row_template: bool = True,
			_table: "Table[Any]" = None, # type: ignore[reportArgumentType]
			_attr_name: Optional[str] = None):
		"""
		Define new TableColumn of TableRow.
		This should only be used in your initial TableRow subclass definition.

		Args
		----
		db_field: str
			Name of field in Database.
		
		db_type: Literal[...]
			MySQL string definition for the datatype of the field.

		py_type: type[Any]
			Python `type` object for the datatype of the field.
		
		required: bool = False
			Whether field is `NOT NULL`
		
		default_value: Optional[Any]
			Any value to automatically apply to TableColumn.value,
			where its type must match `py_type`.
		
		primary_key: bool = False
			Whether field is involved in the `PRIMARY KEY` of the TableRow.
		
		reference: Optional[TableColumn]
			Which TableColumn a field is the foreign key of.

			Usually more convenient to define using
			Table.row.TableColumn.references = X later.
		"""
		
		self._db_type = db_type
		self._db_field = db_field
		self._py_type = py_type
		self._required = required
		self._default_value = default_value
		self._is_pk = primary_key
		self._row_instantiated = _row_instantiated
		self._row_template = _row_template
		self._autoincrement = autoincrement

		self._value =  None
		if (default_value): self.value = default_value
		self._value_changed = False

		self._table = _table
		self._references = reference
		self._attr_name = _attr_name
	

	def _set_value(self, v: T, set_changed: bool = True):
		# TODO: VALIDATION
		self._value = v
		if (set_changed): self._value_changed = True


	@property
	def value(self):
		if (not self._row_instantiated):
			raise AttributeError(
				"TableColumn templates do not have values, "
				"only value holder instances do")
		
		return self._value
	
	@value.setter
	def value(self, v: T):
		# DO NOT APPLY TO CHILDREN OF UNINSTANTIATED TableRow, OR TEMPLATES.
		if ((not self._row_instantiated) or self._row_template):
			raise AttributeError(
				"Cannot set the value of TableColumn templates, "
				"must be value holder instance")
		
		validator = Validator(self.db_type, v)

		if (validator.is_valid() == False):
			new_v = validator.make_valid(self._py_type)

			if (not new_v):
				raise TypeError(f"TableColumn {self} has type {self.db_type} "
					f"{self._py_type}, which does not match "
					f"type {type(v)} of {v}")
		
		self._set_value(v)
	

	@property
	def references(self): return self._references
	
	@references.setter
	def references(self, other: "TableColumn[Any]"):
		"""
		Define field which this TableColumn is a foreign key of.
		Always define for TableColumn template instances,
		children of instantiated TableRows.

		(use Table.row.TableColumn.references = Table2.row.TableColumn).
		"""

		# ONLY APPLY REFERENCES TO TableColumn CHILDREN OF INSTANTIATED TableRow
		if (not (self.is_row_instantiated and other.is_row_instantiated)):
			raise AttributeError(
				"Reference (other) and self must be TableColumns from "
				"instantiated TableRows. You are working with your "
				"type[TableRow].TableColumn, but you must use your "
				"Table.row.TableColumn"
			)
		
		# ONLY APPLY REFERENCES TO TEMPLATES, REJECT IF IS VALUE HOLDER
		if (not (self.is_template and other.is_template)):
			raise AttributeError(
				"You may not define references from value holder instances "
				"of TableColumn. You are running your Table.row.new().TableColumn, "
				"but you may only define Table.row.TableColumn.references"
			)

		self._references = other
	

	# READ-ONLY FOR THE USER
	@property
	def is_primary_key(self): return self._is_pk

	@property
	def is_template(self): return self._row_template

	@property
	def is_row_instantiated(self): return self._row_instantiated

	@property
	def is_autoincrement(self): return self._autoincrement

	@property
	def value_changed(self): return self._value_changed

	@property
	def db_type(self): return self._db_type

	@property
	def table(self): return self._table

	@property
	def field(self):
		""" DB field name """
		return self._db_field
	
	@property
	def name(self):
		""" py attr name """
		return self._attr_name or ""

	@property
	def default(self):
		""" Returns default value of TableColumn. """
		return self._default_value

	def duplicate(self, table: "Table[Any]", attr: str):
		"""
		Creates new instance of TableColumn with all the same properties.
		Does not preserve `self.value`.
		"""

		return self.__class__(
			self._db_field, self._db_type, self._py_type, self._required, # type: ignore
			self._default_value, self._is_pk,
			self._references, self._is_pk, True, True, table, attr # KEEPS OLD TC REFERENCE HERE, TODO: BAD?
		)
	
	def commit(self):
		"""
		Set `self._value_changed` to False.
		You should usually run `TableRow.commit()` to commit all `TableColumn`s.
		"""

		self._value_changed = False





	def in_(self, objects: list[Any]) -> CMP:
		return CMP(self, objects, "IN")
	
	def like_(self, objects: list[Any]) -> CMP:
		return CMP(self, objects, "LIKE")

	def __eq__(self, value: object) -> CMP: # type: ignore[incompatibleMethodOverride]
		return CMP(self, value, "=")

	def __ne__(self, value: object) -> CMP: # type: ignore[incompatibleMethodOverride]
		return CMP(self, value, "<>")

	def __lt__(self, value: object) -> CMP:
		return CMP(self, value, "<")

	def __le__(self, value: object) -> CMP:
		return CMP(self, value, "<=")

	def __gt__(self, value: object) -> CMP:
		return CMP(self, value, ">")

	def __ge__(self, value: object) -> CMP:
		return CMP(self, value, ">=")
	
	@property
	def ascending(self) -> str:
		""" Returns ORDER_BY query for this column, ascending. """
		return str(self) + " " + ASCENDING_SQL

	@property
	def descending(self) -> str:
		""" Returns ORDER_BY query for this column, descending. """
		return str(self) + " " + DESCENDING_SQL

	def __str__(self) -> str:
		if (not self.table): # ROW NOT INSTANTIATED, WHY ARE YOU HERE?
			return self._db_field

		return f"{self.table.identifier}.{self._db_field}"





class TableRow():
	"""
	TableRow contains all TableColumns of a Table.
	Always access through `Table.row`.

	Create one through `Table.rows.new()`, with this instance
	you can assign new values to columns.
	"""

	def __init__(self, table: "Table[Any]"):
		self._table = table
		self._columns: list[str] = []
		self._db_fields: list[str] = []
		self._pkeys: list[str] = []
		self._ai: list[str] = []
		self._db_field_to_col: DSS = {}

		self._is_template: bool = True

		for k in dir(self):
			v = self.get_column(k)

			if (not isinstance(v, TableColumn)): continue
			vv = v.duplicate(table, k)

			setattr(self, k, vv)

			self._columns.append(k)
			self._db_fields.append(vv.field)
			if (vv.is_primary_key): self._pkeys.append(vv.field)
			if (vv.is_autoincrement): self._ai.append(vv.field)

			self._db_field_to_col[vv.field] = k


	# READ-ONLY FOR THE USER
	# USE METHODS, NOT SETTERS, TO DISTINGUISH FROM TableColumn ATTRS.
	def is_value_holder(self): return self._is_template
	def get_column_names(self): return self._columns
	def get_column(self, name: str):
		v: Optional[TableColumn[Any]] = getattr(self, name)

		if (not isinstance(v, TableColumn)): return None
		return v
	
	def get_columns(self):
		return list(filter(
			None, # RETURN ALL WHERE BOOL(v) is True
			(self.get_column(k) for k in self.get_column_names())
		))
	
	def get_fields(self): return self._db_fields


	def get_joins(self):
		joins: list[Join] = []

		for attr in self._columns:
			v = self.get_column(attr)
			assert v

			ref = v.references
			if (not ref): continue

			other_table = ref.table
			if (not other_table): continue # CONCERNING IF THIS HAPPENS

			if (id(self._table) == id(other_table)):
				other_table = other_table.as_alias(uid())
				ref = other_table.row.get_column(ref.name)
			
			joins.append(Join(other_table, v == ref))
		
		return joins



	def get_changes(self, include_defaults: bool = False):
		"""
		Returns `dict` of changes made to instances values,
		ready to be written in UPDATE or INSERT statement.

		Args
		----
		include_defaults: bool = False
			If the result of this method will be used for a table INSERT,
			use include_defaults = True to add default values, adding
			protection for required fields being omitted.
		"""
		changes: DSA = {}

		for attr in self._columns:
			column: Optional[TableColumn[Any]] = self.get_column(attr)
			if (not column): continue

			if (not column.value_changed):
				if (include_defaults):
					changes[attr] = column.value or column.default

				continue

			changes[attr] = column.value
		
		return changes
	
	def to_storable(self) -> QueryParams:
		changes = self.get_changes(True)
		ai = self.get_autoincrement_keys()
		storable: list[Any] = []

		for field in self._db_fields:
			if (field in ai): continue

			col_name = self.get_col_from_field(field)
			storable.append(changes[col_name])
		
		return tuple(storable)





	
	def commit(self):
		"""
		Commit all changes of TableRows.
		This sets `TableColumn.value_changed` to False.
		"""

		for attr in self._columns:
			col: TableColumn[Any] = getattr(self, attr)

			col.commit()
	

	def get_autoincrement_keys(self):
		"""
		Returns list of `db_field` where
		its `TableColumn.is_autoincrement` is True.
		"""
		return self._ai
	
	def get_primarykey_fields(self):
		"""
		Returns list of `db_field` where
		its `TableColumn.is_primary_key` is True
		"""
		return self._pkeys
	
	def get_col_from_field(self, field: str):
		""" Returns column name from db_field. """
		return self._db_field_to_col[field]
		



	# INSTANCE CREATORS

	def from_dict(self, data: DSA, from_db: bool = False):
		"""
		Creates new `TableRow` object with value holder `TableColumns`
		Also sets values of each `TableColumn` based on `data`

		Args
		--------
		data: dict[str, Any]
			Data to apply to `TableRow`
		
		from_db: bool = False
			Declare where `data` originated.
			True = from `mysql-connector`, `data` keys are db columns.
			False = user-generated, `data` keys are py attrs.
			References will not be queried if `from_db` is False. Only
			partials will be created.
		"""

		new: Self = self.new()
		column_types_applied_to: list[bool] = []

		for attr in new._columns:
			col = new.get_column(attr)
			if (not col): continue

			ref = col.references

			if (ref):
				other_row: Self = ref.table.row
				created = other_row.from_dict(data, from_db)
				
				col.value = created
				continue

			key = col.field if from_db else col.name
			value = data.get(key)
			if (not value): continue

			col.value = value
			del data[key] # PREVENT CIRCULAR RECURSION
			column_types_applied_to.append(col.is_primary_key)
		
		# column_types.. = list[is primary key? t/f]
		#if (all(column_types_applied_to)): # ALL PKS
			# TODO: set partial if needed.
		
		new.commit() # SAVE CHANGES

		return new





	def new(self):
		"""
		Returns new `TableRow` object where
		each `TableColumn` may hold a value.

		This method is required to prevent issues
		with shared references in Python.
		"""

		new = self.__class__(self._table)
		new._is_template = False

		for attr in new._columns:
			column: TableColumn[Any] = getattr(new, attr)

			new_column = column._create_value_holder(self._table) # type: ignore
			setattr(new, attr, new_column)
		
		return new






class Table(Generic[TableRowType]):
	"""
	This class encapsulates all query logic (`SELECT`, `UPDATE`, `INSERT`)

	Always use an instance of this class, and use Table.row
	to access the TableRow object.

	Use Table.as_alias() to clone the table and use with an alias. Happens
	automatically if a TableRow self-references, but can also be useful manually.
	"""
	def __init__(
			self, db_name: str, row_model: type[TableRowType], _alias: str = ""):
		self._db_name = db_name
		self._alias = _alias

		self._row_model = row_model
		self._row = row_model(self)
	

	# READ-ONLY FOR THE USER
	@property
	def row(self) -> TableRowType: return self._row

	@property
	def name(self): return self._db_name

	@property
	def alias(self): return self._alias



	def select(
			self,
			columns: list[TableColumn[Any]] = [],
			distinct: bool = False,
			where: CMP | None = None,
			join_all: bool = False,
			join_on: list[Join] = [],
			limit: int = 1000,
			order_by: list[TableColumn[Any] | str] = []) -> DSA:
		"""
		### Build `SELECT` STATEMENT. ###

		Args
		--------
		columns: list[TableColumn]
			List of columns to select, default All.
		
		distinct: bool = False
			Whether selection should include `DISTINCT`	
		
		where: CMP
			Comparison object used to build the statement.

		join_all: bool
			Whether to join all tables as pre-defined. (True)
			Else, only joins relationships defined with `join_on`

		join_on: list[Join]
			Defining any joins required for the query.
			If `join_all` is True, this should be empty.

		limit: int
			Maximum rows to return. Default = 1000

		order_by: list[str | TableColumn]
			Which columns to order by. May be `TableColumn`,
			`TableColumn.ascending`, `TableColumn.descending` or any manually
			created string.

		Example:
		--------
		>>> select(
		>>> 	(Table1.value1 == Table1.value2) & (Table1.value3 == datetime(2025, 8, 1)),
		>>> 	order_by = [Table1.value1, Table1.value2.ascending])
		"""

		if (join_all): join_on.extend(self.row.get_joins())

		tables_involved: list[Table[Any]] = [
			self, *( v.joining_table for v in join_on )]

		all_columns: list[TableColumn[Any]] = columns
		if (not columns):
			all_columns = []
			
			for v in tables_involved:
				r: TableRow = v.row
				cols: list[TableColumn[Any]] = [getattr(r, col) for col in r.get_column_names()]

				all_columns.extend(cols)
		
		order_by_strs: list[str] = [ str(v) for v in order_by]
		

		# BUILD str STATEMENT:
		what_to_select = ", ".join( f"{v} AS \'{v}\'" for v in all_columns )
		distinct_statement = " DISTINCT" if distinct else ""

		sql: str = f"SELECT{distinct_statement} {what_to_select} FROM {self}" # BASE

		for join in join_on: sql += f" {join}" # ADD JOINS

		if (where): sql += f" WHERE {where}" # ADD CONDITION

		if (order_by_strs):
			order_by_statement = ", ".join(order_by_strs)

			sql += f" ORDER BY {order_by_statement}" # ADD ORDER BY

		if (limit): sql += f" LIMIT {limit}" # ADD LIMIT

		return {
			"query": sql + ";",
			"expect_response": "fetchall",
			"objectify_from_table": self.name,
			"debug": ("select", "from " + self.name)
		}


	def insert(self, *rows: TableRow) -> DSA:
		""" ### Build `INSERT` STATEMENT. ### """
		ai_fields = self.row.get_autoincrement_keys()
		fields = ", ".join(f for f in self.row.get_fields() if (not f in ai_fields))

		# "%s" FOR EVERY KEY, THEN [: -2] TO REMOVE TRAILING ", "
		n_values = len(self.row.get_fields()) - len(ai_fields)
		placeholder_str: str = ("%s, " * n_values)[: -2]
		values = [ v.to_storable() for v in rows ]

		sql: str = f"INSERT INTO {self.name} ({fields}) VALUES ({placeholder_str});"

		payload: DSA = {
			"query": sql,
			"expect_response": "lastrowid",
			"debug": ("insert", [ type(v).__name__ for v in rows ])
		}

		if (len(values) == 1): payload["params"] = values[0]
		else: payload["many_params"] = values

		for row in rows:
			row.commit() # CLEAR changes.

		return payload


	def update(self, *rows: TableRow) -> DSA:
		"""
		### Build `UPDATE` STATEMENT. ###
		Only used for updating specific rows based on PKs.
		Blanket UPDATE statements should be created otherwise.
		# """

		sqls: list[str] = []
		valueses: list[QueryParams] = []

		for row in rows:
			changes = row.get_changes()

			py_fields = changes.keys()
			db_fields_changed = list(row.get_column(v).field for v in py_fields) # type: ignore[reportOptionalMemberAccess]

			set_str = ", ".join( f"{k} = %s" for k in db_fields_changed )
			values = tuple(changes.values())

			where_str = ""

			db_fields = row.get_fields()

			pk: str
			for pk in row.get_primarykey_fields():
				col = row.get_column(row.get_col_from_field(pk))
				if (not col): continue

				where_str += f" {col}={col.value}"

			sqls.append(f"UPDATE {self.name} SET {set_str} WHERE{where_str};")
			valueses.append(values)
			row.commit() # CLEAR changes.

		return {
			"queries": sqls,
			"paramses": valueses,
			"debug": ("update", [ type(v).__name__ for v in rows ])
		}














	# NAMING FUNCTIONS

	def as_alias(self, alias: str):
		"""
		Create new instance of Table with alias.

		Happens automatically when a TableRow self-references, but may also
		be useful manually.
		"""

		if (self._alias):
			raise AttributeError("This table has already been aliased.")
		
		cloned = self.__class__.__new__(self.__class__)
		cloned.__init__(self._db_name, self._row_model, alias)
		
		return cloned

	
	def __str__(self):
		""" Always returns `str` db_name. """
		return self._db_name
	
	def id_statement(self):
		"""
		Statement for a FROM or JOIN to identify a table.
		
		Either: "TableName" OR "TableName AS Alias"
		"""
		return f"{self._db_name} AS {self._alias}" if self._alias else str(self)
	
	@property
	def identifier(self) -> str:
		"""
		`str` identifier of the table. alias if exists, else name.
		"""
		return self._alias if self._alias else str(self)







class Database():
	""" # Database Engine # """

	def __init__(
			self, host: str, port: int, schema: str, user: str, passwd: str,
			logger: Logger, init_command: str = "", autocommit: bool = False,
			time_zone_description: str = ""):
		"""
		Initiates the database engine.

		Args
		--------
		host, port, schema, user, passwd: str, int, str, str, str
			Credentials for connection.

		logger: Logger
			Logger to write to.

		init_command: str
			SQL query to run immediately after successful connection

		autocommit: bool
			Whether to automatically commit operations after each
			SQL statement

		time_zone_description: str
			Define the session's time_zone at connection time.
			Example: "+00:00", "UTC"
		"""

		self._config: dict[str, str | int | bool]
		self._connection: MySQLConnectionAbstract | PooledMySQLConnection | None
		self._active_cursor: MySQLCursorAbstract | None
		self._logger: Logger
		self._time_idle: int
		self._is_connected: bool
		self._tables: dict[str, Table[Any]]

		# CONFIG = SETUP OF ACTIVE DB / CONNECTION
		# SET ONCE HERE, NEVER CHANGE.
		self._config = {
			"host": host,
			"port": port,
			"database": schema,
			"user": user,
			"password": passwd,
			"init_command": init_command,
			"autocommit": autocommit,
			"time_zone": time_zone_description
		}


		self._connection = None
		self._active_cursor = None
		self._logger = logger
		self._time_idle = 0
		self._is_connected = False
		self._tables = {}

		# DON'T HAVE SETTERS FOR _active_cursor BECAUSE I WANT ITS CREATION
		# TO BE EXPLICIT WITH ._init_cursor(), PLUS WANT THIS CURSOR TO ONLY
		# BE USED FOR execute() HERE.



	@property # NO SETTER, READ-ONLY.
	def config(self): return self._config


	@property
	def logger(self): return self._logger

	@logger.setter
	def set_logger(self, new: Logger): self._logger = new


	@property # NO SETTER, KEEP WRITE ACCESS PRIVATE
	def connection(self):
		# DON'T TRY TO CONNECT HERE.
		# SHOULD BE EXPLICIT TASK.

		return self._connection


	def increment_time_idle(self): self._time_idle += 1

	def reset_time_idle(self): self._time_idle = 0

	def declare_tables(self, *tables: Table[Any]):
		for table in tables:
			self._tables[table.name] = table



	def test_connection(self):
		assert self._connection, "Connection must be initialised first."

		is_connected: bool = self._connection.is_connected() # PINGS DB

		return is_connected



	@property
	def is_connected(self):
		"""
		Get recent information about connection status.
		Method does not ping DB every time. Only pings if
		no successful interaction sooner than MAX_IDLE_TIME.
		"""
		if (not self._connection): return False
		if (not self._is_connected): return False

		# _IS_CONNECTED = TRUE, CAN WE TRUST THAT?
		# IF TOO OLD, CHECK AGAIN
		if (self._time_idle > MAX_IDLE_TIME):
			success = self.test_connection()
			self._is_connected = success

			if (success): self.reset_time_idle()

		return self._is_connected



	@db_error_safe_catcher
	def connect(self) -> bool:
		"""
		Connect to the database, returning bool of success.
		If already connected, disconnects before reconnecting.
		"""

		if (self._connection): self.disconnect()

		self._connection = mysql.connector.connect(**self._config)

		self.reset_time_idle() # WAS SUCCESSFUL!
		return True # CONFIRM SUCCESS



	@db_error_safe_catcher
	def disconnect(self):
		""" Disconnect from the database """
		if (not self._connection):
			self._is_connected = False
			return

		self._connection.close()
		self._is_connected = False # ONLY RUNS IF .close() DOES NOT ERROR



	def _init_cursor(self, buffered: bool = True):
		assert self.connection, "Connection does not exist."

		if (self._active_cursor): self.close_cursor()

		self._active_cursor = self.connection.cursor(
			#dictionary = True,
			buffered = buffered)

		# CAN'T USE DICT MODE, DOESN'T ALLOW FOR
		# DUPLICATE COLUMN NAMES, EG Table1.ID AND Table2.ID,
		# DICT KEY PRODUCED = "ID", ONLY PROVIDES Table2.ID



	def close_cursor(self):
		if (not self._active_cursor): return

		self._active_cursor.close()
		self._active_cursor = None



	def _execute_one(
			self, query: str, params: QueryParams = (),
			many_params: list[QueryParams] = []):
		"""
		Execute a single SQL Statement.

		MANY = ONE QUERY, USED FOR MULTIPLE VALUES.
		NOT MULTIPLE STATEMENTS.
		"""

		assert self._active_cursor, "There is no active cursor"

		if (many_params): self._active_cursor.executemany(query, many_params)
		else: self._active_cursor.execute(query, params)



	@db_error_catcher_rethrows
	def execute(
			self, query: str, params: QueryParams = (), 
			many_params: list[QueryParams] = [], expect_response: str = "",
			buffered: bool = True, objectify_from_table: str = "",
			**kwargs: Any):
		"""
		Execute SQL Statement

		Cursor/Session is encapsulated here. If you want to run multiple
		queries before committing, use execute_many()

		`**kwargs` is included, so this function will ignore extra
		params in your payload.

		Args
		--------
		query: str or list[str]
			SQL statement(s) to run.

		params: tuple | None
			Parameters to insert into SQL statement

		expect_response: str
			Optional, provide if a response is expected, using:\n
			`"fetchall"`: returns results of cursor.fetchall() [helpful for SELECT]\n
			`"lastrowid"`: returns cursor.lastrowid [helpful for INSERT]

		buffered: bool
			Whether result of a query is read from server immediately,
			by execute() [True], or is read when fetchall() [False] is run.

		objectify_from_table: bool
			Whether to use the database's `table_row_models` to return
			the response as objects [True], or just return the `dict` as
			provided from cursor.fetchall()
		"""

		assert self.connection, "The database is not connected"
		if (kwargs):
			ignored: list[Any] = list(kwargs.keys())
			self.logger.debug(f"Ignoring {ignored} kwargs..")

		result: list[Any] = []

		self._init_cursor(buffered)
		assert self._active_cursor, "Cursor unsuccessfully initialised"

		# THERE WILL ONLY EVER BE ONE OF params, many_params
		self._execute_one(query, params, many_params)

		match expect_response:
			case "fetchall": result = self._active_cursor.fetchall()
			case "lastrowid": result = [ self._active_cursor.lastrowid, ]
			case _: pass

		if (objectify_from_table):
			column_names: list[str] = [
				col[0] for col in (self._active_cursor.description or []) ]

			result = self.objectify_results(
				result, objectify_from_table, column_names)

		self.connection.commit()
		self.close_cursor()

		# WAS SUCCESSFUL! DECLARE SO!
		self.reset_time_idle()

		return result



	@db_error_catcher_rethrows
	def execute_multiple(
			self, queries: list[str],
			paramses: list[QueryParams | list[QueryParams]] = [],
			expect_response: bool = False, buffered: bool = True,
			objectify_from_table: str = "", **kwargs: Any):
		"""
		Execute multiple SQL statements.
		If you want to execute one statement for multiple params,
		call execute() with a list[tuple] params.

		Call execute_multiple() for multiple SQL statements

		`**kwargs` is included, so this function will ignore extra
		params in your payload.
		"""

		assert len(queries) == len(paramses)
		assert self.connection, "The database is not connected"
		if (kwargs):
			ignored: list[Any] = list(kwargs.keys())
			self.logger.debug(f"Ignoring {ignored} kwargs..")

		result: list[Any]

		self._init_cursor(buffered)
		assert self._active_cursor, "Cursor unsuccessfully initialised"

		i: int
		for i in range(len(queries)):
			query: str = queries[i]
			these_params = paramses[i]

			if (type(these_params) == tuple):
				self._execute_one(query, these_params)
				continue

			self._execute_one(
				query, many_params = these_params) # type: ignore


		result = self._active_cursor.fetchall() if (expect_response) else []
		if (objectify_from_table):
			column_names: list[str] = [
				col[0] for col in (self._active_cursor.description or []) ]

			result = self.objectify_results(
				result, objectify_from_table, column_names)

		self.connection.commit()
		self.close_cursor()

		# WAS SUCCESSFUL! DECLARE SO!
		self.reset_time_idle()
		return result

	def execute_payload(self, payload: DSA) -> list[Any]:
		""" Execute SQL Statement from `dict` payload. """

		routine: Callable[..., Any]

		if (payload.get("queries")):
			routine = self.execute_multiple
		else:
			routine = self.execute

		return routine(**payload)





	def objectify_result(
			self, ms_result: MySQLRowType, table_name: str,
			fetched_column_names: list[str]) -> TableRow:
		""" ### Convert one dictionary result to the object of its table. """
		table: Optional[Table[Any]] = self._tables.get(table_name)

		assert table, f"objectify: no model for table_name {table_name}"
		assert len(ms_result) == len(fetched_column_names), \
			f"length of results not equal to amount of column names"

		result = dict(
			(fetched_column_names[i], ms_result[i])
			for i in range(len(fetched_column_names)) )

		return table.row.from_dict(result, True)



	def objectify_results(
			self, results: list[MySQLRowType],
			table_name: str, column_names: list[str]) -> list[TableRow]:
		""" ### Objectify a list of results easily. """

		return [
			self.objectify_result(v, table_name, column_names)
			for v in results ]

	@classmethod
	def from_env(
			cls, env: DSA, logger: Logger, init_command: str = "",
			autocommit: bool = False, time_zone_description: str = ""):
		host: str = env["DB_HOST"]
		port: int = env["DB_PORT"]
		user: str = env["DB_USER"]
		pswd: str = env["DB_PASS"]
		schm: str = env["DB_SCHM"]

		try: port = int(port)
		except: ValueError("Port must be convertable to int.")

		return cls(
			host = host, port = port, user = user, passwd = pswd, schema = schm,
			logger = logger, init_command = init_command, autocommit = autocommit,
			time_zone_description = time_zone_description)
