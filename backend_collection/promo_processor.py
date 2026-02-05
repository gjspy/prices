import traceback
import re

from backend_collection.types import  Any, Callable, Optional, DSA
from backend_collection.constants import (
	regex, convert_str_to_pence, OFFER_TYPES, get_dt)


class InterfacePromoKeys:
	"""
	Class to describe keys in promo objects.
	"""

	# REQUIRED
	promo_id = NotImplemented
	promo_description = NotImplemented
	promo_type = None # NOT REQUIRED

	# OTHER (NOT REQUIRED)
	start_date = None
	end_date = None
	requires_membership = None
	online_exclusive = None


class PromoProcessor:
	""" Class used to process one singular promotion. """
	keys: InterfacePromoKeys = NotImplemented

	# USED IN BASE CLASS
	multibuy_cheapest_free_keyword: Optional[str] = None
	datetime_fmt: Optional[str] = None

	# ONLY USED IN SUBCLASS
	membership_price_promo_keyword: str
	online_exclusive_keyword: str
	pricematch_keyword: str

	def __init__(
			self, result: DSA, specific_promo: DSA):
		self.entire_data = result
		self.promo_data = specific_promo

		self.strapline: str = specific_promo.get(self.keys.promo_description) or ""
		self.promo_id: str = specific_promo.get(self.keys.promo_id) or ""
		
		self.promo_type: str = (
			specific_promo.get(self.keys.promo_type) if (self.keys.promo_type)
			else "") or ""

		self._strapline_checks: list[Callable[[], Optional[DSA]]] = [
			self.check_reduction,
			self.check_multibuy]
		
		self._entire_checks: list[Callable[[], Optional[DSA]]] = []	


	@property
	def promo_start_date(self):
		if (self.keys.start_date is None): return None

		v = self.promo_data.get(self.keys.start_date)
		if (v is None): return
		return get_dt(v, self.datetime_fmt or "")


	
	@property
	def promo_end_date(self):
		if (self.keys.end_date is None): return None

		v = self.promo_data.get(self.keys.end_date)
		if (v is None): return
		return get_dt(v, self.datetime_fmt or "")
	
	@property
	def promo_requires_membership(self):
		return (
			None if (not self.keys.requires_membership)
			else self.promo_data.get(self.keys.requires_membership)
		)
	
	@property
	def promo_online_exclusive(self):
		return (
			None if (not self.keys.online_exclusive)
			else self.promo_data.get(self.keys.online_exclusive)
		)

	
	def _build_initial_data(self):
		return {
			"start_date": self.promo_start_date,
			"end_date": self.promo_end_date,
			"requires_membership": self.promo_requires_membership,
			"online_exclusive": self.promo_online_exclusive,
			"store_given_id": self.promo_id
		}
	

	def _query_regex(
			self, expression: str, string: str) -> Optional[tuple[Any, ...]]:
		""" 
		Uses `re` to query `string` with `expression`.
		Automatically converts `string` to all lowercase as standard.
		"""

		regmatch = re.search(expression, string.lower())
		if (not regmatch): return

		return regmatch.groups()

	


	def check_reduction(self) -> Optional[DSA]:
		""" Check description for match of "now [X], was [Y]" """
		if (not self.strapline): return

		groups = self._query_regex(regex.REDUCTION, self.strapline)
		if (not groups): return

		return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"was_price": convert_str_to_pence(groups[1]),
			"reduced_price": convert_str_to_pence(groups[0])
		}


	def check_multibuy(self) -> Optional[DSA]:
		"""
		Check description for match of "buy [X] for [Y]"
		Check description for match of "any [x] for [y]"

		Check description for match of either of the above,
		where y is an amount and includes
		"cheapest item free" [`multibuy_cheapest_free_keyword`]
		"""
		if (not self.strapline): return

		groups = self._query_regex(regex.MULTIBUY, self.strapline)

		if (not groups):
			groups = self._query_regex(regex.ANYFOR, self.strapline)
			if (not groups): return
		
		if (self.multibuy_cheapest_free_keyword):
			if (self.multibuy_cheapest_free_keyword in self.strapline.lower()):
				return {
					"offer_type": OFFER_TYPES.any_for,
					"any_count": int(groups[0]),
					"for_count": int(groups[1])
				}

		return {
			"offer_type": OFFER_TYPES.any_for,
			"any_count": int(groups[0]),
			"for_price": convert_str_to_pence(groups[1])
		}
	


	def _process_by_type(self) -> Optional[DSA]:
		raise NotImplementedError
	

	def _run_strapline_checks(self):
		"""
		EACH STRAPLINE ONLY SHOWS ONE OFFER. RETURNS WHEN FOUND.
		CREATE NEW PromoProcessor FOR DIFFERENT DATAS.
		"""
		for check in self._strapline_checks:
			try: result = check()
			except Exception as err: traceback.print_exception(err)
			else:
				if (result): return result


	def process_promo(self) -> DSA:
		initial_data = self._build_initial_data()
		result = {}

		if (self.promo_type):
			try: result = self._process_by_type()
			except Exception as err: traceback.print_exception(err)
			else:
				if (result): return {**initial_data, **result}
		
		# PROCESSING BY TYPE DID NOT WORK, USE STRAPLINE/DESCRIPTION:
		if (self.strapline):
			from_strapline = self._run_strapline_checks()
			if (from_strapline): return {**initial_data, **from_strapline}

		return {
			**initial_data,
			"offer_type": OFFER_TYPES.unknown,
			"data": self.promo_data,
			"error": True
		}
	

	def run_entire_checks(self) -> list[DSA]:
		gathered: list[DSA] = []

		for check in self._entire_checks:
			result = check()

			if (result): gathered.append(result)
		
		return gathered