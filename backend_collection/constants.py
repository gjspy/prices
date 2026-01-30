from datetime import datetime, time as dtime, timezone
from concurrent.futures import ThreadPoolExecutor as TPE
from functools import partial
from threading import Thread
from asyncio import get_running_loop
import requests
from typing import Any, Callable, Iterable
import re

import logging
import logging.handlers


from backend_collection.types import Number, SDG_Key, DSA, Optional

COLLECT_START_TIME = "02:00"
DATE_FMT = "%Y%m%dT%H%M%S"

class StoreNames:
	unknown = "UNKNOWN"
	tesco = "TESCO"
	asda = "ASDA"
	morrisons = "MORRISONS"
	sainsburys = "SAINSBURYS"
	aldi = "ALDI"

class regex:
	"""ALL MATCHES SHOULD USE .lower() FOR THE SEARCH STRING."""

	CLEAN_STR = r"(?: {2,})|(?:^ +)|(?: +$)|(?:\( *\))|(?:\[ *\])|(?:\{ *\})"

	# MATCHES £4.29, £4, 29p
	__PRICE = r"(?:£\d+\.\d+)|(?:£\d+)|(?:\d+p)" # DEFINITION, NO CAPTURE
	PRICE = rf"({__PRICE})" # ONE CAPTURE GROUP

	# ALLOWS NUMBER WITHOUT £ OR p, ALSO ALLOWS .95 (DECIMAL WITHOUT LEADING 0)
	PRICE_FLEX = rf"({__PRICE}|(?:\d+\.\d+)|(?:\d+)|(?:\.\d+))" 

	# MATCHES 1/3, 25%
	FRACTION_OR_PERC = r"((?:\d+\/\d+)|(?:\d+%))"
	
	ANYFOR = rf"any (\d+) for {PRICE_FLEX}"
	REDUCTION = rf"now {PRICE},? was {PRICE}"
	MULTIBUY = rf"buy (\d+) for {PRICE_FLEX}"
	MULTIBUY_SAVE = rf"buy (\d+),? save {FRACTION_OR_PERC}"

	SAVE = rf"save {FRACTION_OR_PERC}"

	# MATCHES DIGITS FOLLOWED BY CHAR UNITS.
	PACKSIZE_ONE = r"([\d\.]+) ?([A-z]*)\)?$"

	# "{a} x {b} {unit}", "{a} x {b}", "{a} pack {b} {unit}", "{a} pack {b}"
	# WHERE EVERY SPACE IS OPTIONAL.
	# ALLOWS FOR CLOSING BRACKET.
	# MUST BE END OF STR.
	PACKSIZE_MULTIPLE = rf"(\d+)(?:(?: ?x ?)|(?: ?pack ?)){PACKSIZE_ONE}"

	ALL_NON_ASCII = r"[^\x00-\x7F]"

print(regex.PACKSIZE_MULTIPLE)

class OFFER_TYPES:
	unknown = 0
	any_for = 1
	simple_reduction = 2

class LABEL_TYPES:
	unknown = 0
	price_match = 1

	param_structures: list[tuple[Optional[str]]] = [
		(None, ), ("matching_store", ) ]
	
	n_types = len(param_structures)

	@classmethod
	def get_type(cls, label: DSA):
		for id_ in range(1, cls.n_types):
			structure = cls.param_structures[id_]
			okay = True

			for k in structure:
				if (k is None): continue
				if (label.get(k) is not None): continue

				okay = False
				break
			
			if (okay): return id_
		
		return 0
	
	@classmethod
	def return_params(cls, label_type: int, label: DSA):
		structure = cls.param_structures[label_type]

		data: list[Any] = []

		for k in structure:
			if (k is None):
				data.append(None)
				continue

			data.append(label.get(k))
		
		return data




# TODO: use this for each keyword!
# WE HAVE EXECUTOR AS requests IS NOT NATIVELY ASYNCHRONOUS.
async def async_executor(func: partial[Any]):
	loop = get_running_loop()

	with TPE() as pool:
		result = await loop.run_in_executor(pool, func)

	return result

def sdg_dict_filter(filter_key: dict[Any, Any], data: list[Any]):
	def filterer(v: Any):
		if (not (isinstance(v, dict) or isinstance(v, list))): return

		# MATCH ALL KEYS/VALUES. FIRST FAIL = RETURN.
		for fk, fv in filter_key.items():
			try:
				if (v[fk] != fv): return False
			except: pass
		
		return True
	
	return list(filter(filterer, data))[0]


def safe_deepget(
		data: dict[Any, Any], path: SDG_Key,
		default_value: Any = None) -> Any:
	"""
	Safe method to get nested values of `data` by following `path`
	`path` a list of keys (usually str or int), or callable to filter a list,
	or dict to filter list where all keys/values must match child.
	"""
	
	if (not path): return default_value
	
	for key in path:
		try:
			if (callable(key) and isinstance(data, list)):
				results: Iterable[Any] = filter(key, data)
				data = list(results)[0]
				continue

			if (isinstance(key, dict) and isinstance(data, list)):
				data = sdg_dict_filter(key, data) # type: ignore
				continue

			data = data[key] # NOT .get(), NEED list[index] TOO.

		except: return default_value
	
	return data

