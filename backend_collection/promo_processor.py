from typing import Any
import re
import traceback

from backend_collection.constants import regex, convert_str_to_pence, OFFER_TYPES

class InterfacePromoKeys:
	promo_id = NotImplemented
	promo_description = NotImplemented
	promo_type = NotImplemented

	start_date = NotImplemented
	end_date = NotImplemented
	requires_membership = NotImplemented


class PromoProcessor:
	def __init__(
			self, store: str, promo_keys: InterfacePromoKeys,
			membership_price_promo_keyword: str):
		self._store = store
		self._keys = promo_keys

		self.membership_price_promo_keyword = membership_price_promo_keyword

		self._strapline_checks = [self.check_reduction, self.check_multibuy]

		
	def get_requires_membership(self, data: dict[str, Any]):
		return data.get(self._keys.requires_membership)

	
	def _build_initial_data(self, data: dict[str, Any], promo_id: str | None):
		return {
			"start_date": data.get(self._keys.start_date),
			"end_date": data.get(self._keys.end_date),
			"requires_membership": self.get_requires_membership(data),
			"store_given_id": promo_id
		}
	

	def _query_regex(self, expression: str, string: str) -> tuple[Any, ...] | None:
		""" 
		Uses `re` to query `string` with `expression`.
		Automatically converts `string` to all lowercase as standard.
		"""

		regmatch = re.match(expression, string.lower())
		if (not regmatch): return

		return regmatch.groups()

	



	def check_reduction(self, strapline: str):
		""" Check description for match of "now [X], was [Y]" """
		groups = self._query_regex(regex.REDUCTION, strapline)
		if (not groups): return

		return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"store_given_data": strapline,
			"was_price": convert_str_to_pence(groups[1])
		}
	

	def check_multibuy(self, strapline: str):
		"""
		Check description for match of "buy [X] for [Y]"

		-- or, if no match --

		Check description for match of "any [x] for [y]
		"""
		groups = self._query_regex(regex.MULTIBUY, strapline)

		if (not groups):
			groups = self._query_regex(regex.ANYFOR, strapline)
			if (not groups): return

		return {
			"offer_type": OFFER_TYPES.any_for,
			"any_count": int(groups[0]),
			"for_price": convert_str_to_pence(groups[1])
		}
	
	
	def check_membership_price(self, strapline: str):
		"""
		Check match for membership price keyword.
		MUST BE LAST, AS other promos may include the keyword.
		"""

		# TODO: look at this. how to ensure price is the WAS price.

		if (not self.membership_price_promo_keyword in strapline): return

		price = self._query_regex(regex.PRICE, strapline)
		if (not price): return

		return {
			"offer_type": OFFER_TYPES.simple_reduction,
			"member_reduced_price": convert_str_to_pence(price[0])
		}

		


	def process_by_type(self, promo_type: str) -> dict[str, Any]:
		raise NotImplementedError


	def process_promo(self, data: dict[str, Any]) -> dict[str, Any]:
		promo_description = data.get(self._keys.promo_description)
		promo_id = data.get(self._keys.promo_id)
		promo_type = data.get(self._keys.promo_type)

		initial_data = self._build_initial_data(data, promo_id)

		result = {}

		if (promo_type):
			try: result = self.process_by_type(promo_type)
			except Exception as err: traceback.print_exception(err)
			else: return {**initial_data, **result}
		
		# PROCESSING BY TYPE DID NOT WORK, USE STRAPLINE/DESCRIPTION:

		if (not promo_description): return {}

		for check in self._strapline_checks:
			result = check(promo_description)
			
			if (result): break
		
		if (result): return {**initial_data, **result}
		
		return {
			**initial_data,
			"offer_type": OFFER_TYPES.unknown,
			"data": data,
			"error": True
		}

		

		# TODO: ALDI PRICE MATCH
		# VERIFY IF IS ACTUALLY A PRICE MATCH!! COOL IDEA!!
		# MORRISONS ALSO HAS PRICE MATCHES.s