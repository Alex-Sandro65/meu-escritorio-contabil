from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.core.database import get_db
from app.core.security import (
    verify_password, hash_password, create_access_token,
    create_refresh_token, decode_token, generate_mfa_secret,
    get_mfa_qrcode, verify_mfa_token
)
from app.models.user import User
from app.models.tenant import Tenant

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False


class MFAVerify(BaseModel):
    token: str
    temp_token: str


class RegisterRequest(BaseModel):
    nome: str
    email: EmailStr
    password: str
    nome_escritorio: str
    cnpj_escritorio: Optional[str] = None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    tenant = Tenant(nome=data.nome_escritorio, cnpj=data.cnpj_escritorio or None)
    db.add(tenant)
    await db.flush()

    from app.models.user import PerfilUsuario
    user = User(
        tenant_id=tenant.id,
        nome=data.nome,
        email=data.email,
        hashed_password=hash_password(data.password),
        perfil=PerfilUsuario.ADMIN,
    )
    db.add(user)
    await db.commit()
    return {"message": "Cadastro realizado com sucesso", "tenant_id": str(tenant.id)}


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form_data.username, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    if user.mfa_ativo:
        temp_token = create_access_token(str(user.id), expires_delta=__import__("datetime").timedelta(minutes=5))
        return TokenResponse(
            access_token="",
            refresh_token="",
            mfa_required=True,
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/mfa/verify", response_model=TokenResponse)
async def mfa_verify(data: MFAVerify, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.temp_token)
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not verify_mfa_token(user.mfa_secret, data.token):
        raise HTTPException(status_code=400, detail="Código MFA inválido")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me")
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models.tenant import Tenant
    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()
    return {
        "id": str(current_user.id),
        "nome": current_user.nome,
        "email": current_user.email,
        "perfil": current_user.perfil,
        "tenant_id": str(current_user.tenant_id),
        "escritorio": tenant.nome if tenant else "",
    }


@router.post("/mfa/setup")
async def mfa_setup(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    secret = generate_mfa_secret()
    qrcode = get_mfa_qrcode(secret, current_user.email)
    current_user.mfa_secret = secret
    await db.commit()
    return {"secret": secret, "qrcode": qrcode}


@router.post("/mfa/enable")
async def mfa_enable(
    data: MFAVerify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_mfa_token(current_user.mfa_secret, data.token):
        raise HTTPException(status_code=400, detail="Código MFA inválido")
    current_user.mfa_ativo = True
    await db.commit()
    return {"message": "MFA ativado com sucesso"}
