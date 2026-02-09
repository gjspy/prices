from concurrent.futures import ThreadPoolExecutor as TPE
from datetime import datetime, timezone
from asyncio import get_running_loop
from functools import partial
from threading import Thread

import re

from backend_collection.types import (
	Number, SDG_Key, DSA,

	Any, Callable, Iterable, Optional)

DATE_FMT = "%y%m%dT%H%M%S"

class StoreNames:
	unknown = "UNKNOWN"
	tesco = "TESCO"
	asda = "ASDA"
	morrisons = "MORRISONS"
	sainsburys = "SAINSBURYS"
	aldi = "ALDI"

class regex:
	"""ALL MATCHES SHOULD USE .lower() FOR THE SEARCH STRING."""

	CLEAN_STR = r"(?:\( *\))|(?:\[ *\])|(?:\{ *\})|(?:^ +)|(?: *,.* *$)"
	MULTI_SPACES = r" {2,}"

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
	_EOS = r"\)? *$"
	_CH = r"[,\(\) ]" # MISC CHARACTERS TO IGNORE
	_UOM = r"([A-z]{0,2}|pint|litre|pound)s?" # UNIT OF MEASUREMENT
	_PS_ONE = rf"([\d\.]+) ?{_UOM}" # 
	PACKSIZE_SINGLE = rf"{_PS_ONE}{_EOS}"

	# "{a} x {b} {unit}", "{a} x {b}", "{a} pack {b} {unit}", "{a} pack {b}"
	# WHERE EVERY SPACE IS OPTIONAL.
	# ALLOWS FOR CLOSING BRACKET.
	# MUST BE END OF STR.
	_PS_MULTI = rf"(\d+) *(?:x|pack|pk) *{_PS_ONE}"
	PACKSIZE_MULTI = rf"(?:(?:{_PS_MULTI}{_CH}+{_PS_ONE})|(?:{_PS_MULTI})|(?:{_PS_ONE}{_CH}+{_PS_MULTI})){_EOS}"
	PACKSIZE_MULTI_GROUPS = ["c", "s", "u", "_", "_", "c", "s", "u", "_", "_", "c", "s", "u"]

	ALL_NON_ASCII = r"[^\x00-\x7F]"

print(regex.PACKSIZE_SINGLE)

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

def int_safe(value: Any) -> Optional[int]:
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


def convert_str_to_pence(value: Optional[str]) -> Optional[int]:
	if (value is None): return None

	if type(value) == int or type(value) == float: # type: ignore [JUST IN CASE]
		return value * 100 # pence
	
	if (value.startswith(".")): return int_safe(value.replace(".", ""))
	if ("£" in value): return int_safe(float(value.replace("£", "")) * 100)
	if ("p" in value): return int_safe(value.replace("p", ""))
	
	return int_safe(float(value) * 100) # pence

def convert_fracorperc_to_perc(value: str):
	if type(value) == int or type(value) == float: # type: ignore [JUST IN CASE]
		return value
	
	if ("/" in value):
		vals = value.split("/")
		return round((int(vals[0]) / int(vals[1]))*100)
	
	if ("%" in value):  return int_safe(value.replace("%",""))


def standardise_packsize(size: str | Number, unit: str) -> tuple[float, str]:
	"""
	Convert packsize data to standard units

	Not all unit types standardised anymore, as it doesnt make sense to.

	Always returns 2-char str representation of unit
	"""
	unit = unit.lower()

	size = float(size)

	if ("kg" in unit): return (size * 1000, "g")
	if ("ml" in unit): return (size, "ml")
	if ("cl" in unit): return (size * 10, "ml")

	if ("mg" in unit): return (size, "mg") # doesn't make sense to / 1000

	"""if ("pint" in unit or "pt" in unit): return (size, "pt")
	if ("fl" in unit): return (size, "fz") # fluid ounce
	if ("gal" in unit): return (size, "ga") # gallon"""

	if ("pint" in unit or "pt" in unit): return (round(size * 568, 2), "ml")
	if ("fl" in unit): return (round(size * 28.4, 2), "ml") # fluid ounce
	if ("gal" in unit): return (round(size * 4546), "ml") # gallon

	if ("oz" in unit): return (round(size * 28.4, 2), "g")
	if ("pound" in unit or "lb" in unit): return (round(size * 454), "g")

	if ("g" in unit): return (size, "g")
	if ("l" in unit): return (size * 1000, "ml")

	if ("mm" in unit): return (size, "mm")
	if ("cm" in unit): return (size * 10, "mm")
	if ("m" in unit): return (size * 100, "mm")

	# TODO others like /sheet for paper, /pod for laundry?
	
	return (0.0, "")



def clean_string(value: str):
	"""
	- Removes preceding, trailing, and double spaces.
	- Removes empty pairs of (), [], {}
	"""
	value = re.sub(regex.CLEAN_STR, "", value)
	value =  re.sub(regex.MULTI_SPACES, " ", value)
	value = re.sub(" +$", "", value)

	return value


def clean_product_name(name: str, brand_name: Optional[str] = None):
	"""
	Remove packsize/brand name, and clean string.

	DO NOT .lower() the string here. Would lose original case.
	regexes use `re.IGNORECASE`

	Also uses an expression to remove any non-ascii characters.
	Helps combat weird formatting.
	"""

	new = name.replace(",", "")
	new = re.sub(regex.PACKSIZE_MULTI, " ", new, flags = re.IGNORECASE)
	new = re.sub(regex.PACKSIZE_SINGLE, " ", new, flags = re.IGNORECASE)
	new = re.sub(regex.ALL_NON_ASCII, " ", new)

	if (brand_name):
		# USE re.sub NOT str.replace SO WE CAN re.IGNORECASE!
		new = re.sub(re.escape(brand_name), " ", new, flags = re.IGNORECASE)
	
	new = clean_string(new)

	if ((not new) or new == " "): return name
	return new


def stringify_query(query_params: dict[str, str | Any], remove_quotes: bool = False):
	"""
	Created this method as an alternative to `urllib.parse.urlencode`
	
	Point of this method is to stringify query params without urlsafing characters.

	Normal Response: "q='cheese'&limit=60"

	Response `remove_quotes = True`: "q=cheese&limit=60
	"""
	v = "&".join(f"{k}={repr(v)}" for k,v in query_params.items())
	return v.replace("'", "") if remove_quotes else v


def get_dt(v: Any, dt_fmt: str = ""):
	try:
		if (isinstance(v, str)):
			if (not dt_fmt): raise ValueError("No dt_fmt")

			return datetime.strptime(v, dt_fmt)

		return datetime.fromtimestamp(float(v), timezone.utc)

	except: pass




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
		self.error: Optional[Exception] = None

	
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