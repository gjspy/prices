from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Body, APIRouter
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from dotenv import dotenv_values
from datetime import datetime
from functools import wraps
from time import time
from os import path
import json
import os

from backend.log_handler import get_logger, CustomLogger
from dbmanager.engine import Database
from backend.dbclasses import (
	Products, ProductLinks, PriceEntries, Ratings, Images,
	Brands, Stores, Offers, OfferHolders, Labels, Keywords,

	Store)


from backend.api.routers import data

config = dotenv_values(".config")
env = dotenv_values(".env")

logger = get_logger("api", path.join("state", "apistats.json"))


app = FastAPI() # TODO secure docs


app.include_router(data, prefix = "v1")