from datetime import datetime
from logging import Logger

from functools import wraps
from copy import copy
from os import getenv

from typing import Any, Callable, Self, Type

import mysql.connector
from mysql.connector import Error as MySQLError

from mysql.connector.abstracts import (
	MySQLConnectionAbstract, MySQLCursorAbstract)
from mysql.connector.types import RowType as MySQLRowType
from mysql.connector.pooling import PooledMySQLConnection

from dbmanager.misc import (
	Errors, ExecutionException, ASCENDING_SQL, DESCENDING_SQL, ENVStrucutre,
	flatten)
from dbmanager.types import O, P, T, QP, DSA, DST, DSS


FATAL_ERROR_CODES: list[int] = [2006, 2013, 2055]
MAX_IDLE_TIME: int = 30 # TICKS

SQL_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"



# ERROR CATCHING FOR VARIOUS DB METHODS, TO SAVE REWRITING TRY/EXCEPT
# EVERY TIME.
def error_handling(
		self: "Database", e: Exception | MySQLError, rethrow: bool = False):
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


def db_error_safe_catcher(func: Callable[P, O]) ->  Callable[P, O | None]:

	@wraps(func)
	def wrapper(self: "Database", *args: P.args, **kwargs: P.kwargs) -> O | None:

		try:
			return func(self, *args, **kwargs) # type: ignore

		except Exception as e: # CATCH ERROR CAUSED BY func, HANDLE IT NOW.
			error_handling(self, e)

	return wrapper # type: ignore


def db_error_catcher_rethrows(func: Callable[P, O]) ->  Callable[P, O | None]:

	@wraps(func)
	def wrapper(
		self, *args: P.args, **kwargs: P.kwargs) -> O | None: # type: ignore

		try:
			return func(self, *args, **kwargs) # type: ignore

		except Exception as e: # CATCH ERROR CAUSED BY func, HANDLE IT NOW.
			error_handling(self, e, True) # type: ignore

	return wrapper # type: ignore


class CMP():
	""" Class used to help define query statements. """

	def __init__(self, a: Any, b: Any, symbol: str):
		self.a = a
		self.b = b
		self.symbol = symbol
	
	def _convert_to_str(self, v: Any) -> str:
		if (isinstance(v, datetime)):
			v = f"{v.strftime(SQL_DATETIME_FMT)}"
		
		if (not isinstance(v, TableColumn) and not isinstance(v, CMP)):
			v = f"\'{v}\'" # MUST RUN FOR DATETIME TOO.
		
		if (not type(v) == str): # int, str, float, TableColumn
			v = str(v)
		
		return v
	

	def __str__(self) -> str:
		a = self._convert_to_str(self.a)
		b = self._convert_to_str(self.b)

		
		return f"({a}{self.symbol}{b})"

	# BITWISE OPERATIONS BEING OVERWRITTEN!
	# DO THIS SO CAN WRITE Table1.uid == Table2.uid & Table1.name != "Jim"
	def __and__(self, value: object) -> "CMP": # type: ignore
		return CMP(self, value, " AND ")

	def __or__(self, value: object) -> "CMP": # type: ignore
		return CMP(self, value, " OR ")
	
	def __invert__(self) -> "CMP":
		return NOT(self)



class NOT(CMP):
	def __init__(self, value: Any):
		self.a = value
	
	def __str__(self) -> str:
		a = self._convert_to_str(self.a)

		return f"NOT ({a})"




class Join():
	""" ## Simple class to help define a JOIN statement. ## """

	def __init__(
			self, joining_table_row_model: type["TableRow"],
			condition: CMP | str, join_type: str = "LEFT",
			):
		"""
		## Define a JOIN statement. ##

		Args
		--------
		joining_table_row_model: type[TableRow]
			typr object of the TableRow of the table
			you're joining into this statement.

		condition: CMP | str
			Query str to define how the joined table relates to this.
			Usually linking primary / foreign keys.

		join_type: str
			Optional, can be INNER, LEFT, RIGHT, CROSS.
			Default is LEFT
		"""

		self.join_type = join_type
		self.joining_table_row_model = joining_table_row_model
		self.condition = condition

	def __str__(self) -> str:
		join_type: str = self.join_type
		if (join_type): join_type += " "

		return f"{join_type}JOIN {self.joining_table_row_model.table_name} ON {self.condition}"




