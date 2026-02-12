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
import mysql.connector.errorcode as errorcodes
#import mysql.connector.errors as errors

from mysql.connector.abstracts import (
	MySQLConnectionAbstract, MySQLCursorAbstract)
from mysql.connector.types import RowType as MySQLRowType
from mysql.connector.pooling import PooledMySQLConnection

from datetime import datetime, timezone, date
from asyncio import Future
from functools import wraps
from logging import Logger
from copy import deepcopy


from dbmanager.types import (
	Generic, Any, Optional, Literal, TypeVar, Self, Callable,

	DSS, DSA, QueryParams )

from dbmanager.misc import ASCENDING_SQL, DESCENDING_SQL, uid, async_executor

# USE TypeVar TO GIVE NICE TYPING FOR SUBCLASSES.
TableRowType = TypeVar("TableRowType", bound = "TableRow") 
T = TypeVar("T")
EH = TypeVar("EH", bound = Callable[..., Any])

MAX_IDLE_TIME: int = 30 # TICKS
SQL_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


# ERROR CATCHING FOR VARIOUS DB METHODS, TO SAVE REWRITING TRY/EXCEPT
# EVERY TIME.
def error_handling(
		self: "Database", e: Exception | MySQLError, rethrow: bool = False,
		debug_config: Optional[DSA] = None):
	"""
	HANDLES ERRORS FOR DB METHODS
	PREVENTS WRITING TRY/EXCEPT AROUND EVERY EXECUTION

	AUTOMATICALLY CLOSES CURSORS AND ROLLS BACK CONNECTIONS.
	"""
	is_msql = isinstance(e, MySQLError)
	is_fatal = is_msql and (2000 <= e.errno < 3000)

	quiet_codes: list[int] = []
	if (debug_config): quiet_codes = debug_config.get("quiet_codes") or []
	is_quiet = is_msql and (e.errno in quiet_codes)

	fatal_str: str = (
		"[FATAL] EXCEPTION WITH DB WHILE TRANSACTING" if is_fatal 
		else "QUIET DB EXCEPTION" if is_quiet else "EXCEPTION WITH DB" )

	connection: Optional[MySQLConnectionAbstract] = None

	try: connection = getattr(self, "connection")
	except: pass

	msg = f"{fatal_str} - {e}"

	if (is_fatal): self.logger.critical(msg)
	elif (is_quiet): self.logger.info(msg)
	else: self.logger.error(msg)

	if (is_msql and connection and connection.in_transaction):
		connection.rollback()
		self.close_cursor()

	#if (is_fatal):
	#	self.disconnect()

	if (rethrow): raise e


def db_error_safe_catcher(func: EH) -> Callable[[Any], EH]:
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
			error_handling(self, e, False, kwargs.get("debug_config"))

	return wrapper


def db_error_catcher_rethrows(func: EH) -> Callable[[Any], EH]:
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
			error_handling(self, e, True, kwargs.get("debug_config"))

	return wrapper




JOIN_TYPE = Literal["INNER", "LEFT", "RIGHT", "CROSS"]

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

	def TIMESTAMP(self): return type(self.value) == str
	def DATE(self): return type(self.value) == str
	def DATETIME(self): return type(self.value) == str

	TYPES_CHECKING = Literal[
		"CHAR", "VARCHAR", "TINYTEXT", "MEDIUMTEXT", "TEXT", "LONGTEXT",
		"TINYINT", "TINYINT UNSIGNED", "SMALLINT", "SMALLINT UNSIGNED",
		"MEDIUMINT", "MEDIUMINT UNSIGNED", "INT", "INT UNSIGNED",
		"BIGINT", "BIGINT UNSIGNED", "FLOAT", "FLOAT UNSIGNED", "BOOL",
		"TIMESTAMP", "DATE", "DATETIME", "_ANY"]

	def is_valid(self):
		try: return getattr(self, self.db_type)()
		except:
			print("DB TYPE", self.db_type, "NOT RECOGNISED")
			return None

	def make_valid(self, py_type: type[Any]):
		if (py_type == datetime):
			if (
					isinstance(self.value, datetime) or
					isinstance(self.value, date) ):

				return self.value.strftime(SQL_DATETIME_FMT)

			else:
				return datetime.fromtimestamp(
					float(self.value), timezone.utc).strftime(SQL_DATETIME_FMT)

		try: return py_type(self.value)
		except: return None




class Join():
	"""
	Use this class to define a JOIN statement.

	This may be created manually, but also happens automatically when
	`join_all` is true in `Table.select()`
	"""

	def __init__(
			self, joining_table: "Table[Any]",
			condition: "CMP | str", join_type: JOIN_TYPE = "LEFT"):
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
	

	@property
	def joined_identifier(self):
		return self.joining_table.id_statement()

	def __str__(self):
		join_type: str = self.join_type
		if (join_type): join_type += " "

		return f"{join_type}JOIN {self.joined_identifier} ON {self.condition}"
	
	def safe(self):
		if (isinstance(self.condition, str)): return (str(self), tuple())

		join_type: str = self.join_type
		if (join_type): join_type += " "

		a = self.condition.safe()

		return (
			f"{join_type}JOIN {self.joined_identifier} ON {a[0]}",
			a[1] )


