from datetime import datetime
from logging import Logger

from functools import wraps
from copy import copy
from os import getenv

from typing import Any, Callable

import mysql.connector
from mysql.connector import Error as MySQLError

from mysql.connector.abstracts import MySQLConnectionAbstract, MySQLCursorAbstract
from mysql.connector.pooling import PooledMySQLConnection

from dbmanager.misc import Errors, ExecutionException, ASCENDING_SQL, DESCENDING_SQL, \
ENVStrucutre
from dbmanager.types import O, P, QP, DSA, DST


FATAL_ERROR_CODES: list[int] = [2006, 2013, 2055]
MAX_IDLE_TIME: int = 30 # TICKS

SQL_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"



# ERROR CATCHING FOR VARIOUS DB METHODS, TO SAVE REWRITING TRY/EXCEPT
# EVERY TIME.
def error_handling(self: "Database", e: Exception | MySQLError, rethrow: bool = False):
	is_fatal: bool = type(e) == MySQLError and e.errno in FATAL_ERROR_CODES
	fatal_str: str = "[FATAL] " if is_fatal else ""

	if (self.connection and self.connection.in_transaction):
		self.logger.exception(
			f"{fatal_str}EXCEPTION WITH DB WHILE TRANSACTING")
		self.connection.rollback()
		self.close_cursor()
		
	else: self.logger.exception(f"{fatal_str}EXCEPTION WITH DB")

	if (is_fatal):
		self.disconnect()
	
	if (rethrow): raise ExecutionException(e, is_fatal)


def db_error_safe_catcher(func: Callable[P, O]) ->  Callable[P, O | None]:

	@wraps(func)
	def wrapper(self: "Database", *args: P.args, **kwargs: P.kwargs) -> O | None:

		try:
			return func(self, *args, **kwargs) # type: ignore

		except MySQLError as e:
			error_handling(self, e)

	return wrapper # type: ignore


def db_error_catcher_rethrows(func: Callable[P, O]) ->  Callable[P, O | None]:

	@wraps(func)
	def wrapper(self: "Database", *args: P.args, **kwargs: P.kwargs) -> O | None:

		try:
			return func(self, *args, **kwargs) # type: ignore

		except MySQLError as e:
			error_handling(self, e, True)

	return wrapper # type: ignore



class CMP():
	""" Class used to help define query statements. """

	def __init__(self, a: Any, b: Any, symbol: str):
		self.a = a
		self.b = b
		self.symbol = symbol

	def __str__(self) -> str:
		a = self.a
		b = self.b

		if (isinstance(a, datetime)): a = f"\'{a.strftime(SQL_DATETIME_FMT)}\'"
		if (isinstance(b, datetime)): b = f"\'{b.strftime(SQL_DATETIME_FMT)}\'"
		
		# int, str, float, TableColumn
		return f"{a}{self.symbol}{b}"
	
	# BITWISE OPERATIONS BEING OVERWRITTEN!
	# DO THIS SO CAN WRITE Table1.uid == Table2.uid & Table1.name != "Jim"
	def __and__(self, value: object) -> "CMP": # type: ignore
		return CMP(str(self), value, " AND ")
	
	def __or__(self, value: object) -> "CMP": # type: ignore
		return CMP(str(self), value, " OR ")


class Join():
	""" ## Simple class to help define a JOIN statement. ## """

	def __init__(
			self, joining_table_name: str,
			condition: CMP | str, join_type: str = ""):
		"""
		## Define a JOIN statement. ##
		
		Args
		--------
		joining_table_name: str
			db name of the table you-re joining into your statement.
		
		condition: CMP | str
			Query str to define how the joined table relates to this.
			Usually linking primary / foreign keys.

		join_type: str
			Optional, can be INNER, LEFT, RIGHT, CROSS.
		"""

		self.join_type = join_type
		self.joining_table_name = joining_table_name
		self.condition = condition

	def __str__(self) -> str:
		join_type: str = self.join_type
		if (join_type): join_type += " "

		return f"{join_type}JOIN {self.joining_table_name} ON {self.condition}"