# CLASS OF THE CLASSOBJECT THAT DEFINES A TableRow
# TableRow IS THE CLASS, BUT IN PY IS ALSO AN OBJ
# METACLASSES DEFINE THE CLASS THAT CREATES THAT OBJ.
# ATTRS EVALUATE FIRST, SO THEY'RE CREATED FOR US
# TO UPDATE.
class TableRowMeta(type):
	table_name: str
	pkeys: list[str]

	def __new__(cls, name: str, bases: tuple[type, ...], attrs: DSA) -> "TableRow":
		# cls = TableRowMeta
		# new = TableRow!
		new: TableRow = super().__new__(cls, name, bases, attrs) # type: ignore

		table_name = attrs.get("table_name")
		pkeys = attrs.get("pkeys")
		if (not table_name or not pkeys): return new

		# DEFINE ALL PROPERTIES HERE
		new.table_name = table_name
		new.pkeys = pkeys

		# BASED ON DEFINED PROPERTIES WITH TableColumn VALUES,
		# POPULATE DICTIONARIES WHICH DESCRIBE ALL FIELDS AND DATATYPES.
		new._py_fields = {} # type: ignore
		new._db_fields = {} # type: ignore
		new._autoincrement_keys = [] # type: ignore

		v: Any
		for k, v in attrs.items():
			if (not isinstance(v, TableColumn)): continue

			# SLIGHTLY POOR DESIGN, AS IS CIRCULAR:
			# COLUMN.TABLE.COLUMN.TABLE....
			v._table_row_model = new # type: ignore

			new._py_fields[k] = v.py_type # type: ignore
			new._db_fields[v.db_field] = k # type: ignore

			if (v.autoincrement):
				new._autoincrement_keys.append(v.db_field) # type: ignore

		return new




