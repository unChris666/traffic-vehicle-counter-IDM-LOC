"""Serve only checksum-addressed maps downloaded from verified GCS artifacts."""
import re
from pathlib import Path
from ..artifacts import sha

def install_map_route(app,cache):
    from fastapi import HTTPException
    from starlette.responses import FileResponse
    @app.get('/saved-maps/{digest}',include_in_schema=False)
    def saved_map(digest:str):
        if not re.fullmatch('[a-f0-9]{64}',digest):raise HTTPException(404,'Peta tidak tersedia.')
        path=Path(cache)/(digest+'.html')
        if not path.is_file() or path.is_symlink() or sha(path)!=digest:raise HTTPException(404,'Muat ulang hasil untuk membuka peta.')
        return FileResponse(path,media_type='text/html',headers={'Content-Security-Policy':'sandbox allow-scripts','Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff'},content_disposition_type='inline')
