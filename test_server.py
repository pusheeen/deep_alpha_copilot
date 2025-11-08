"""
Minimal FastAPI server to serve the UI for testing without full dependencies.
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()

# Templates directory relative to this file
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'app', 'templates'))

@app.get('/', response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main UI index page."""
    return templates.TemplateResponse('index.html', {'request': request})