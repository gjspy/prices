from datetime import datetime, timezone, timedelta
from datetime import time as dtime

import logging
import logging.handlers

from constants import *


log_file_handler = CustomLogFH() # CONFIG IN SUBCLASS.
console = CustomLogSH()

logger = logging.getLogger("main-logger") # GETS OR CREATES
logger.setLevel(logging.DEBUG)

logger.addHandler(log_file_handler) # FOR WRITING TO .log FILES
logger.addHandler(console) # FOR WRITING TO TERMINAL





notify()




def main():
	


if (__name__ == "__main__"): main()