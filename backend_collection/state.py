from datetime import datetime
import json


class State(): # give same instance to writer and scheduler
	STATE_FILE = "state.json"

	keywords_todo: list[str] = []
	ids_todo: list[int] = []

	now: datetime
	time_next_batch: datetime
	batch: int = 0

	store_names: dict[str, int] = {}

	keys = ["keywords_todo", "ids_todo", "now", "time_next_batch", "store_names"]

	def new_batch(self):
		data_today = {}
		# set time
	
	def dump(self):
		self.now = datetime.now()
		data = {} #todo type

		for k in self.keys:
			v = getattr(self, k)

			data[k] = v
		
		with open(self.STATE_FILE, "w") as f:
			json.dump(data, f)



	def load(self):
		""" Load from JSON """

		with open(self.STATE_FILE, "r") as f:
			data = json.load(f)
		
		for k in self.keys:
			v = data.get(k)
			if (not v): continue

			setattr(self, k, v)

