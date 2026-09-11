from fastapi import APIRouter, Depends
from app.auth import require_vendor_role
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(dependencies=[Depends(require_vendor_role)])

@router.get("/")
def get_negotiation():
    return {"message": "Vendor negotiation endpoint"}
