from dbmanager2.types import Generic, Type, T, Any, Optional, Literal, DSS, DSA, Union, overload, TypeVar
from dbmanager2.misc import uid, flatten

from datetime import datetime



TableRowType = TypeVar("TableRowType", bound = "TableRow")


SQL_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


class Validator():
	def __init__(self, db_type: str, value: Any):
		self.db_type = db_type.replace(" UNSIGNED", "")
		self.value = value
		self.unsigned = "UNSIGNED" in db_type
	

	def CHAR(self, size: int): return len(self.value) == size
	def VARCHAR(self, size_exc: int): return len(self.value) < size_exc

	def TINYTEXT(self): return self.VARCHAR(255)
	def MEDIUMTEXT(self): return self.VARCHAR(16_777_216) # 2**24
	def LONGTEXT(self): return self.VARCHAR(4_294_967_296) # 2**32

	def _NUMBER(self, signed_max_exc: int):
		if (self.unsigned): return self.value < (signed_max_exc * 2)
		else: return self.value >= -signed_max_exc and self.value < signed_max_exc
	
	def TINYINT(self): return self._NUMBER(128)
	def SMALLINT(self): return self._NUMBER(32_768)
	def MEDIUMINT(self): return self._NUMBER(8_388_608)
	def INT(self): return self._NUMBER(2_147_483_648)

	TYPES_CHECKING = Literal[
		"CHAR", "VARCHAR", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT",
		"TINYINT", "TINYINT UNSIGNED", "SMALLINT", "SMALLINT UNSIGNED",
		"MEDIUMINT", "MEDIUMINT UNSIGNED", "INT", "INT UNSIGNED"]






class CMP():
	""" Class used to help define query statements. """

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


class NOT(CMP):
	def __init__(self, value: Any):
		self.a = value
	
	def __str__(self):
		a = self._convert_to_str(self.a)

		return f"NOT ({a})"







class Join():

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
	def __init__(
			self, db_field: str, db_type: Validator.TYPES_CHECKING,
			py_type: type[T], required: bool = False,
			default_value: Optional[T] = None, primary_key: bool = False,
			reference: Optional["TableColumn[Any]"] = None,
			_row_instantiated: bool = False,
			_row_template: bool = True,
			_table: Optional["Table[Any]"] = None):
		
		self._db_type: Validator.TYPES_CHECKING = db_type
		self._db_field = db_field
		self._py_type = py_type
		self._required = required
		self._default_value = default_value
		self._is_pk = primary_key
		self._row_instantiated = _row_instantiated
		self._row_template = _row_template

		self._value = default_value if _row_instantiated else None
		self._value_changed = False


		self._table: Optional[Table[Any]] = _table
		self._references: Optional[TableColumn[Any]] = reference


	@property
	def value(self):
		if (not self._row_instantiated):
			raise AttributeError(
				"TableColumn templates do not have values, "
				"only value holder instances do")
		
		return self._value
	
	@value.setter
	def value(self, v: T):
		if (not self._row_instantiated):
			raise AttributeError(
				"Cannot set the value of TableColumn templates, "
				"must be value holder instance")
		
		self._value = v
		self._value_changed = True
	

	@property
	def references(self): return self._references
	
	@references.setter
	def references(self, other: "TableColumn[Any]"):
		if (not other.is_row_instantiated):
			raise AttributeError(
				"Reference (other) must be a TableColumn from an instantiated "
				"TableRow. You are working with your "
				"type[TableRow].TableColumn, but you must use your "
				"Table.row.TableColumn"
			)
		
		if (not (self.is_template and other.is_template)):
			raise AttributeError(
				"You may not define references from value holder instances "
				"of TableColumn. You are running your Table.row.new().TableColumn, "
				"but you may only define Table.row.TableColumn.references"
			)
		
		#if (id(self.table) == id(other.table)):
		#	other._table = other._table.as_alias(uid())

		self._references = other
	

	# READ-ONLY FOR THE USER
	@property
	def is_primary_key(self): return self._is_pk

	@property
	def is_template(self): return self._row_template

	@property
	def is_row_instantiated(self): return self._row_instantiated

	@property
	def value_changed(self): return self._value_changed

	@property
	def table(self): return self._table

	@property
	def field(self): return self._db_field

	

	def duplicate(self, table):
		return self.__class__(
			self._db_field, self._db_type, self._py_type, self._required,
			self._default_value, self._is_pk,
			self._references, True, False, table
		)

	def _create_value_holder(self, table: "Table[Any]"):
		return self.__class__(
			self._db_field, self._db_type, self._py_type, self._required,
			self._default_value, self._is_pk,
			self._references, True, True, table
		)
	





	def in_(self, objects: list[Any]) -> CMP:
		return CMP(self, objects, "IN")
	
	def like_(self, objects: list[Any]) -> CMP:
		return CMP(self, objects, "LIKE")

	def __eq__(self, value: object) -> CMP:
		return CMP(self, value, "=")

	def __ne__(self, value: object) -> CMP:
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
		if (not self.table):
			raise AttributeError(
				"TableRow is not instantiated, why are you here"
			)

		return f"{self.table.identifier}.{self._db_field}"