def choose_child(data: list[Any], check: Callable[[Any], bool]):
	for child in data:
		try:
			if (check(child)): return child
		except: pass

def int_safe(value: Any) -> int | None:
	try: return int(value)
	except: return None

def utcnow(): return datetime.now(timezone.utc)


def pad_list(l: list[Any], value: Any, length: int):
	"""
	Backfill list `l` until its `len()` matches `length`.
	Returns original `l` if `len()` >= `length`
	"""

	curr_l = len(l)

	return l + [value] * (length - len(l)) if (curr_l < length) else l


def convert_str_to_pence(value: str | None) -> Optional[int]:
	if (value is None): return None

	if type(value) == int or type(value) == float: # type: ignore [JUST IN CASE]
		print(f"assuming int value is £ {value}")
		return value * 100 # pence
	
	if (value.startswith(".")): return int_safe(value.replace(".", ""))
	if ("£" in value): return int_safe(float(value.replace("£", "")) * 100)
	if ("p" in value): return int_safe(value.replace("p", ""))
	
	print(f"assuming int value is £ {value}")
	return int_safe(float(value) * 100) # pence

def convert_fracorperc_to_perc(value: str):
	if type(value) == int or type(value) == float: # type: ignore [JUST IN CASE]
		return value
	
	if ("/" in value):
		vals = value.split("/")
		return round((int(vals[0]) / int(vals[1]))*100)
	
	if ("%" in value):  return int_safe(value.replace("%",""))


def standardise_packsize(size: str | Number, unit: str):
	""" Convert packsize data to standard units (g or ml) """
	unit = unit.lower()

	if (type(size) == str):
		size = size.lower()

		if ("kg" in unit): return (float(size.replace("kg", "")) * 1000, "g")
		if ("ml" in unit): return (float(size.replace("ml", "")), "ml")

		if ("g" in unit): return (float(size.replace("g", "")), "g")
		# TODO ASDA: "L" LITRE CAN BE "LT" (MANUAL INPUT OF DATA SOMEWHERE)
		if ("l" in unit): return (float(size.replace("l","")) * 1000, "ml") 
	
	return (0, "")


def split_packsize_str(value: str) -> tuple[float, str]:
	"""
	Splits packsize into size and unit.
	Does not handle multipacks.

	Then uses standardise_packsize to convert to standard units.
	"""
	value = value.lower()

	match = re.search(regex.PACKSIZE_ONE, value)
	if (not match): return (0, "")

	# TWO VERSIONS POSSIBLE TO MATCH, SO 4 GROUPS UNFORTUNATELY.
	
	size, unit, size_, unit_ = match.groups()

	# ALWAYS INDEPENDENT OF EACH OTHER. NO WORRY ABOUT CROSSOVER.
	size = size or size_
	unit = unit or unit_

	if (not size or not unit): return (0, "")
	
	standardised = standardise_packsize(size, unit)
	return standardised


def clean_string(value: str):
	"""
	- Removes preceding, trailing, and double spaces.
	- Removes empty pairs of (), [], {}
	"""

	return re.sub(regex.CLEAN_STR, "", value)


def clean_product_name(name: str, brand_name: str | None = None):
	"""
	Remove packsize/brand name, and clean string.

	DO NOT .lower() the string here. Would lose original case.
	regexes use `re.IGNORECASE`

	Also uses an expression to remove any non-ascii characters.
	Helps combat weird formatting.
	"""
	name = re.sub(regex.PACKSIZE_MULTIPLE, "", name, flags = re.IGNORECASE)
	name = re.sub(regex.PACKSIZE_ONE, "", name, flags = re.IGNORECASE)
	name = re.sub(regex.ALL_NON_ASCII, " ", name)

	if (brand_name):
		# USE re.sub NOT str.replace SO WE CAN re.IGNORECASE!
		name = re.sub(brand_name, "", name, flags = re.IGNORECASE)
	
	name = clean_string(name)
	return name


def stringify_query(query_params: dict[str, str | Any], remove_quotes: bool = False):
	"""
	Created this method as an alternative to `urllib.parse.urlencode`
	
	Point of this method is to stringify query params without urlsafing characters.

	Normal Response: "q='cheese'&limit=60"

	Response `remove_quotes = True`: "q=cheese&limit=60
	"""
	v = "&".join(f"{k}={repr(v)}" for k,v in query_params.items())
	return v.replace("'", "") if remove_quotes else v

class TaskThread(Thread):
	"""
	Subclassed threading.Thread object, used for running a routine
	asynchronously, and returning a response.
	
	Use this exactly like you would a normal Thread, just call .join()
	asynchronously!
	"""
	def __init__(self, *args: Any, **kwargs: Any):
		self._target: Callable[..., Any]
		self._args: list[Any]
		self._kwargs: DSA

		super().__init__(*args, **kwargs)

		self.value: Any = None
		self.complete: bool = False
		self.error: Exception | None = None

	
	def run(self):
		"""
		Called after Thread().start().

		start() actually starts a thread, run() runs the code in it.
		"""

		if (self._target == None):
			self.complete = True
			return
		
		try:
			self.value = self._target(*self._args, **self._kwargs)
		
		except Exception as err:
			self.error = err
		
		self.complete = True
	
	