# CLASS OF THE CLASSOBJECT THAT DEFINES A TableRow
# TableRow IS THE CLASS, BUT IN PY IS ALSO AN OBJ
# METACLASSES DEFINE THE CLASS THAT CREATES THAT OBJ.
# ATTRS EVALUATE FIRST, SO THEY'RE CREATED FOR US
# TO UPDATE.
class TableRowMeta(type):
	def __new__(cls, name: str, bases: tuple[type, ...], attrs: DSA):
		new = super().__new__(cls, name, bases, attrs)

		table_name = attrs.get("table_name")
		if (not table_name): return new

		# DEFINE ALL PROPERTIES HERE
		cls.table_name: str = ""
		cls.pkeys: list[str] = []

		# BASED ON DEFINED PROPERTIES WITH TableColumn VALUES,
		# POPULATE DICTIONARIES WHICH DESCRIBE ALL FIELDS AND DATATYPES.
		cls.py_fields: DST = {} 
		cls.db_fields: DST = {}

		v: Any
		for k, v in attrs.items():
			if (not isinstance(v, TableColumn)): continue

			v._table_name = table_name # type: ignore

			cls.py_fields[k] = v.py_type
			cls.db_fields[v.db_field] = v.py_type
		
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
		self.table_name: str
		self.pkeys: list[str]

		self._changes: DSA
		self.py_fields: DST # FIELD -> TYPE MAP WITH PYTHON KEYS (EG user_name)
		self.db_fields: DST # FIELD -> TYPE MAP WITH DB KEYS. (EG USERNAME)

		assert self.table_name, Errors.TBNMissing
		assert self.pkeys, Errors.PKMissing

		self._changes = {}

		# __init__ RUNNING, SO IS INSTANTIATED.
		# CLEAR AWAY TableColumn VALUES.
		k: Any
		for k in dir(self):
			if (k.startswith("_")): continue

			v: Any = getattr(self, k)
			if (not isinstance(v, TableColumn)): continue

			setattr(self, k, None) # COULD USE PALCEHOLDER? EG 0, ""?



	def __setattr__(self, name: str, value: Any) -> None:
		# OVERWRITE THIS TO DETECT CHANGES, FOR UPDATE STATEMENTS.

		super().__setattr__(name, value)

		if (not hasattr(self, "db_fields")): return
		if (self.py_fields.get(name) == None): return

		self._changes[name] = value



	# NO GETTERS FOR db_fields AND py_fields BECAUSE WE WANT TO USE
	# THEM WITHOUT INSTANTIATING THE CLASS.
	# NO SETTERS BECAUSE THEY'RE READ-ONLY.

	# USE @property BECAUSE IS INSTANTIATED.
	@property # KEEP WRITE ACCESS PRIVATE
	def changes(self): return self._changes



	def to_dict(self) -> DSA:
		"""
		Convert object into `dict` ready to store in the database.
		"""
		result: DSA = vars(self)

		for k in copy(result.keys()):
			if (not k.startswith("_")): continue

			# TODO: handle joined tables

			del result[k]

		return result



	def to_storable_tuple(self) -> QP:
		"""
		Convert object into `tuple` ready to store in the database.
		"""
		result: list[Any] = []

		for k,v in vars(self):
			if (not k.startswith("_")): continue

			# TODO: handle joined tables

			result.append(v)

		return tuple(result)



	@classmethod
	def from_dict(cls, data: DSA) -> "TableRow":
		"""
		Load values into object from dictionary provided by `mysql-connector`.
		Works by iterating through all annotated types of `self`, any which have
		values in `data` are written.
		"""

		this = cls()

		k: str
		for k, required_type in this.py_fields.items():
			if (k.startswith("_")): continue

			v: Any = data.get(k)
			if (not v): continue
			
			# STRICT TYPE CONTROL, RAISE EXCEPTION
			assert required_type == Any or type(v) == required_type, \
				f"dict key {k} value type {type(v)} does not match required {required_type}"

			# TODO: handle joined tables

			setattr(this, k, v)
		
		return this




