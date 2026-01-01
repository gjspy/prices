from typing import Any
import re

from backend_collection.constants import regex, convert_str_to_pence

class PromoKeys:
	promo_id = NotImplemented
	promo_description = NotImplemented

	start_date = NotImplemented
	end_date = NotImplemented
	requires_membership = NotImplemented


class PromoProcessor:
	def __init__(self, store: str, promo_keys: PromoKeys):
		self._store = store
		self._keys = promo_keys

		

	
	def _build_initial_data(self, data: dict[str, Any], promo_id: str | None):
		return {
			"start_date": data.get(self._keys.start_date),
			"end_date": data.get(self._keys.end_date),
			"requires_membership": data.get(self._keys.requires_membership),
			"store_given_id": promo_id
		}
	



	def check_reduction(self, strapline: str):
		""" Check description for match of "now [X], was [Y]" """

		regmatch = re.match(regex.REDUCTION, strapline.lower())

		if (not regmatch): return

		groups = regmatch.groups()

		return {
			"offer_type": "_Reduction",
			"store_given_data": strapline,
			"was_price": convert_str_to_pence(groups[1])
		}
	
	

		


	

	def process_promo(self, data: dict[str, Any]) -> dict[str, Any]:
		promo_description = data.get(self._keys.promo_description)
		promo_id = data.get(self._keys.promo_id)

		if (not promo_description): return {}

		initial_data = self._build_initial_data(data, promo_id)




