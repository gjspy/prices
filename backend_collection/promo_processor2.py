from typing import Any
import re
import traceback

from backend_collection.constants import regex, convert_str_to_pence, OFFER_TYPES, safe_deepget
from backend_collection.mytypes import DSA

class InterfacePromoKeys:
	promo_from_data = NotImplemented

	promo_id = NotImplemented
	promo_description = NotImplemented
	promo_type = NotImplemented

	start_date = NotImplemented
	end_date = NotImplemented
	requires_membership = NotImplemented


class PromoProcessor:
	# store: str = NotImplemented
	keys: InterfacePromoKeys = NotImplemented

	membership_price_promo_keyword: str = NotImplemented
	multibuy_cheapest_free_keyword: str = NotImplemented

	def __init__(
			self, result: DSA, specific_promo: DSA):
		self.entire_data = result
		self.promo_data = specific_promo

		self.strapline: str = specific_promo.get(self.keys.promo_description) or ""
		self.promo_id: str = specific_promo.get(self.keys.promo_id) or ""
		self.promo_type: str = specific_promo.get(self.keys.promo_type) or ""

		self._strapline_checks = [
			self.check_reduction,
			self.check_membership_price,
			self.check_multibuy]

		
	def get_requires_membership(self):
		return self.promo_data.get(self.keys.requires_membership)

	
	def _build_initial_data(self):
		return {
			"start_date": self.promo_data.get(self.keys.start_date),
			"end_date": self.promo_data.get(self.keys.end_date),
			"requires_membership": self.get_requires_membership(),
			"store_given_id": self.promo_id
		}
	

	def _query_regex(self, expression: str, string: str) -> tuple[Any, ...] | None:
		""" 
		Uses `re` to query `string` with `expression`.
		Automatically converts `string` to all lowercase as standard.
		"""

		regmatch = re.match(expression, string.lower())
		if (not regmatch): return

		return regmatch.groups()

	


	def check_reduction(self):
		""" Check description for match of "now [X], was [Y]" """
		if (not self.strapline): return

		groups = self._query_regex(regex.REDUCTION, self.strapline)
		if (not groups): return

		return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"was_price": convert_str_to_pence(groups[1])
		}


	def check_multibuy(self):
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
	
	
	def check_membership_price(self) -> DSA:
		raise NotImplementedError

	def check_pricematch(self) -> DSA:
		raise NotImplementedError

		


	def process_by_type(self) -> DSA:
		raise NotImplementedError


	def process_promo(self) -> DSA:
		initial_data = self._build_initial_data()

		result = {}

		if (self.promo_type):
			try: result = self.process_by_type()
			except Exception as err: traceback.print_exception(err)
			else: return {**initial_data, **result}
		
		# PROCESSING BY TYPE DID NOT WORK, USE STRAPLINE/DESCRIPTION:
		if (not self.strapline): return {}

		# EACH STRAPLINE ONLY SHOWS ONE OFFER. break WHEN FOUND.
		# CALL process_promo MULTIPLE TIMES FOR DIFFERENT STRAPLINES.
		for check in self._strapline_checks:
			result = check()
			if (result): break
		
		if (result): return {**initial_data, **result}
		
		return {
			**initial_data,
			"offer_type": OFFER_TYPES.unknown,
			"data": self.promo_data,
			"error": True
		}

		

		# TODO: ALDI PRICE MATCH
		# VERIFY IF IS ACTUALLY A PRICE MATCH!! COOL IDEA!!
		# MORRISONS ALSO HAS PRICE MATCHES.s
		# CHECK WHEN SETTING PRODUCT PRICE THAT IT IS NON-DISCOUNTED PRICE.
		# IN PROMO, STORE WAS_PRICE AND NEW_PRICE? IDK WHAT?