class TableColumn():
	def __init__(self, db_field: str, py_type: type):
		self._db_field: str = db_field
		self._py_type: type = py_type

		self._table_name: str
		self._sort_order: str
	


	@property
	def db_field(self): return self._db_field

	@property
	def py_type(self): return self._py_type

	@property
	def table_name(self): return self._table_name

	@property
	def sort_order(self): return self._sort_order

	@sort_order.setter
	def sort_order(self, new: str):
		if (type(new) != str):
			raise TypeError("sort_order must be of type str")
		
		if (new != ASCENDING_SQL and new != DESCENDING_SQL):
			raise ValueError(Errors.InvalidSortOrder)
		
		self._sort_order = new



	# OVERWRITE DEFAULT COMPARISONS, AS ISNT NECESSARY.
	# WHEN INSTANTIATED, TableColumn OBJECTS ARE REMOVED.
	# NEVER COMPARED TOGETHER, ONLY USED TO FORM SELECT STATEMENTS.

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
	
	def ascending(self):
		self.sort_order = ASCENDING_SQL
		return self
	
	def descending(self):
		self.sort_order = DESCENDING_SQL
		return self




class Table():
	def __init__(self, db_name: str, row_model: type[TableRow]):
		self.name: str
		self._row_model: type[TableRow]
		self._db_keys: list[str]

		self.name = db_name

		self.set_row_model(row_model)


	@property # READ AND WRITE, BUT USE METH FOR SETTER.
	def row_model(self): return self._row_model

	@property # WRITE ACCESS PRIVATE.
	def db_keys(self): return self._db_keys


	# COULD USER SETTER, BUT WANT TO BE EXPLICIT METH
	# BECAUSE IT CHANGES MORE THAN ONE PROPERTY. DB_KEYS
	# DOESN'T HAVE A SETTER.
	def set_row_model(self, new_row_model: type[TableRow]):
		self._row_model = new_row_model
		self._db_keys = list(new_row_model.db_fields.keys())


	def select(
			self, condition: CMP, join_on: list[Join] = [],
			order_by: list[TableColumn] = []) -> DSA:
		""" ### Build `SELECT` STATEMENT. ### """

		sql: str = f"SELECT * FROM {self.name}"
		
		for join in join_on: sql += " " + str(join)
		sql += " WHERE " + str(condition)

		order_by_strs: list[str] = []

		for v in order_by:
			if (hasattr(v, "sort_order")):
				order_by_strs.append(str(v) + " " + v.sort_order)
				continue

			order_by_strs.append(str(v))

		if (len(order_by_strs) > 0): sql += " "+ ", ".join(order_by_strs)

		return {
			"query": sql + ";",
			"expect_response": True,
			"objectify_from_table": self.name,
			"debug": ("select", "from " + self.name)
		}


	def insert(self, rows: list[TableRow]) -> DSA:
		""" ### Build `INSERT` STATEMENT. ### """
		keys_str: str = ", ".join(self.db_keys)
		
		# "%s" FOR EVERY KEY, THEN [: -2] TO REMOVE TRAILING ", "
		placeholder_str: str = ("%s, " * len(self.db_keys))[: -2]
		values: list[QP] = [ v.to_storable_tuple() for v in rows ]

		sql: str = f"INSERT INTO {self.name} ({keys_str}) VALUES {placeholder_str};"

		payload: DSA = {
			"query": sql,
			"expect_response": False,
			"debug": ("insert", [ type(v).__name__ for v in rows ])
		}

		if (len(values) == 1): payload["values"] = values[0]
		else: payload["many_values"] = values

		return payload

	
	def update(self, data: list[TableRow]) -> DSA:
		""" ### Build `UPDATE` STATEMENT. ### """

		sqls: list[str] = []

		for row in data:
			set_str = ( f"{k} = %s, " for k in row.changes.keys() )
			where_str = ""

			pk: str
			for pk in row.pkeys:
				assert hasattr(row, pk), Errors.PKMissing

				where_str += f" {row.table_name}.{pk}={getattr(row, pk)}" # TODO: joined tables

			sqls.append(f"UPDATE {self.name} SET {set_str} WHERE {where_str};")
		
		return {
			"queries": sqls,
			"debug": ("update", [ type(v).__name__ for v in data ])
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
		if (not self._connection):
			self.connect()
		
		return self._connection


	def increment_time_idle(self): self._time_idle += 1

	def reset_time_idle(self): self._time_idle = 0

	def declare_table_row_model(self, table_row: type[TableRow]):
		self._table_row_models[table_row.table_name] = table_row



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
		""" Connect to the database, returning bool of success. """

		if (self._connection): self.disconnect()

		self._connection = mysql.connector.connect(**self._config)

		self.reset_time_idle() # WAS SUCCESSFUL!
		return True # CONFIRM SUCCESS



	@db_error_safe_catcher
	def disconnect(self):
		""" Disconnect from the database """
		if (not self._connection): return

		self._connection.close()
		self._is_connected = False



	def _init_cursor(self, buffered: bool = True):
		assert self.connection, "Connection does not exist."

		if (self._active_cursor): self.close_cursor()

		self._active_cursor = self.connection.cursor(
			dictionary = True,
			buffered = buffered)

	

	def close_cursor(self):
		if (not self._active_cursor): return

		self._active_cursor.close()
		self._active_cursor = None



	def _execute_one(
			self, query: str, params: QP = (),
			many_params: list[QP] = []):
		"""
		Execute a single SQL Statement.

		MANY = REPEAT query FOR EACH tuple IN params.
		NOT MULTIPLE STATEMENTS.
		"""		

		assert self._active_cursor, "There is no active cursor"

		if (many_params): self._active_cursor.executemany(query, many_params)
		else: self._active_cursor.execute(query, params)



	@db_error_catcher_rethrows
	def execute(
			self, query: str, params: QP  = (),
			many_params: list[QP] = [], expect_response: bool = False,
			buffered: bool = True, objectify_from_table: str = ""):
		"""
		Execute SQL Statement

		Cursor/Session is encapsulated here. If you want to run multiple
		queries before committing, use execute_many()

		Args
		--------
			query: str or list[str]
				SQL statement(s) to run.
			
			params: tuple | None
				Parameters to insert into SQL statement
			
			expect_response: bool
				Whether to run cursor.fetchall() or not.
				Should be True for any select statement.
			
			buffered: bool
				Whether result of a query is read from server immediately,
				by execute() [True], or is read when fetchall() [False] is run.
		"""

		assert self.connection, "The database is not connected"

		result: list[Any]

		self._init_cursor(buffered)
		assert self._active_cursor, "Cursor unsuccessfully initialised"

		# THERE WILL ONLY EVER BE ONE OF params, many_params
		self._execute_one(query, params, many_params)

		result = self._active_cursor.fetchall() if (expect_response) else []
		if (objectify_from_table):
			result = self.objectify_results(result, objectify_from_table)

		self.connection.commit()
		self.close_cursor()

		# WAS SUCCESSFUL! DECLARE SO!
		self.reset_time_idle() 
		
		return result
	


	@db_error_catcher_rethrows
	def execute_multiple(
			self, queries: list[str], paramses: list[QP | list[QP]] = [],
			expect_response: bool = False, buffered: bool = True,
			objectify_from_table: str = ""):
		"""
		Execute multiple SQL statements.
		If you want to execute one statement for multiple params,
		call execute() with a list[tuple] params.
		
		Call execute_multiple() for multiple SQL statements"""

		assert len(queries) == len(paramses)
		assert self.connection, "The database is not connected"

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
			result = self.objectify_results(result, objectify_from_table)

		self.connection.commit()
		self.close_cursor()

		# WAS SUCCESSFUL! DECLARE SO!
		self.reset_time_idle()
		return result



	def objectify_result(self, result: DSA, table_name: str) -> TableRow:
		""" ### Convert one dictionary result to the object of its table. """
		model: type[TableRow] | None = self._table_row_models.get(table_name)

		assert model, f"objectify: no model for table_name {table_name}"

		return model.from_dict(result)



	def objectify_results(
			self, results: list[DSA], table_name: str) -> list[TableRow]:
		""" ### Objectify a list of results easily. """

		return [ self.objectify_result(v, table_name) for v in results ]
	


	@classmethod
	def from_env(
			cls, logger: Logger, init_command: str = "",
			autocommit: bool = False, time_zone_description: str = ""):
		host: str | None = getenv(ENVStrucutre.host)
		prt_: str | None = getenv(ENVStrucutre.port)
		user: str | None = getenv(ENVStrucutre.user)
		pswd: str | None = getenv(ENVStrucutre.pswd)
		schm: str | None = getenv(ENVStrucutre.schm)

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
