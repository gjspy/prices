from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Body, APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from typing import Annotated
from platform import system
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps
from time import time
import json
import os

from enum import Enum

from backend.api.constants import SortOption





router = APIRouter(prefix = "/data")
SEARCH_RETURN_RESULTS = 20
SEARCH_QUERY_MAX_LEN = 50



@router.get("/search")
async def search(
		query: Annotated[str, Query(max_length = SEARCH_RETURN_RESULTS)],
		page: int = 0,
		sort_mode: SortOption = SortOption.relevance):
	
