from datetime import datetime
from os import path
import json

from backend_collection.constants import DATE_FMT


class State(): # give same instance to writer and scheduler
	STATE_FILE = path.join("state", "state.json")

	keywords_todo: list[str] = []
	ids_todo: list[int] = []

	now: datetime
	time_next_batch: datetime
	session: int = 0

	store_names: dict[str, int] = {}

	keys = ["keywords_todo", "now", "time_next_batch", "session", "store_names"]
	
	def dump(self):
		self.now = datetime.now()
		data = {} #todo type

		for k in self.keys:
			v = getattr(self, k)

			if (isinstance(v, datetime)):
				v = v.strftime(DATE_FMT)

			data[k] = v
		
		with open(self.STATE_FILE, "w") as f:
			json.dump(data, f)



	def load(self):
		""" Load from JSON """

		with open(self.STATE_FILE, "r") as f:
			data = json.load(f)
		
		for k in self.keys:
			v = data.get(k)
			
			if (v is None):
				try: 
					curr = getattr(self, k)
					if (curr is not None): continue
				except: pass

				setattr(self, k, v)
				continue

			type_ = self.__annotations__[k]
			if (type_ == datetime):
				v = datetime.strptime(v, DATE_FMT)

			setattr(self, k, v)

