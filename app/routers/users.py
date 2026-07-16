from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.config import SECRET_KEY, ALGORITHM
from app.db_depends import get_async_db
from app.models.users import User as UserModel
from app.schemas import UserCreate, User as UserSchema, RefreshTokenRequest
from app.auth import hash_password, verify_password, create_access_token, create_refresh_token

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserSchema)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_async_db)) -> UserSchema:
    email_stmt = select(UserModel).where(
        UserModel.is_active == True,
        UserModel.email == user.email,
    )
    email = (await db.scalars(email_stmt)).first()
    if email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    db_user = UserModel(
        email=user.email,
        hashed_password=hash_password(user.password),
        role=user.role,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_async_db)) -> dict:
    user_stmt = select(UserModel).where(
        UserModel.email == form_data.username,
        UserModel.is_active == True,
    )
    user = (await db.scalars(user_stmt)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email, "role": user.role, "id": user.id})
    refresh_token = create_refresh_token(data={"sub": user.email, "role": user.role, "id": user.id})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh-token")
async def update_refresh_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_async_db)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    old_refresh_token = body.refresh_token

    try:
        payload = jwt.decode(old_refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("token_type")
        if email is None or token_type != "refresh":
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    user_stmt = select(UserModel).where(UserModel.is_active == True, UserModel.email == email)
    user = (await db.scalars(user_stmt)).first()
    if user is None:
        raise credentials_exception

    new_refresh_token = create_refresh_token(data={"sub": email, "role": user.role, "id": user.id})
    return {"refresh_token": new_refresh_token, "token_type": "bearer"}


@router.post("/access-token")
async def update_access_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_async_db)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    old_refresh_token = body.refresh_token

    try:
        payload = jwt.decode(old_refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("token_type")
        if email is None or token_type != "refresh":
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    user_stmt = select(UserModel).where(UserModel.is_active == True, UserModel.email == email)
    user = (await db.scalars(user_stmt)).first()
    if user is None:
        raise credentials_exception

    new_access_token = create_access_token(data={"sub": email, "role": user.role, "id": user.id})
    return {"access_token": new_access_token, "token_type": "bearer"}

