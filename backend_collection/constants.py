from datetime import time as dtime
from threading import Thread
from typing import Any, Callable
import re

import logging
import logging.handlers


from backend_collection.mytypes import Number

COLLECT_START_TIME = "02:00"



ASDA_ENDPOINT = "https://8i6wskccnv-dsn.algolia.net/1/indexes/*/queries"
TESCO_ENDPOINT = "https://xapi.tesco.com"
MORRISONS_ENDPOINT = "https://groceries.morrisons.com/api/webproductpagews/v6/product-pages/search"
SAINSBURYS_ENDPOINT = "https://www.sainsburys.co.uk/groceries-api/gol-services/product/v1/product" # SEARCH ENDPOINT. (SAME AS PRODUCT?)

class StoreNames:
	tesco = "TESCO"
	asda = "ASDA"
	morrisons = "MORRISONS"
	sainsburys = "SAINSBURYS"

class regex:
	"""ALL MATCHES SHOULD USE .lower() FOR THE SEARCH STRING."""

	CLEAN_STR = r"(?: {2,})|(?:^ +)|(?: +$)|(?:\( *\))|(?:\[ *\])|(?:\{ *\})"

	# MATCHES £4.29, £4, 29p
	ANY_PRICE = r"((?:£\d+\.\d+)|(?:£\d+)|(?:\d+p))" # CAPTURE GROUP
	ANY_X_FOR_PROMO = rf"any (\d+) for {ANY_PRICE}"

	MOR_REDUCTION = rf"now {ANY_PRICE}, was {ANY_PRICE}"
	MOR_MULTIBUY = rf"buy (\d+) for {ANY_PRICE}"

	# MATCHES DIGITS FOLLOWED BY CHAR UNITS.
	PACKSIZE_ONE = r"([\d\.]+)([A-z]+)"
	# MATCHES PACKSIZE_ONE, OR PACKSIZE_ONE WITH A SPACE
	# (IF IS AT THE END OF STR), MAY HAVE CLOSING BRACKET BEFORE STR END.
	PACKSIZE_SINGLE = rf"(?:{PACKSIZE_ONE})|(?:([\d\.]+) ?([A-z]+)\)?$)"
	# SECOND HALF OF MULTI IS SAME AS SINGLE, BUT [A-z] IS OPTIONAL.
	# SOME WILL GIVE 4x330 BUT NO UNIT. STILL WANT MATCH.
	PACKSIZE_MULTIPLE = rf"([\d\.]+) ?x ?([\d\.]+)([A-z]*)"


LOG_FORMAT = "%(asctime)s - %(levelname)-8s IN %(threadName)-20s :  %(message)s"
LOG_DATE_FORMAT = "%d-%m-%y %H:%M:%S"

LOG_FORMATTER = logging.Formatter(
	fmt = LOG_FORMAT,
	datefmt = LOG_DATE_FORMAT)

class CustomLogFH(logging.handlers.TimedRotatingFileHandler):
	def __init__(self):
		super().__init__(
			filename = "collection.log", # FILENAME
			when = "midnight", # SWITCH ACTION, HAVE TO SAY THIS AS WELL.
			utc = True, # TIMEZONE
			atTime = dtime(23, 55), # TIME TO SWITCH.
			backupCount = 14 # N OF LOG FILES TO KEEP BEFORE DELETING
		)

		self.setFormatter(LOG_FORMATTER)


	def namer(self, default_name: str) -> str: # type: ignore
		# EG DEFAULT_NAME: 'collection.log.2025-07-31'

		fn: str; ext: str; date: str
		fn, ext, date = default_name.split(".")

		return f"{fn}-{date}.{ext}"
	

class CustomLogSH(logging.StreamHandler): # type: ignore
	formatter = LOG_FORMATTER




def safe_deepget(
		data: dict[Any, Any], path: list[Any],
		default_value: Any = None) -> Any:
	
	for key in path:
		try: data = data[key] # NOT .get(), NEED LIST[index] TOO.
		except: return default_value
	
	if (not data): return default_value
	return data


def dict_add_values(
		data: dict[Any, Any], **kwargs: Any) -> dict[Any, Any]:

	for i,v in kwargs.items():
		data[i] = v

	return data

def int_safe(value: Any) -> int | None:
	try: return int(value)
	except: return None





def convert_str_to_pence(value: str) -> int:
	if type(value) == int or type(value) == float: # type: ignore [JUST IN CASE]
		print(f"assuming int value is £ {value}")
		return value * 100 # pence
	
	if ("£" in value): return int_safe(float(value.replace("£", "")) * 100) or -1
	if ("p" in value): return int_safe(value.replace("p", "")) or -1

	return -1


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
	
	return (-1, "")


def split_packsize_str(value: str) -> tuple[float, str]:
	"""
	Splits packsize into size and unit.
	Does not handle multipacks.

	Then uses standardise_packsize to convert to standard units.
	"""
	value = value.lower()

	match = re.search(regex.PACKSIZE_SINGLE, value)
	if (not match): return (-1, "")

	# TWO VERSIONS POSSIBLE TO MATCH, SO 4 GROUPS UNFORTUNATELY.
	
	size, unit, size_, unit_ = match.groups()

	# ALWAYS INDEPENDENT OF EACH OTHER. NO WORRY ABOUT CROSSOVER.
	size = size or size_
	unit = unit or unit_

	if (not size or not unit): return (-1, "")
	
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
	"""
	name = re.sub(regex.PACKSIZE_MULTIPLE, "", name, flags = re.IGNORECASE)
	name = re.sub(regex.PACKSIZE_SINGLE, "", name, flags = re.IGNORECASE)

	if (brand_name):
		# USE re.sub NOT str.replace SO WE CAN re.IGNORECASE!
		name = re.sub(brand_name, "", name, flags = re.IGNORECASE)
	
	name = clean_string(name)
	return name


def stringify_query(query_params: dict[str, str | Any]):
	"""
	Created this method as an alternative to `urllib.parse.urlencode`
	
	Point of this method is to stringify query params without urlsafing characters.
	"""
	return "&".join(f"{k}={repr(v)}" for k,v in query_params.items())

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
		self._kwargs: dict[str, Any]

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
	
	
