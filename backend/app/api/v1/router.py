from fastapi import APIRouter
from app.api.v1.endpoints import auth, balancete, conciliacao, dashboard, auditoria, empresa

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(empresa.router)
api_router.include_router(balancete.router)
api_router.include_router(conciliacao.router)
api_router.include_router(dashboard.router)
api_router.include_router(auditoria.router)