class JoinInlineTable(Join):
	def __init__(
			self,
			inline_payload: DSA,
			aliased_table: "Table[Any]",
			condition: "CMP | str",
			join_type: JOIN_TYPE = "LEFT"):

		self.join_type = join_type
		self.condition = condition

		self.table = aliased_table

		self._query = inline_payload["query"].replace(";", "")
		self._values = inline_payload["params"]
	
	@property
	def joined_identifier(self):
		return f"({self._query}) {self.table.alias}"

	def safe(self):
		q, values = super().safe()

		return (q, (*self._values, *values))


class ComparisonMethods():
	
	
	def in_(self, objects: list[Any]) -> "CMP":
		return IN(self, objects, " IN ")

	def like_(self, value: str) -> "CMP":
		return CMP(self, value, " LIKE ")

	def __eq__(self, value: object) -> "CMP": # type: ignore
		return CMP(self, value, "=")

	def __ne__(self, value: object) -> "CMP": # type: ignore
		return CMP(self, value, "<>")

	def __lt__(self, value: object) -> "CMP":
		return CMP(self, value, "<")

	def __le__(self, value: object) -> "CMP":
		return CMP(self, value, "<=")

	def __gt__(self, value: object) -> "CMP":
		return CMP(self, value, ">")

	def __ge__(self, value: object) -> "CMP":
		return CMP(self, value, ">=")


	# BITWISE OPERATIONS BEING OVERWRITTEN!
	# DO THIS SO CAN WRITE (Table1.uid == Table2.uid) & (Table1.name != "Jim")
	def __and__(self, value: object):
		return CMP(self, value, " AND ")

	def __or__(self, value: object):
		return CMP(self, value, " OR ")

	def __invert__(self):
		return NOT(self)
	
	def __add__(self, value: Any):
		return CMP(self, value, " + ")

	def __sub__(self, value: Any):
		return CMP(self, value, " - ")
	

	def __ordered_stmt(self, stmt: str) -> str:
		print(self, type(self), isinstance(self, ColumnType))
		if (isinstance(self, ColumnType)): return f"{self.select_name} {stmt}"
		if (isinstance(self, CMP)): return f"{self.safe()[0]} {stmt}"
		return f"{self} {stmt}"


	@property
	def ascending(self) -> str:
		""" Returns ORDER_BY query for this column, ascending. """
		return self.__ordered_stmt(ASCENDING_SQL)


	@property
	def descending(self) -> str:
		""" Returns ORDER_BY query for this column, descending. """
		return self.__ordered_stmt(DESCENDING_SQL)

	
	@property
	def select_name(self) -> str:
		return str(self)





class CMP(ComparisonMethods):
	"""
	Class used to help define query statements.

	Internal, shouldn't usually be created manually outside of dbmanager
	"""

	_placeholder = "%s"

	def __init__(self, a: Any, b: Any, symbol: str):
		self.a = a
		self.b = b
		self.symbol = symbol


	def _convert_to_str(
			self, v: Any, only_str: bool = True
			) -> str | tuple[str, tuple[Any, ...]]:

		# WANT TO 'QUOTE' IT, NO RETURN.
		if (isinstance(v, datetime) and only_str):
			v = v.strftime(SQL_DATETIME_FMT) 

		if (isinstance(v, ColumnType)):
			if (only_str): return str(v)
			else: return (v.select_name, v.params)

		if (isinstance(v, CMP)):
			if (only_str): return str(v)
			return v.safe()

		return f"'{v}'" if (only_str) else (self._placeholder, tuple())


	def _fmt_str(self, a: Any, b: Any) -> str:
		return f"({a}{self.symbol}{b})"


	def __str__(self):
		a = self._convert_to_str(self.a)
		b = self._convert_to_str(self.b)

		return self._fmt_str(a, b)


	def safe(self) -> tuple[str, tuple[Any, ...]]:
		a = self._convert_to_str(self.a, False)
		b = self._convert_to_str(self.b, False)

		values: list[Any] = []
		values.extend(a[1])
		if (a[0] == self._placeholder): values.append(self.a)
		
		values.extend(b[1])
		if (b[0] == self._placeholder): values.append(self.b)

		return (self._fmt_str(a[0], b[0]), tuple(values))
	
	def as_column(self, name: str):
		"""
		Create DerivedColumn from METHOD or CMP subclass.

		Args
		--------
		name: str
			Name to `SELECT [...] AS ''`. Must be SQL and Python compliant,
			this will be the name of the `TableRow` attribute to access its
			results. (attr is lowercased.)
		
		"""
		return DerivedColumn(self, name)


class IN(CMP):
	def safe(self):
		assert isinstance(self.b, list), "IN params must be list"
		self.b: list[Any]

		ph = ((self._placeholder + ", ") * len(self.b))[:-2]
		return (f"({self.a}{self.symbol}({ph}))", tuple(self.b))