class TableRow(metaclass = TableRowMeta):
	"""
	## Definition of the object a `SELECT * FROM ...` should return. ##
	Use this to describe the python name, db name and python type of each
	column in the table.
	Also, use this to define the table's name in the db, and the primary key.

	Example:
	--------
	>>> class User(TableRow):
	>>>		# DEFINE TABLE NAME.
	>>> 	table_name = "USERS"
	>>>
	>>> 	# DEFINE ALL COLUMNS
	>>> 	user_id = TableColumn("ID", int)
	>>> 	name = TableColumn("NAME", str)
	>>> 	email = TableColumn("EMAIL", str)
	>>>
	>>> 	# DEFINE PRIMARY/COMPOSITE KEY
	>>> 	pkeys = ["ID"]
	"""

	def __init__(self):
		# NOT PRIVATE BECAUSE USER DEFINED IT IN THEIR SUBCLASS
		self.table_name: str
		self.pkeys: list[str] # LIST OF DB KEYS

		# PRIVATE
		self._py_fields: DST # FIELD -> PY TYPE MAP WITH PYTHON KEYS (EG user_name)
		self._db_fields: DSS # FIELD -> PY PROPERTY MAP WITH DB KEYS (EG USERNAME)

		self._autoincrement_keys: list[str]

		self._changes: DSA = {}
		self._load_status = "intialised"

		assert self.table_name, Errors.TBNMissing
		assert self.pkeys, Errors.PKMissing

		# __init__ RUNNING, SO IS INSTANTIATED.
		# CLEAR AWAY TableColumn VALUES.
		k: Any
		for k in dir(self):
			if (k.startswith("_")): continue

			v: Any = getattr(self, k)
			if (not isinstance(v, TableColumn)): continue

			if (v.joins):
				setattr(self, k, Join(
					v.joins.table_row_model, v == v.joins))
				continue

			setattr(self, k, None) # TODO: COULD USE PLCAEHOLDER? EG 0, ""?



	def __setattr__(self, name: str, value: Any) -> None:
		# OVERWRITE THIS TO DETECT CHANGES, FOR UPDATE STATEMENTS.

		super().__setattr__(name, value)

		if (not hasattr(self, "_py_fields")): return
		if (self._py_fields.get(name) == None): return # type: ignore

		if (not hasattr(self, "_autoincrement_keys")): return
		if (name in self._autoincrement_keys): return

		self._changes[name] = value


	# MAKE THE FOLLOWING PROPERTIES REQUIRE METHODS TO ACCESS
	# TO DISTINGUISH PROPERTIES WITH TableColumn VALUES FROM
	# BUILTIN ONES.

	# WE WANT TO USE THEM WITHOUT INSTANTIATING THE CLASS.
	# CLASSMETHODS STILL WORK WHEN INSTANTIATED TOO!
	# NO SETTERS BECAUSE THEY'RE READ-ONLY.
	@classmethod
	def get_db_fields(cls) -> DSA:
		""" db_fields is a dict[db_column_name: py_property_name] """

		try: return cls._db_fields # type: ignore
		except: return {}

	@classmethod
	def get_py_fields(cls) -> DSA:
		""" py_fields is a dict[py_property_name: required_type] """

		try: return cls._py_fields # type: ignore
		except: return {}

	@classmethod
	def get_autoincrement_keys(cls) -> list[str]:
		return cls._autoincrement_keys # type: ignore


	@classmethod
	def list_column_objs(cls) -> list["TableColumn"]:
		return [
			getattr(cls, v) for v in cls.get_py_fields() if hasattr(cls, v)]

	@classmethod
	def get_column(cls, py_field: str) -> "TableColumn":
		return getattr(cls, py_field)


	# IS INSTANTIATED NOW.
	# KEEP WRITE ACCESS PRIVATE
	def get_changes(self): return self._changes
	def commit(self): self._changes = {}

	def is_loaded(self): return self._load_status == "complete"
	def is_partial(self): return self._load_status == "partial"
	def is_only_initial(self):
		"""Equivalent of `not self.is_loaded() and not self.is_partial()`"""
		return self._load_status == "initialised"

	def get_primary_key_value(self) -> list[Any]:
		db_fields = self.get_db_fields()
		pkeys = self.pkeys # list ALLOWS FOR COMPOSITE KEYS

		primary_key: list[Any] = []

		for key in pkeys:
			py_prop = db_fields.get(key)
			assert py_prop, \
				f"PRIMARY KEY {key} DOES NOT HAVE PYTHON PROPERTY"

			primary_key.append(getattr(self, py_prop))

		return primary_key


	def to_dict(self) -> DSA:
		"""
		Convert object into `dict` ready to store in the database.
		"""
		result: DSA = vars(self)

		for k in copy(list(result.keys())): # IS .keys() A GENERATOR? MIGHT CHANGE WHILE ITERATING
			if (not k.startswith("_")): continue

			# TODO: handle joined tables

			del result[k]

		return result



	def to_storable_tuple(self, db_keys: list[str]) -> QP:
		"""
		Convert object into `tuple` ready to store in the database.
		"""
		result: list[Any] = []

		db_fields = self.get_db_fields()
		autoincrement_keys = self.get_autoincrement_keys()

		for k in db_keys:
			if (k in autoincrement_keys): continue

			py_field: str | None = db_fields.get(k)

			if (not py_field):
				result.append(None)

			if (not py_field or py_field.startswith("_")): continue

			v: Any = None

			try: v = getattr(self, py_field)
			except: pass

			# TODO: handle joined tables

			result.append(v)

		print(result)

		return tuple(result)



	def set_autoincrement_value(self, db_field: str, id_: int):
		assert db_field in self.get_autoincrement_keys(), Errors.NotAI

		py_prop = self.get_db_fields().get(db_field)
		assert py_prop, Errors.PKNoPy

		setattr(self, py_prop, id_)



	@classmethod
	def partial_from_id(cls, id_: Any, column: "TableColumn") -> Self:
		this = cls()

		db_fields = cls.get_db_fields()
		py_prop = db_fields[column.db_field]

		setattr(this, py_prop, id_)

		this._load_status = "partial"

		this.commit() # CLEAR changes, BECAUSE WE'VE JUST SET INITIAL VALUES.

		return this


	def _db_value_to_py(self, db_value: Any, required_type: type) -> Any:
		if (required_type == bool and (db_value == 1 or db_value == 0)): ... # TODO

	@classmethod
	def from_dict(cls, data: DSA) -> Self:
		"""
		Load values into object from dictionary provided by `mysql-connector`.
		Works by iterating through all annotated types of `self`, any which have
		values in `data` are written to.
		"""

		# INSTANTIATION. TableColumns REMOVED HERE.
		this = cls()

		col_types = this.get_py_fields()
		print("making", cls.table_name)

		db_col: str
		py_prop: str
		for db_col, py_prop in this.get_db_fields().items():
			existing_value: Join | None = None

			try: existing_value = getattr(this, py_prop)
			except: pass

			# GET VALUE IN data WHICH WILL BE USED TO FILL OBJ.
			# DO THIS BEFORE CHECKING FOR JOIN, ROW MAY NOT HAVE
			# VALUE TO REFERENCE.
			key = f"{cls.table_name}.{db_col}"

			v: Any = data.get(key)
			if (not v):
				# REMOVE JOIN OBJ.
				if (existing_value): setattr(this, py_prop, None)

				continue

			required_type = col_types[py_prop]
			got_type: type[Any] = type(v) # type: ignore

			print(required_type, got_type)

			if (got_type != required_type):
				try:
					print(got_type(v))
					v = required_type(v)
					got_type = type(v) # type: ignore
				except: pass

			# STRICT TYPE CONTROL, RAISE EXCEPTION
			assert required_type == Any or got_type == required_type, \
				f"dict key {db_col} value type {got_type} does not match required {required_type}"

			del data[key] # PREVENTS CIRCULAR REFERENCES

			if (existing_value):
				# CREATES OBJECT FOR JOINED COLUMN
				# IF DATA DOESN'T EXIST (CIRCULAR, OR WASNT JOINED)
				# IN SELECT, CREATES PARTIAL OBJ WITH JUST THE ID.

				joining_model = existing_value.joining_table_row_model

				child = joining_model.from_dict(data)
				child_primary_key = child.get_primary_key_value()

				if (len(child_primary_key) == 0 or None in child_primary_key):
					this_column = cls.get_column(py_prop)
					assert this_column and this_column.joins

					child = joining_model.partial_from_id(v, this_column.joins)

				v = child

			setattr(this, py_prop, v)

		this._load_status = "complete"
		this.commit() # CLEAR changes, BECAUSE WE'VE JUST SET INITIAL VALUES.

		return this