class TableRow():
	"""
	TableRow contains all TableColumns of a Table.
	Always access through `Table.rows`.

	Create one through `Table.rows.new()`, with this instance
	you can assign new values
	"""

	def __init__(self, table: "Table[Any]"):
		self._table = table
		self._columns: list[str] = []
		self._pkeys: list[str] = []
		self._joins: list[Join] = []

		self._is_template: bool = True

		for k in dir(self):
			v = getattr(self, k)

			if (not isinstance(v, TableColumn)): continue

			if (not v._table): v._table = table # type: ignore
			v._row_instantiated = True # type: ignore
			v._row_template = True # type: ignore

			self._columns.append(k)
			if (v.is_primary_key): self._pkeys.append(k)
			
			if (v.references):
				print(table.name, k, "references", v.references.table.name, v.references._db_field)
				other_table = v.references.table

				#if (id(self._table) == id(other_table) and not other_table.alias):#other_table.name == self._table.name): # id() == id() ?
				#	other_table = other_table.as_alias(uid())

				self._joins.append(Join(other_table, v == v.references))


	# READ-ONLY FOR THE USER
	# USE METHODS, NOT SETTERS, TO DISTINGUISH FROM TableColumn ATTRS.
	def is_value_holder(self): return self._is_template
	def get_joins(self): return self._joins
	def get_columns(self): return self._columns



	def get_changes(self):
		changes: DSA = {}

		for attr in self._columns:
			column: TableColumn[Any] = getattr(self, attr)
			if (not column.value_changed): continue

			changes[attr] = column.value
		
		return changes



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
		"""

		new = self.new()

	
	def duplicate(self):
		new = self.__class__(self._table)
		new._is_template = True

		for attr in new._columns:
			column: TableColumn[Any] = getattr(new, attr)

			new_column = column.duplicate(self._table) # type: ignore
			setattr(new, attr, new_column)
		
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
	def __init__(
			self, db_name: str, row_model: type[TableRowType], _alias: str = ""):
		self._db_name = db_name
		print(db_name,_alias, id(row_model))
		self._row_model = row_model
		self._alias = _alias
	

	# READ-ONLY FOR THE USER
	@property
	def row(self) -> TableRowType: return self._row_model(self)

	@property
	def name(self): return self._db_name

	@property
	def alias(self): return self._alias



	def select(
			self, columns: Optional[list[TableColumn[Any]]] = None,
			distinct: bool = False, where: CMP | None = None,
			join_all: bool = False, join_on: list[Join] = [], limit: int = 1000,
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

		all_columns = columns
		if (not columns):
			all_columns = []
			
			for v in tables_involved:
				r: TableRow = v.row
				cols: list[TableColumn[Any]] = [getattr(r, col) for col in r.get_columns()]

				all_columns.extend(cols)
		
		order_by_strs: list[str] = [ str(v) for v in order_by]
		

		# BUILD str STATEMENT:
		what_to_select = ", ".join( f"{v} AS \'{v}\'" for v in all_columns )

		sql: str = f"SELECT {what_to_select} FROM {self}" # BASE

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














	# NAMING FUNCTIONS

	def as_alias(self, alias: str):
		""" Create new instance of Table with alias. """

		if (self._alias):
			raise AttributeError("This table has already been aliased.")
		
		return self.__class__(self._db_name, self._row_model, alias)

	
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