class MATCH(CMP):
	def __init__(self, col: "TableColumn[Any]", against: str):
		self.a = col
		self.b = against
		self.symbol = ""
	
	def _fmt_str(self, a: Any, b: Any) -> str:
		return f"MATCH({a}) AGAINST ({b})"


class METHOD(CMP):
	method = ""

	def __init__(self, value: Any):
		self.a = value

	def __str__(self):
		a = self._convert_to_str(self.a)

		return f"{self.method}({a})"
	
	def safe(self):
		a = self._convert_to_str(self.a, False)

		values: list[Any] = []
		values.extend(a[1])
		if (a[0] == self._placeholder): values.append(self.a)

		return (f"{self.method}({a[0]})", tuple(values))


class NOT(METHOD): method = "NOT"
class UPPER(METHOD): method = "UPPER"
class LOWER(METHOD): method = "LOWER"
class MAX(METHOD): method = "MAX"
class MIN(METHOD): method = "MIN"














class ColumnType():
	"""
	This class purely for typing, to check if value is any typ of column.
	"""

	@property
	def select_name(self) -> str: return ''

	@property
	def params(self) -> tuple[Any, ...]: return tuple()



class DerivedColumn(ComparisonMethods, ColumnType):
	def __init__(self, method: CMP | METHOD, name: str):
		self._str, self._values = method.safe()
		self._name = name
	

	@property
	def select_name(self) -> str:
		return self._name
	
	@property
	def params(self):
		return self._values
	
	def __str__(self) -> str:
		return self._str
	

	




# USE _row_instantiated BCS OTHERWISE, IF SET .value, WOULD BE SAME FOR ALL
# INSTANCES AND CLASS.
# id(TableColumn.attribute) == id(TableColumn().attribute)!!!!!



# row_instantiated = False always, unless TableColumn accessed by Table.row.new().TableColumn