class TableColumn():
	def __init__(
			self, db_field: str, py_type: type,
			required: bool = False, autoincrement: bool = False):
		self._db_field: str = db_field
		self._py_type: type = py_type
		self.required = required
		self.autoincrement = autoincrement

		self._table_row_model: type[TableRow]
		self._relationship: TableColumn | None = None



	@property # READ-ONLY
	def db_field(self): return self._db_field

	@property # READ-ONLY
	def py_type(self): return self._py_type

	@property # NO PRIVATE PROPERTY, READ-ONLY
	def table_name(self): return self._table_row_model.table_name

	@property # READ-ONLY
	def table_row_model(self): return self._table_row_model

	@property # FOR USER TO DEFINE LATER, READ AND WRITE
	def joins(self): return self._relationship

	@joins.setter
	def joins(self, other: "TableColumn"):
		self._relationship = other




	# OVERWRITE DEFAULT COMPARISONS, AS ISNT NECESSARY.
	# WHEN INSTANTIATED, TableColumn OBJECTS ARE REMOVED.
	# NEVER COMPARED TOGETHER, ONLY USED TO FORM SELECT STATEMENTS.

	def in_(self, objects: list[Any]) -> CMP:
		return CMP(self, objects, "IN")

	def __eq__(self, value: object) -> CMP: # type: ignore
		return CMP(self, value, "=")

	def __ne__(self, value: object) -> CMP: # type: ignore
		return CMP(self, value, "<>")

	def __lt__(self, value: object) -> CMP:
		return CMP(self, value, "<")

	def __le__(self, value: object) -> CMP:
		return CMP(self, value, "<=")

	def __gt__(self, value: object) -> CMP:
		return CMP(self, value, ">")

	def __ge__(self, value: object) -> CMP:
		return CMP(self, value, ">=")


	def __str__(self) -> str:
		return f"{self.table_name}.{self.db_field}"


	@property
	def ascending(self) -> str:
		""" Returns ORDER_BY query for this column, ascending. """
		return str(self) + " " + ASCENDING_SQL

	@property
	def descending(self) -> str:
		""" Returns ORDER_BY query for this column, descending. """
		return str(self) + " " + DESCENDING_SQL




