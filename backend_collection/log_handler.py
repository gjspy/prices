from datetime import time as dt_time

import logging
import logging.handlers

log_file_handler = logging.handlers.TimedRotatingFileHandler(
	filename = "collection.log",
	when = "midnight",
	utc = True,
	atTime = dt_time(23, 55),
	backupCount = 14 # N OF LOG FILES TO KEEP
)

log_file_formatter = logging.Formatter(
	fmt = "%(asctime)s - %(levelname)-8s IN %(threadName)-20s :  %(message)s",
	datefmt = "%d-%m-%y %H:%M:%S"
)
log_file_handler.setFormatter(log_file_formatter)

logger = logging.getLogger("gather-logger")
logger.setLevel(logging.DEBUG)
logger.addHandler(log_file_handler)

console = logging.StreamHandler()
console.setFormatter(log_file_formatter)
logger.addHandler(console)