class TableColumn(ComparisonMethods, ColumnType, Generic[T]):
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
			autoincrement: bool = False,
			_reference: Optional["TableColumn[Any]"] = None,
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
		self._references = _reference
		self._attr_name = _attr_name


	def _set_value(self, v: Optional[T | "TableRow"], set_changed: bool = True):
		self._value = v
		if (set_changed): self._value_changed = True


	@property
	def value(self):
		if (not self._row_instantiated):
			raise AttributeError(
				"TableColumn templates do not have values, "
				"only value holder instances do")

		return self._value
	

	@property
	def plain_value(self) -> Optional[T]:
		"""
		This attribute returns self.value as usual. Only exists to help with
		typing when you're certain the `TableColumn` has no reference.
		"""

		v = self.value
		
		if (isinstance(v, TableRow)):
			raise TypeError(
				f"Use {self.table.name}.{self.name}.ref_value to get a "
				"reference, not .plain_value")

		return v


	def ref_value(self, as_: type[TableRowType]) -> TableRowType:
		"""
		This attribute returns self.value as usual. Only exists to help with
		typing when you're certain the `TableColumn` has a reference.

		(HATE having this. I don't know what else to do.)

		Args
		--------
		as_: type[TableRow]
			Type of TableRow to be returned. I'd love pylance to be able to
			infer this but manually works I guess...
		"""

		v = self.value
		
		if (not isinstance(v, as_)):
			raise TypeError(
				f"Use {self.table.name}.{self.name}.plain_value to get a "
				"value, not .ref_value")

		return v

	@value.setter
	def value(self, v: Optional[T | "TableRow"]):
		# DO NOT APPLY TO CHILDREN OF UNINSTANTIATED TableRow, OR TEMPLATES.
		if ((not self._row_instantiated) or self._row_template):
			raise AttributeError(
				"Cannot set the value of TableColumn templates, "
				"must be value holder instance")
		
		ref = self.references

		if (ref):
			if (isinstance(v, TableRow)): self._set_value(v)
			else:
				this = f"{self.table.name}.{self.name}"
				raise TypeError(
				f"{self} references {ref}, so you cannot set {this}.value, "
				f"you must use {this}.value.{ref.name}.value even if partial")
			
			return
		
		if (v is None):
			v = self.default

			if (v is None and self._required): raise TypeError(
				f"TableColumn {self} is required.")
			
			self._set_value(v)
			return

		validator = Validator(self.db_type, v)

		if (validator.is_valid() == False):
			new_v = validator.make_valid(self._py_type)

			if (new_v is None):
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
		# BECAUSE DATA LIKE TC.table IS ADDED AS ROW IS INSTANTIATED.
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
		
		#if (id(self._table) == id(other)):
		if (self._table.name == other.table.name):
			other_table = other.table.as_alias(uid())
			other = other_table.row.get_column(other.name)
		

		self._references = other
	
	@property
	def join(self):
		ref = self.references
		if (not ref): raise TypeError("No reference.")

		return Join(ref.table, self == ref)


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
			self._db_field, self._db_type, self._py_type, self._required, # type: ignore[reportArgumentType]
			self._default_value, self._is_pk,
			self._autoincrement, self._references, True, True, table, attr
		)

	def create_value_holder(self, table: "Table[Any]", attr: str):
		"""
		Creates new instance of TableColumn with all the same properties
		Does not preserve `self.value`.

		This method used to create a new TableColumn instance which can
		hold a value. Only used internally, you should only ever use
		`Table.row.new()` to access TableColumns.
		"""

		return self.__class__(
			self._db_field, self._db_type, self._py_type, self._required, # type: ignore[reportArgumentType]
			self._default_value, self._is_pk,
			self._autoincrement, self._references, True, False, table, attr
		)


	def commit(self):
		"""
		Set `self._value_changed` to False.
		You should usually run `TableRow.commit()` to commit all `TableColumn`s.
		"""

		self._value_changed = False
	
	@property
	def select_name(self):
		return f"{self.table.rigid_identifier}.{self._db_field}"


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

	def __init__(
			self, table: "Table[Any]", _is_template: bool = True,
			_old_cols: Optional[list[TableColumn[Any]]] = None,
			_is_derived: bool = False):
		self._table = table
		self._columns: list[str] = []
		self._db_fields: list[str] = []
		self._pkeys: list[str] = []
		self._ai: list[str] = []
		self._db_field_to_col: DSS = {}

		self._is_template: bool = _is_template # False FROM Table.row.new()
		self._partial: bool = False

		if (_is_derived): return

		# old_cols PRESENT IN Table.row.new(), TO PRESERVE REFERENCES.
		if (_old_cols):
			for v in _old_cols:
				k = v.name
				self.__init_one_tc(k, v, _is_template)

		else:
			for k in dir(self):
				v = self.get_column(k)

				if (not isinstance(v, TableColumn)): continue
				self.__init_one_tc(k, v, _is_template)
			
	

	def __init_one_tc(self, attr: str, v: TableColumn[Any], _is_template: bool):
		vv = (
			v.duplicate(self._table, attr) if _is_template 
			else v.create_value_holder(self._table, attr))
		
		if (vv.references and not _is_template):
			vv.value = vv.references.table.row.new()
		
		setattr(self, attr, vv)

		self._columns.append(attr)
		self._db_fields.append(vv.field)
		if (vv.is_primary_key): self._pkeys.append(vv.field)
		if (vv.is_autoincrement): self._ai.append(vv.field)

		self._db_field_to_col[vv.field] = attr
	

	def is_partial(self): return self._partial
	def set_partial(self, v: bool): self._partial = v

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
			if (not other_table): continue

			joins.append(Join(other_table, v == ref))

		return joins
	
	def get_pkey_where_statement(self) -> CMP:
		where_str: CMP = None # type: ignore

		for pk in self.get_primarykey_fields():
			col = self.get_column(self.get_col_from_field(pk))
			if (not col): continue

			if (where_str): where_str = where_str & (col == col.value)
			else: where_str = (col == col.value)
		
		return where_str



	def get_changes(self, include_defaults: bool = False):
		"""
		Returns `dict` of changes made to instances values,
		ready to be written in UPDATE or INSERT statement.

		Args
		----
		include_defaults: bool = False
			If the result of this method will be used for a table INSERT,
			use include_defaults = True to add default values, **and
			any other existing values, which haven't changed**.
			Provides protection for required fields being omitted.
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

	def to_storable(self, for_insert: bool = True) -> QueryParams:
		"""
		Returns tuple of VALUES representing the TableRow.

		Args
		--------
		for_insert: bool = True
		If True, excludes autoincrement fields but includes defaults and
		unchanged values.
		If False, includes all fields.
		"""
		changes = self.get_changes(True)
		ai = self.get_autoincrement_keys()
		storable: list[Any] = []

		for field in self._db_fields:
			if (field in ai and for_insert): continue

			col_name = self.get_col_from_field(field)
			this_col = self.get_column(col_name)
			value = changes.get(col_name)

			if (this_col and isinstance(value, TableRow)):
				value = value.get_column(this_col.references.name).value # type: ignore

			storable.append(value)

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

	def get_primarykey_value(self):
		v = list(
			self.get_column(self.get_col_from_field(v))
			for v in self.get_primarykey_fields())
		l = len(v)

		if   (l == 0): return None
		elif (l == 1 and v[0]): return v[0].value
		else: return v


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
		data = deepcopy(data)

		for attr in new._columns:
			col = new.get_column(attr)
			if (not col): continue

			ref = col.references
			key = str(col) if from_db else col.name
			value = data.get(key)

			if (ref):
				other_row: Self = ref.table.row
				created = other_row.from_dict(data, from_db)

				if (created.get_primarykey_value() is None):
					other_col = created.get_column(ref.name)
					other_col.value = value # type: ignore
					created.set_partial(True)

				col.value = created
				if (value is not None): del data[key] # PREVENT INF RECURSION
				continue

			if (value is None): continue

			col.value = value
			del data[key] # PREVENT INF RECURSION

		new.commit() # SAVE CHANGES
		return new





	def new(self):
		"""
		Returns new `TableRow` object where
		each `TableColumn` may hold a value.

		This method is required to prevent issues
		with shared references in Python.
		"""

		new = self.__class__(self._table, False, self.get_columns())
		new.commit()

		return new
	

	@classmethod
	def collect_derived_columns(cls, derived_columns: list[str], data: DSA):
		row = cls(None, True, _is_derived = True) # type: ignore
		# MAKE row A TEMPLATE, SO USER CAN'T SET VALUES.

		for name in derived_columns:
			attr_name = name.lower()
			col = TableColumn(
				name, "_ANY", str, _attr_name = attr_name,
				_row_instantiated = True, _row_template = True)

			col._set_value(data.get(name), False) # type: ignore

			setattr(row, attr_name, col)

			row._columns.append(attr_name)
			row._db_fields.append(name) 
			row._db_field_to_col[name] = attr_name


		return row
		







class Table(Generic[TableRowType]):
	"""
	This class encapsulates all query logic (`SELECT`, `UPDATE`, `INSERT`)

	Always use an instance of this class, and use Table.row
	to access the TableRow object.

	Use Table.as_alias() to clone the table and use with an alias. Happens
	automatically if a TableRow self-references, but can also be useful manually.
	"""
	def __init__(
			self, db_name: str, row_model: type[TableRowType], _alias: str = "",
			_partial_alias: bool = False):
		self._db_name = db_name
		self._alias = _alias
		self._partial_alias = _partial_alias

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
			columns: Optional[list[ColumnType]] = None,
			distinct: bool = False,
			where: Optional[CMP] = None,
			join_all: bool = False,
			join_on: Optional[list[Join]] = None,
			limit: Optional[int] = 1000,
			limit_offset: Optional[int] = 0,
			page: Optional[int] = 0,
			order_by: Optional[list[ColumnType | str | CMP]] = None,
			group_by: Optional[list[ColumnType | str | CMP]] = None,
			objectify_results: bool = True,
			is_inline: bool = False) -> DSA:
		"""
		### Build `SELECT` STATEMENT. ###

		Args
		--------
		columns: list[TableColumn | DerivedColumn]
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
		
		limit_offset: int
			Optional Number of items to offset LIMIT by. Provide this OR page.
		
		page: int
			Optional page number, will be used to calculate `limit_offset` based
			on your `limit` provided. Page 0 is first (no offset)

		order_by: list[str | Column]
			Which columns to order by. May be `TableColumn`,
			`TableColumn.ascending`, `TableColumn.descending` or any manually
			created string.
		
		group_by: list[str | Column]
			Same as order_by.

		Example:
		--------
		>>> select(
		>>> 	(Table1.value1 == Table1.value2) & (Table1.value3 == datetime(2025, 8, 1)),
		>>> 	order_by = [Table1.value1, Table1.value2.ascending])
		"""

		# SETTING DEFAULT VALUES TO PARAMS AS [] OR {} MAINTAINS REF,
		# SO NEXT Table.select() WOULD INCLUDE OLD DATA. (ONLY EVALS ONCE)
		if (not columns): columns = []
		if (not join_on): join_on = []
		if (not order_by): order_by = []

		if (join_all): join_on.extend(self.row.get_joins())

		tables_involved: list[Table[Any]] = [
			self, *( v.joining_table for v in join_on if (not isinstance(v, JoinInlineTable)))]

		if (not columns):
			for v in tables_involved:
				columns.extend(v.row.get_columns())


		values: list[Any] = []
		derived: list[str] = []

		# BUILD str STATEMENT:
		what_to_select = ""

		for c in columns:
			is_tc = isinstance(c, TableColumn)
	
			if (is_inline):
				if (is_tc): what_to_select += f"{c} AS \'{c.field}\', "
				else: what_to_select +=f"{c} AS \'{c.select_name}\', "
			else: what_to_select += f"{c} AS \'{c.select_name}\', "

			if (is_tc): continue

			values.extend(c.params)
			derived.append(c.select_name)

		distinct_statement = " DISTINCT" if distinct else ""

		# BASE
		sql: str = f"SELECT{distinct_statement} {what_to_select[:-2]} FROM {self}" 

		for join in join_on:
			safe = join.safe()

			sql += f" {safe[0]}" # ADD JOINS
			values.extend(safe[1])

		if (where):
			safe = where.safe()

			sql += f" WHERE {safe[0]}" # ADD CONDITION
			values.extend(safe[1])
		
		if (group_by):
			group_by_statement = ", ".join(str(v) for v in group_by)

			sql += f" GROUP BY {group_by_statement}" # ADD GROUP BY

		if (order_by):
			order_by_statement = ", ".join(str(v) for v in order_by)

			sql += f" ORDER BY {order_by_statement}" # ADD ORDER BY

		if (limit): sql += f" LIMIT {limit}" # ADD LIMIT
		if (page):
			assert limit, "You must provide page size (limit)"
			limit_offset = limit * page
		if (limit_offset): sql += f" OFFSET {limit_offset}"

		query: DSA = {
			"query": sql + ";",
			"params": values,
			"expect_response": ["fetchall"],
			"debug": ("SELECT", "from " + self.name),
			"derived_columns": derived,
			"tables_involved": tables_involved
		}

		if (objectify_results): query["objectify_from_table"] = self
		return query


	def insert(
			self, *rows: TableRow,
			on_duplicate_key_query: Optional[DSA] = None,
			on_duplicate_key_update: bool = False,
			quiet_on_duplicate_entry: bool = False,
			on_duplicate_key_return_existing_id: bool = False) -> DSA:

		"""
		### Build `INSERT` STATEMENT. ###

		Args
		--------
		on_duplicate_key_query: dict[str, Any]
			Optional, query payload generated by any `Table.*` method,
			which will run if a UNIQUE or PRIMARY KEY constraint fails.
			This is not another db call, it is appended to the original
			`INSERT` query, through `ON DUPLICATE KEY ...`. Only applicable
			query is `UPDATE`.

		on_duplicate_key_update: bool = False
			Optional, allows for `ON DUPLICATE KEY UPDATE` statement but
			query str is generated here, instead of your own `Table.update()`
			call. Generated based on the `TableRow` changes.

		quiet_on_duplicate_entry: bool = False
			Optional, whether `ON DUPLICATE KEY` Exception should be quiet
			when logged. (INFO instead of ERROR.)

		on_duplicate_key_return_existing_id: bool = False
			Optional, whether you want the `AUTOINCREMENT ID` of the existing
			row clashing with the one you're trying to insert.
			This works by adding
			`ON DUPLICATE KEY UPDATE [PKEY_FIELD]=LAST_INSERT_ID([PKEY_FIELD])`
			
			Does not modify any values in existing entry. You must only specify
			one of this, or on_duplicate_key_update.
		"""

		ai_fields = self.row.get_autoincrement_keys()
		fields = ", ".join(f for f in self.row.get_fields() if (not f in ai_fields))

		# "%s" FOR EVERY KEY, THEN [: -2] TO REMOVE TRAILING ", "
		n_values = len(self.row.get_fields()) - len(ai_fields)
		placeholder_str: str = ("%s, " * n_values)[: -2]
		values = [ v.to_storable() for v in rows ]

		if ((not on_duplicate_key_query) and on_duplicate_key_update):
			on_duplicate_key_query = self.update(*rows, for_odk = True)

		if (on_duplicate_key_query):
			# ADD VALUES TO SUB INTO ODK STATEMENT
			# TO EVERY STORABLE tuple, INCASE OF many_params

			odk_params = on_duplicate_key_query.get("params")
			if (odk_params): values = [ (*v, *odk_params) for v in values ]
			else:
				values = [
					(*v, *on_duplicate_key_query["paramses"][i])
					for i,v in enumerate(values) ]
				on_duplicate_key_query["query"] = on_duplicate_key_query["queries"][0]

		odk = (
			f" ON DUPLICATE KEY {on_duplicate_key_query["query"]}"
			if on_duplicate_key_query else "" )
		
		if (on_duplicate_key_return_existing_id):
			if (odk): raise ValueError(
				"You may only specify one on_duplicate_key action. "
				"(not including quiet)")
			
			ai = ai_fields[0] # ONLY EVER ONE IS ALLOWED PER TABLE.
			odk = f" ON DUPLICATE KEY UPDATE {ai}=LAST_INSERT_ID({ai})"

		sql: str = (f"INSERT INTO {self.name} ({fields}) "
		f"VALUES ({placeholder_str}){odk};")

		payload: DSA = {
			"query": sql,
			"expect_response": ["lastrowid", "rowsaffected"],
			"debug": ("INSERT", [ type(v).__name__ for v in rows ]),
			"tables_involved": [self]
		}

		if (len(values) == 1): payload["params"] = values[0]
		else: payload["many_params"] = values

		if (quiet_on_duplicate_entry):
			payload["debug_config"] = {
				"quiet_codes": [ errorcodes.ER_DUP_ENTRY ]
			}

		for row in rows:
			row.commit() # CLEAR changes.

		return payload
	

	def update_blanket(
			self, set_values: list[tuple[TableColumn[T], T]],
			where: Optional[CMP] = None, for_odk: bool = False):
		"""
		### Build `UPDATE` STATEMENT. ###
		Use this to update MULTIPLE rows based on a `WHERE` statement.

		Args
		--------
		where: CMP
			Statement to select which rows to update.
		
		set_values: list[tuple[TableColumn[T], T]]
			List of k,v tuple pairs to apply to db rows,
			where k is the TableColumn and v is the value to set.
		
		for_odk: bool = False
			Whether statement will be used with `ON DUPLICATE KEY` in an
			INSERT query.
		"""

		set_str = ", ".join( f"{k[0]} = %s" for k in set_values )

		q = (
			f"UPDATE {set_str}"	if for_odk
			else f"UPDATE {self.name} SET {set_str};" )
		
		if (where and not for_odk): q += f" WHERE {where}"

		return {
			"query": q,
			"params": list( k[1] for k in set_values ),
			"debug": ("UPDATE", [ self.name ]),
			"tables_involved": [self]
		}
	
	def delete(
			self, rows: Optional[list[TableRow]] = None, 
			where: Optional[CMP] = None, allow_del_all: bool = False):
		"""
		### Build `DELETE` STATEMENT. ###
		Use this to update MULTIPLE rows based on a `WHERE` statement.

		Args
		--------
		rows: TableRow
			Rows to delete (using PKey)

		where: CMP
			Statement to select which rows to update.
		
		allow_del_all: bool = False
			Whether to allow DELETE without WHERE clause.
		"""

		if (rows):
			for row in rows:
				this_where = row.get_pkey_where_statement()

				if (where): where = where & this_where
				else: where = this_where
		
		where_stmt = str(where)
		if (not (where_stmt or allow_del_all)): raise ValueError(
			"No valid WHERE statement for DELETE")
		
		if (where_stmt): where_stmt = " WHERE " + where_stmt

		return {
			"query": f"DELETE FROM {self.name}{where_stmt}",
			"debug": ("DELETE", [ self.name ]),
			"tables_involved": [self]
		}


	def update(self, *rows: TableRow, for_odk: bool = False) -> DSA:
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

			where = row.get_pkey_where_statement()

			sqls.append(
				f"UPDATE {set_str}" if for_odk else
				f"UPDATE {self.name} SET {set_str} WHERE {where};")
			valueses.append(values)
			row.commit() # CLEAR changes.

		return {
			"queries": sqls,
			"paramses": valueses,
			"debug": ("UPDATE", [ type(v).__name__ for v in rows ]),
			"tables_involved": [self]
		}














	# NAMING FUNCTIONS

	def as_alias(self, alias: str, partial_alias: bool = False):
		"""
		Create new instance of Table with alias.

		Happens automatically when a TableRow self-references, but may also
		be useful manually.

		Partial alias is for creating SELECT.
			- True: Table.COL AS 'Alias.COL'
			- False: Alias.COL AS 'Alias.COL'

		"""

		if (self._alias):
			raise AttributeError("This table has already been aliased.")

		cloned = self.__class__.__new__(self.__class__)
		cloned.__init__(self._db_name, self._row_model, alias, partial_alias)

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
		`str` identifier of the table.
		alias if exists (AND NOT PARTIAL ALIAS), else name.
		"""
		return self._alias if (self._alias and not self._partial_alias) else str(self)
	
	@property
	def rigid_identifier(self) -> str:
		"""
		`str` identifier of the table. alias if exists (ALWAYS), else name.
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
		self._connection: Optional[MySQLConnectionAbstract | PooledMySQLConnection]
		self._active_cursor: Optional[MySQLCursorAbstract]
		self._logger: Logger
		self._time_idle: int
		self._is_connected: bool

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
		self.logger.critical("METHOD DEPRECATED, DOES NOTHING!")



	def test_connection(self):
		assert self._connection, "Connection must be initialised first."
		self._logger.debug("TESTING CONNECTION")

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

		try: self._active_cursor.close()
		except ReferenceError:
			pass # SOMETIMES "weakly-referenced object no longer exists",
			# ALREADY CLOSED BY PACKAGE.
		self._active_cursor = None



	def _execute_one(
			self, query: str, params: Optional[QueryParams] = None,
			many_params: Optional[list[QueryParams]] = None):
		"""
		Execute a single SQL Statement.

		MANY = ONE QUERY, USED FOR MULTIPLE VALUES.
		NOT MULTIPLE STATEMENTS.
		"""
		if (not params): params = ()
		if (not many_params): many_params = []

		assert self._active_cursor, "There is no active cursor"
		self.logger.debug(f"{query} < {params} < {many_params}")

		self.logger.add_to_stats("DBQUERY") # type: ignore

		if (many_params): self._active_cursor.executemany(query, many_params)
		else: self._active_cursor.execute(query, params)



	@db_error_catcher_rethrows
	def execute(
			self,
			query: str,
			params: Optional[QueryParams] = None,
			many_params: Optional[list[QueryParams]] = None,
			expect_response: Optional[list[str]] = None,
			buffered: bool = True,
			objectify_from_table: Optional[Table[Any]] = None,
			derived_columns: Optional[list[str]] = None,
			**kwargs: Any) -> DSA:
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

		params: Optional[tuple]
			Parameters to insert into SQL statement

		expect_response: list[str]
			Optional, provide if a response is expected, using:

			`"fetchall"`: returns results of cursor.fetchall() [helpful for SELECT]

			`"rowsaffected"`: returns cursor.rowcount [helpful for INSERT]

				- rowsaffected 1 = inserted your row. (if you provide exactly one)
				- rowsaffected 2 = returned existing_id (through LAST_INSERT_ID)

			`"lastrowid"`: returns cursor.lastrowid [helpful for INSERT]

		buffered: bool
			Whether result of a query is read from server immediately,
			by execute() [True], or is read when fetchall() [False] is run.

		objectify_from_table: bool
			Whether to use the database's `table_row_models` to return
			the response as objects [True], or just return the `dict` as
			provided from cursor.fetchall().
		
		Returns
		--------
		`dict` where each key is an `expect_response` keyword, eg `fetchall`.
		`fetchall` = list[TableRow] if `objectify_results`.

		`list[{"tablename": TableRow, "derived": TableRow}]`
		if `objectify_results` and derived columns are involved.

		`list[dict]` if not `objectify_results`.
		"""
		if (not params): params = ()
		if (not many_params): many_params = []
		if (not expect_response): expect_response = []
		if (not derived_columns): derived_columns = []


		assert self.connection, "The database is not connected"
		if (kwargs):
			ignored = set(kwargs.keys()) - {
				'debug', 'debug_config', 'tables_involved'}
			if (ignored): self.logger.debug(f"Ignoring {ignored} kwargs..")

		self._init_cursor(buffered)
		assert self._active_cursor, "Cursor unsuccessfully initialised"

		# THERE WILL ONLY EVER BE ONE OF params, many_params
		self._execute_one(query, params, many_params)

		result: dict[str, Optional[Any]] = {}

		for wanted in expect_response:
			got = None
			if (wanted == "fetchall"): got = self._active_cursor.fetchall()
			elif (wanted == "lastrowid"): got = self._active_cursor.lastrowid
			elif (wanted == "rowsaffected"): got = self._active_cursor.rowcount

			result[wanted] = got

		if (objectify_from_table):
			column_names: list[str] = [
				col[0] for col in (self._active_cursor.description or []) ]

			rows = result.get("fetchall")

			if (rows): result["fetchall"] = self.objectify_results(
					rows, objectify_from_table,
					column_names, derived_columns)

		self.connection.commit()
		self.close_cursor()

		# WAS SUCCESSFUL! DECLARE SO!
		self.reset_time_idle()

		return result



	@db_error_catcher_rethrows
	def execute_multiple(
			self,
			queries: list[str],
			paramses: Optional[list[QueryParams | list[QueryParams]]] = None,
			expect_response: bool = False,
			buffered: bool = True,
			objectify_from_table: Optional[Table[Any]] = None, 
			derived_columns: Optional[list[str]] = None,
			**kwargs: Any) -> DSA:
		"""
		Execute multiple SQL statements.
		If you want to execute one statement for multiple params,
		call execute() with a list[tuple] params.

		Call execute_multiple() for multiple SQL statements

		`**kwargs` is included, so this function will ignore extra
		params in your payload.
		"""
		if (not paramses): paramses = []
		if (not derived_columns): derived_columns = []

		assert len(queries) == len(paramses)
		assert self.connection, "The database is not connected"
		if (kwargs):
			ignored = set(kwargs.keys()) - {
				'debug', 'debug_config', 'tables_involved'}
			if (ignored): self.logger.debug(f"Ignoring {ignored} kwargs..")

		result: DSA = {}

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

		if (expect_response):
			result = {
				"fetchall": self._active_cursor.fetchall()
			}

		if (objectify_from_table):
			column_names: list[str] = [
				col[0] for col in (self._active_cursor.description or []) ]

			got = result.get("fetchall")

			if (got): result["fetchall"] = self.objectify_results(
				got, objectify_from_table,
				column_names, derived_columns)

		self.connection.commit()
		self.close_cursor()

		# WAS SUCCESSFUL! DECLARE SO!
		self.reset_time_idle()
		return result

	def execute_payload(self, payload: DSA) -> DSA:
		""" Execute SQL Statement from `dict` payload. """

		routine: Callable[..., Any]

		if (payload.get("queries")): routine = self.execute_multiple
		else: routine = self.execute

		return routine(**payload)


	def execute_payload_async(
			self, payload: DSA) -> Future[DSA]:
		""" Execute SQL Statement from `dict` payload. """

		routine: Callable[..., Any]

		if (payload.get("queries")): routine = self.execute_multiple
		else: routine = self.execute

		return async_executor(routine, **payload)



	def objectify_result(
			self,
			ms_result: MySQLRowType,
			table: Table[Any],
			fetched_column_names: list[str],
			derived_column_names: list[str]) -> TableRow | dict[str, TableRow]:
		""" ### Convert one dictionary result to the object of its table. """

		assert len(ms_result) == len(fetched_column_names), \
			f"length of results not equal to amount of column names"

		result = dict(
			(fetched_column_names[i], ms_result[i])
			for i in range(len(fetched_column_names)) )
		
		row: TableRow = table.row.from_dict(result, True)

		if (not derived_column_names): return row

		return {
			row._table.name: row, # type: ignore
			"derived": TableRow.collect_derived_columns(
				derived_column_names, result)
		}



	def objectify_results(
			self,
			results: list[MySQLRowType],
			table: Table[Any],
			column_names: list[str],
			derived_column_names: list[str]
			) -> list[TableRow | dict[str, TableRow]]:
		""" ### Objectify a list of results easily. """

		return [
			self.objectify_result(v, table, column_names, derived_column_names)
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
