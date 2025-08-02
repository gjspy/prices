from datetime import time as dtime

import logging
import logging.handlers


COLLECT_START_TIME = "02:00"










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