class Table():
	def __init__(self, db_name: str, row_model: type[TableRow]):
		self.name: str
		self._row_model: type[TableRow]
		self._db_keys: list[str]
		#self._joins: dict[str, TableColumn]
		self._joins: list[Join]

		self.name = db_name

		self.set_row_model(row_model)


	@property # READ AND WRITE, BUT USE METH FOR SETTER.
	def row_model(self): return self._row_model

	@property # WRITE ACCESS PRIVATE.
	def db_keys(self): return self._db_keys


	# COULD USE SETTER, BUT WANT TO BE EXPLICIT METH
	# BECAUSE IT CHANGES MORE THAN ONE PROPERTY. DB_KEYS
	# DOESN'T HAVE A SETTER.
	def set_row_model(self, new_row_model: type[TableRow]):
		self._row_model = new_row_model
		self._db_keys = list(new_row_model.get_db_fields().keys())

		self._joins = []

		for field in new_row_model.get_py_fields().keys():
			column: TableColumn | None = None

			try: column = getattr(new_row_model, field)
			except: pass

			if ((not column) or (not column.joins)): continue

			#if (joins): self._joins[field] = joins
			self._joins.append(Join(
				column.joins.table_row_model, column == column.joins))


	def select(
			self, condition: CMP | None = None, join_all: bool = False,
			join_on: list[Join] = [], limit: int = 1000,
			order_by: list[str | TableColumn] = []) -> DSA:
		"""
		### Build `SELECT` STATEMENT. ###

		Args
		--------
		condition: CMP
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

		if (join_all): join_on.extend(self._joins)
		tables_involved: list[type[TableRow]] = [
			self.row_model, *( v.joining_table_row_model for v in join_on )]

		all_columns = flatten( v.list_column_objs() for v in tables_involved )
		what_to_select = ", ".join( f"{v} AS \'{v}\'" for v in all_columns )

		sql: str = f"SELECT {what_to_select} FROM {self.name}"


		for join in join_on: sql += " " + str(join)

		if (condition): sql += " WHERE " + str(condition)

		order_by_strs: list[str] = [ str(v) for v in order_by]
		if (len(order_by_strs) > 0):
			sql += " ORDER BY " + ", ".join(order_by_strs)

		if (limit): sql += " LIMIT " + str(limit)

		return {
			"query": sql + ";",
			"expect_response": "fetchall",
			"objectify_from_table": self.name,
			"debug": ("select", "from " + self.name)
		}


	def insert(self, *rows: TableRow) -> DSA:
		""" ### Build `INSERT` STATEMENT. ### """

		autoincrement_keys = self.row_model.get_autoincrement_keys()
		keys_str: str = ", ".join(k for k in self.db_keys if (not k in autoincrement_keys))

		# "%s" FOR EVERY KEY, THEN [: -2] TO REMOVE TRAILING ", "
		n_values = len(self.db_keys) - len(autoincrement_keys)
		placeholder_str: str = ("%s, " * n_values)[: -2]
		values: list[QP] = [ v.to_storable_tuple(self.db_keys) for v in rows ]

		sql: str = f"INSERT INTO {self.name} ({keys_str}) VALUES ({placeholder_str});"

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
		""" ### Build `UPDATE` STATEMENT. ### """

		sqls: list[str] = []
		valueses: list[QP] = []

		for row in rows:
			changes = row.get_changes()

			py_fields = changes.keys()
			db_keys_changed = [
				k for k,v in row.get_db_fields().items() if v in py_fields ]

			set_str = ", ".join( f"{k} = %s" for k in db_keys_changed )
			values = tuple(changes.values())

			where_str = ""

			db_fields = self.row_model.get_db_fields()

			pk: str
			for pk in row.pkeys:
				py_field = db_fields.get(pk)
				assert py_field and hasattr(row, py_field), Errors.PKNoPy

				where_str += f" {row.table_name}.{pk}={getattr(row, py_field)}"
				# TODO: joined tables

			sqls.append(f"UPDATE {self.name} SET {set_str} WHERE{where_str};")
			valueses.append(values)
			row.commit() # CLEAR changes.

		return {
			"queries": sqls,
			"paramses": valueses,
			"debug": ("update", [ type(v).__name__ for v in rows ])
		}




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
		self._table_row_models: dict[str, type[TableRow]]

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
		self._table_row_models = {}

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

	def declare_table_row_model(self, table_row: type[TableRow]):
		self._table_row_models[table_row.table_name] = table_row

	def declare_table_row_models(self, *rows: type[TableRow]):
		for row in rows:
			self.declare_table_row_model(row)



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
			self, query: str, params: QP = (),
			many_params: list[QP] = []):
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
			self, query: str, params: QP  = (), many_params: list[QP] = [],
			expect_response: str = "", buffered: bool = True,
			objectify_from_table: str = "", **kwargs: Any):
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
			self, queries: list[str], paramses: list[QP | list[QP]] = [],
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
			these_params: QP | list[QP] = paramses[i]

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
		model: type[TableRow] | None = self._table_row_models.get(table_name)

		assert model, f"objectify: no model for table_name {table_name}"
		assert len(ms_result) == len(fetched_column_names), \
			f"length of results not equal to amount of column names"

		result = dict(
			(fetched_column_names[i], ms_result[i])
			for i in range(len(fetched_column_names)) )

		print(fetched_column_names)
		print(result)

		return model.from_dict(result)



	def objectify_results(
			self, results: list[MySQLRowType],
			table_name: str, column_names: list[str]) -> list[TableRow]:
		""" ### Objectify a list of results easily. """

		print(results)

		return [
			self.objectify_result(v, table_name, column_names)
			for v in results ]



	@classmethod
	def from_env(
			cls, logger: Logger, init_command: str = "",
			autocommit: bool = False, time_zone_description: str = ""):
		host: str | None = getenv(ENVStrucutre.host)
		prt_: str | None = getenv(ENVStrucutre.port)
		user: str | None = getenv(ENVStrucutre.user)
		pswd: str | None = getenv(ENVStrucutre.pswd)
		schm: str | None = getenv(ENVStrucutre.schm) # TODO: dotenv_values

		to_assert: list[str | None] = [host, prt_, user, pswd, schm]

		assert (host and prt_ and user and pswd and schm), (
			"Load from env missing params: "
			",".join(str(v) for v in to_assert if not v))


		port: int = -1
		try: port = int(prt_)
		except: ValueError("Port must be convertable to int.")

		return cls(
			host = host, port = port, user = user, passwd = pswd, schema = schm,
			logger = logger, init_command = init_command, autocommit = autocommit,
			time_zone_description = time_zone_description)
