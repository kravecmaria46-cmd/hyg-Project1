# -*- coding: utf-8 -*-
"""H.Y.G. PORTAL - БЭКЕНД (FULLY FIXED)"""

# ============================================
# ИМПОРТЫ
# ============================================

import os
import json
import bcrypt
import shutil
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict  # <-- Убедитесь, что есть Dict
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, Integer, ForeignKey, JSON, Float, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from pydantic import BaseModel
import uvicorn
import openai
import nest_asyncio
nest_asyncio.apply()
import asyncio

# ============================================
# СОЗДАЕМ БАЗОВЫЙ КЛАСС ДЛЯ МОДЕЛЕЙ
# ============================================

Base = declarative_base()  # <-- ЭТО БЫЛО ПРОПУЩЕНО!

# ============================================
# ДЕФОЛТНЫЕ ЗНАЧЕНИЯ ДЛЯ AI
# ============================================

POLZA_API_KEY = os.environ.get("POLZA_API_KEY", "your-default-api-key-here")
POLZA_MODEL = os.environ.get("POLZA_MODEL", "deepseek/deepseek-v4-flash")

# ============================================
# БАЗА ДАННЫХ (SUPABASE OPTIMIZED)
# ============================================

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///hyg_portal.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=300,
        pool_pre_ping=True,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ============================================
# МОДЕЛИ (ТЕПЕРЬ Base ОПРЕДЕЛЕН!)
# ============================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    avatar = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    display_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    api_keys = Column(JSON, default=dict)
    active_persona_id = Column(Integer, nullable=True)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

class Character(Base):
    __tablename__ = "characters"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    role = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    personality = Column(Text, nullable=True)
    backstory = Column(Text, nullable=True)
    appearance = Column(Text, nullable=True)
    greeting = Column(Text, nullable=True)
    avatar = Column(String(500), nullable=True)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    world_id = Column(Integer, nullable=True)

class World(Base):
    __tablename__ = "worlds"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    genre = Column(String(50), nullable=True)
    setting = Column(Text, nullable=True)
    rules = Column(Text, nullable=True)
    avatar = Column(String(500), nullable=True)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

class Persona(Base):
    __tablename__ = "personas"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    appearance = Column(Text, nullable=True)
    personality = Column(Text, nullable=True)
    backstory = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)
    goal = Column(Text, nullable=True)
    avatar = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    world_id = Column(Integer, nullable=True)

class Memory(Base):
    __tablename__ = "memories"
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String(20), default="personal")
    importance = Column(Float, default=1.0)
    is_auto = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    persona_id = Column(Integer, nullable=True)
    character_id = Column(Integer, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    chat_id = Column(Integer, nullable=True)

class ChatHistory(Base):
    __tablename__ = "chat_histories"
    id = Column(Integer, primary_key=True)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    persona_id = Column(Integer, nullable=True)
    character_id = Column(Integer, nullable=True)
    world_id = Column(Integer, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))

class LoreEntry(Base):
    __tablename__ = "lore_entries"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)
    tags = Column(JSON, default=list)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    character_id = Column(Integer, nullable=True)
    world_id = Column(Integer, nullable=True)
    room_id = Column(Integer, nullable=True)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))
    world_id = Column(Integer, nullable=True)
    lorebook_id = Column(Integer, nullable=True)
    members = Column(JSON, default=list)

class UserMemory(Base):
    __tablename__ = "user_memories"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fact = Column(Text, nullable=False)
    category = Column(String(50), default="general")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MemoryHierarchy(Base):
    __tablename__ = "memory_hierarchy"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    memory_type = Column(String(20), default="short")
    importance = Column(Float, default=1.0)
    category = Column(String(50), nullable=True)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=True)
    world_id = Column(Integer, ForeignKey("worlds.id"), nullable=True)  # <-- ЭТУ СТРОКУ ДОБАВИТЬ!
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    access_count = Column(Integer, default=0)
    is_forgotten = Column(Boolean, default=False)
    
class MemoryConsolidation(Base):
    __tablename__ = "memory_consolidation"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    summary = Column(Text, nullable=False)
    source_memory_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

# ============================================
# СОЗДАНИЕ БАЗЫ (С МИГРАЦИЕЙ)
# ============================================

try:
    with engine.connect() as conn:
        # Проверяем тип БД
        if DATABASE_URL.startswith("sqlite"):
            # Для SQLite - просто пытаемся добавить колонку
            try:
                conn.execute("ALTER TABLE memory_hierarchy ADD COLUMN world_id INTEGER")
                conn.commit()
                print("✅ Колонка world_id добавлена в SQLite")
            except Exception as e:
                # Колонка уже существует или другая ошибка
                print(f"ℹ️ Колонка уже существует или ошибка: {e}")
        else:
            # Для PostgreSQL/MySQL с внешним ключом
            try:
                conn.execute("ALTER TABLE memory_hierarchy ADD COLUMN world_id INTEGER REFERENCES worlds(id)")
                conn.commit()
                print("✅ Колонка world_id добавлена")
            except Exception as e:
                print(f"ℹ️ Колонка уже существует или ошибка: {e}")
    
    # Создаем остальные таблицы (если их нет)
    Base.metadata.create_all(bind=engine)
    print("✅ База данных подключена")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СЕССИЙ (FIXED)
# ============================================

def create_session(user_id: int) -> str:
    """Создает новую сессию для пользователя"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    with SessionLocal() as db:
        # Удаляем старые сессии этого пользователя
        db.query(Session).filter(Session.user_id == user_id).delete()
        
        session = Session(
            user_id=user_id,
            session_token=token,
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
    
    return token  # <-- ✅ Сессия уже закрыта!

def get_user_by_token(token: str) -> Optional[User]:
    """Получает пользователя по токену сессии"""
    if not token:
        return None
    with SessionLocal() as db:
        session = db.query(Session).filter(
            Session.session_token == token,
            Session.expires_at > datetime.utcnow()
        ).first()
        if not session:
            return None
        return db.query(User).filter(User.id == session.user_id).first()

def delete_session(token: str):
    """Удаляет сессию (выход)"""
    with SessionLocal() as db:
        db.query(Session).filter(Session.session_token == token).delete()
        db.commit()

# ============================================
# FASTAPI
# ============================================

app = FastAPI(title="H.Y.G. Portal")

# Создаем папку для uploads если её нет
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PYDANTIC МОДЕЛИ ---

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class CharacterCreate(BaseModel):
    name: str
    role: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None
    appearance: Optional[str] = None
    greeting: Optional[str] = None
    avatar: Optional[str] = None
    is_public: Optional[bool] = False
    world_id: Optional[int] = None

class WorldCreate(BaseModel):
    name: str
    description: Optional[str] = None
    genre: Optional[str] = None
    setting: Optional[str] = None
    rules: Optional[str] = None
    is_public: Optional[bool] = False
    avatar: Optional[str] = None

class PersonaCreate(BaseModel):
    name: str
    age: Optional[int] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None
    skills: Optional[str] = None
    goal: Optional[str] = None
    avatar: Optional[str] = None
    world_id: Optional[int] = None

class MemoryCreate(BaseModel):
    content: str
    importance: Optional[float] = 1.0
    memory_type: Optional[str] = "personal"
    character_id: Optional[int] = None

class LoreCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = []
    character_id: Optional[int] = None
    world_id: Optional[int] = None
    room_id: Optional[int] = None

class RoomCreate(BaseModel):
    name: str
    description: Optional[str] = None
    world_id: Optional[int] = None
    lorebook_id: Optional[int] = None

class ChatRequest(BaseModel):
    message: str
    character_id: int
    persona_id: Optional[int] = None
    temperature: Optional[float] = 0.8
    mode: Optional[str] = "all"
    max_tokens: Optional[int] = 1500

class ApiKeysUpdate(BaseModel):
    keys: dict

class EditMessageRequest(BaseModel):
    message_id: int
    new_content: str
    is_bot: bool

class GenerateRequest(BaseModel):
    prompt: str
    world_id: Optional[int] = None

class RegenerateRequest(BaseModel):
    character_id: int
    persona_id: Optional[int] = None
    user_message: str
    temperature: Optional[float] = 0.8
    mode: Optional[str] = "all"
    max_tokens: Optional[int] = 1500

# ============================================
# ЗАГРУЗКА АВАТАРОК
# ============================================

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        # Генерируем уникальное имя
        filename = f"{datetime.utcnow().timestamp()}.{ext}"
        filepath = os.path.join("uploads", filename)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"url": f"/uploads/{filename}"}
    except Exception as e:
        return JSONResponse({"error": f"Ошибка загрузки: {str(e)}"}, 500)

# ============================================
# API ЭНДПОИНТЫ
# ============================================

# --- АВТОРИЗАЦИЯ ---

@app.post("/api/register")
async def register(req: RegisterRequest):
    with SessionLocal() as db:
        if db.query(User).filter(User.username == req.username).first():
            return JSONResponse({"error": "Имя уже занято"}, 400)
        
        hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt())
        user = User(username=req.username, password_hash=hashed.decode(), display_name=req.username)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        user_id = user.id
        username = user.username
        
        # Создаем дефолтную персону
        persona = Persona(name=req.username, user_id=user_id)
        db.add(persona)
        db.commit()
        db.refresh(persona)
        
        user.active_persona_id = persona.id
        db.commit()
    
    # Создаем сессию (отдельно, с своей сессией)
    token = create_session(user_id)
    
    return {
        "success": True, 
        "user_id": user_id, 
        "username": username,
        "token": token
    }

@app.post("/api/login")
async def login(req: LoginRequest):
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == req.username).first()
        if not user:
            return JSONResponse({"error": "Пользователь не найден"}, 404)
        if not bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
            return JSONResponse({"error": "Неверный пароль"}, 401)
        
        user_id = user.id
        username = user.username
    
    token = create_session(user_id)
    
    return {
        "success": True, 
        "user_id": user_id, 
        "username": username,
        "token": token
    }

@app.post("/api/logout")
async def logout(token: str):
    delete_session(token)
    return {"success": True}

# --- ПЕРСОНАЖИ ---

@app.get("/api/characters")
async def get_characters(token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        chars = db.query(Character).filter(Character.user_id == user.id).all()
        return [{
            "id": c.id, "name": c.name, "role": c.role,
            "description": c.description, "personality": c.personality,
            "backstory": c.backstory, "appearance": c.appearance,
            "greeting": c.greeting, "avatar": c.avatar,
            "is_public": c.is_public, "world_id": c.world_id
        } for c in chars]

@app.get("/api/characters/public")
async def get_public_characters(limit: int = 20, offset: int = 0, search: str = ""):
    with SessionLocal() as db:
        query = db.query(Character).filter(Character.is_public == True)
        if search:
            query = query.filter(Character.name.contains(search))
        total = query.count()
        chars = query.offset(offset).limit(limit).all()
        return {
            "items": [{"id": c.id, "name": c.name, "role": c.role, "avatar": c.avatar, "user_id": c.user_id} for c in chars],
            "total": total,
            "limit": limit,
            "offset": offset
        }

@app.post("/api/characters")
async def create_character(char: CharacterCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        new_char = Character(**char.dict(), user_id=user.id)
        db.add(new_char)
        db.commit()
        db.refresh(new_char)
        return {"id": new_char.id, "name": new_char.name, "success": True}

@app.put("/api/characters/{char_id}")
async def update_character(char_id: int, char: CharacterCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        existing = db.query(Character).filter(Character.id == char_id, Character.user_id == user.id).first()
        if not existing:
            return JSONResponse({"error": "Персонаж не найден или не принадлежит вам"}, 404)
        
        for key, value in char.dict().items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "name": existing.name, "success": True}

@app.get("/api/characters/{char_id}")
async def get_character(char_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        char = db.query(Character).filter(Character.id == char_id, Character.user_id == user.id).first()
        if not char:
            return JSONResponse({"error": "Персонаж не найден"}, 404)
        return {
            "id": char.id,
            "name": char.name,
            "role": char.role,
            "description": char.description,
            "personality": char.personality,
            "backstory": char.backstory,
            "appearance": char.appearance,
            "greeting": char.greeting,
            "avatar": char.avatar,
            "is_public": char.is_public,
            "world_id": char.world_id
        }

@app.delete("/api/characters/{char_id}")
async def delete_character(char_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        char = db.query(Character).filter(Character.id == char_id, Character.user_id == user.id).first()
        if not char:
            raise HTTPException(404, "Персонаж не найден")
        db.delete(char)
        db.commit()
        return {"success": True}

# --- ГЕНЕРАЦИЯ ПЕРСОНАЖА ЧЕРЕЗ AI ---

class GenerateRequest(BaseModel):
    prompt: str
    world_id: Optional[int] = None

@app.post("/api/generate/character")
async def generate_character(req: GenerateRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    api_keys = user.api_keys or {}
    api_key = api_keys.get("polza") or POLZA_API_KEY
    model = api_keys.get("model") or POLZA_MODEL
    
    if not api_key or api_key == "your-default-api-key-here":
        return JSONResponse({
            "error": "API ключ не настроен. Добавьте ключ Polza в настройках профиля."
        }, 400)
    
    openai.api_key = api_key
    openai.base_url = "https://polza.ai/api/v1/"
    
    # Определяем, короткий это запрос или длинный
    is_short = len(req.prompt.split()) < 10
    
    if is_short:
        system_prompt = """Ты — помощник по созданию персонажей для ролевых игр.
        Пользователь дал КОРОТКИЙ запрос. Твоя задача:
        1. Распознать персонажа
        2. Додумать недостающие детали (характер, внешность, предыстория)
        3. Сделать персонажа ЖИВЫМ и ИНТЕРЕСНЫМ
        
        Сгенерируй персонажа в формате JSON с полями:
        name, role, description, personality, backstory, appearance, greeting.
        
        Заполни ВСЕ поля качественно и подробно!
        description - минимум 2-3 предложения.
        personality - минимум 2-3 предложения.
        backstory - минимум 3-4 предложения.
        appearance - минимум 2 предложения.
        greeting - первое сообщение персонажа.
        
        ВАЖНО: Создай ТОЛЬКО ОДНОГО персонажа!
        ВАЖНО: Ответ должен содержать только JSON, без лишнего текста!"""
    else:
        system_prompt = """Ты — помощник по созданию персонажей для ролевых игр.
        Пользователь дал ПОДРОБНЫЙ запрос. Твоя задача:
        1. Точно следовать всем указаниям пользователя
        2. Не добавлять ничего от себя
        3. Сохранить все детали из запроса
        
        Сгенерируй персонажа в формате JSON с полями:
        name, role, description, personality, backstory, appearance, greeting.
        
        Заполни ВСЕ поля качественно и подробно!
        
        ВАЖНО: Создай ТОЛЬКО ОДНОГО персонажа!
        ВАЖНО: Ответ должен содержать только JSON, без лишнего текста!"""
    
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Создай персонажа по запросу: {req.prompt}"}
            ],
            temperature=0.9,
            max_tokens=4096
        )
        result = response.choices[0].message.content
        
        # Пробуем найти JSON в ответе
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            try:
                char_data = json.loads(json_match.group())
            except json.JSONDecodeError:
                lines = [line.strip() for line in result.split('\n') if line.strip()]
                char_data = {
                    "name": lines[0][:50] if lines else "Сгенерированный персонаж",
                    "role": "Не указана",
                    "description": result[:300],
                    "personality": "Не указан",
                    "backstory": "Не указана",
                    "appearance": "Не указана",
                    "greeting": "Привет! Я новый персонаж."
                }
        else:
            lines = [line.strip() for line in result.split('\n') if line.strip()]
            char_data = {
                "name": lines[0][:50] if lines else "Сгенерированный персонаж",
                "role": "Не указана",
                "description": result[:300],
                "personality": "Не указан",
                "backstory": "Не указана",
                "appearance": "Не указана",
                "greeting": "Привет! Я новый персонаж."
            }
        
        # Сохраняем персонажа в БД
        with SessionLocal() as db:
            new_char = Character(
                user_id=user.id,
                name=char_data.get('name', 'Без имени'),
                role=char_data.get('role', ''),
                description=char_data.get('description', ''),
                personality=char_data.get('personality', ''),
                backstory=char_data.get('backstory', ''),
                appearance=char_data.get('appearance', ''),
                greeting=char_data.get('greeting', 'Привет!'),
                world_id=req.world_id if hasattr(req, 'world_id') else None
            )
            db.add(new_char)
            db.commit()
            db.refresh(new_char)
            return {"success": True, "id": new_char.id, "name": new_char.name}
            
    except Exception as e:
        return JSONResponse({"error": f"Ошибка генерации: {str(e)}"}, 500)
        
# --- МИРЫ ---

@app.get("/api/worlds")
async def get_worlds(token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        worlds = db.query(World).filter(World.created_by == user.id).all()
        return [{
            "id": w.id, "name": w.name, "description": w.description,
            "genre": w.genre, "setting": w.setting, "rules": w.rules,
            "is_public": w.is_public, "avatar": w.avatar
        } for w in worlds]

@app.post("/api/worlds")
async def create_world(world: WorldCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        new_world = World(
            name=world.name,
            description=world.description,
            genre=world.genre,
            setting=world.setting,
            rules=world.rules,
            avatar=world.avatar,
            is_public=world.is_public if world.is_public is not None else False,
            created_by=user.id
        )
        db.add(new_world)
        db.commit()
        db.refresh(new_world)
        return {"id": new_world.id, "name": new_world.name, "success": True}

@app.put("/api/worlds/{world_id}")
async def update_world(world_id: int, world: WorldCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        existing = db.query(World).filter(World.id == world_id, World.created_by == user.id).first()
        if not existing:
            return JSONResponse({"error": "Мир не найден или не принадлежит вам"}, 404)
        
        existing.name = world.name
        existing.description = world.description
        existing.genre = world.genre
        existing.setting = world.setting
        existing.rules = world.rules
        existing.avatar = world.avatar
        existing.is_public = world.is_public
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "name": existing.name, "success": True}

@app.get("/api/worlds/{world_id}")
async def get_world(world_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        world = db.query(World).filter(World.id == world_id, World.created_by == user.id).first()
        if not world:
            return JSONResponse({"error": "Мир не найден"}, 404)
        return {
            "id": world.id,
            "name": world.name,
            "description": world.description,
            "genre": world.genre,
            "setting": world.setting,
            "rules": world.rules,
            "avatar": world.avatar,
            "is_public": world.is_public
        }

@app.delete("/api/worlds/{world_id}")
async def delete_world(world_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        world = db.query(World).filter(World.id == world_id, World.created_by == user.id).first()
        if not world:
            raise HTTPException(404, "Мир не найден")
        db.delete(world)
        db.commit()
        return {"success": True}

@app.get("/api/worlds/public")
async def get_public_worlds(limit: int = 20, offset: int = 0, search: str = ""):
    with SessionLocal() as db:
        query = db.query(World).filter(World.is_public == True)
        if search:
            query = query.filter(World.name.contains(search))
        total = query.count()
        worlds = query.offset(offset).limit(limit).all()
        return {
            "items": [{"id": w.id, "name": w.name, "description": w.description, "avatar": w.avatar, "created_by": w.created_by} for w in worlds],
            "total": total,
            "limit": limit,
            "offset": offset
        }

# --- ПЕРСОНЫ ---

@app.get("/api/personas")
async def get_personas(token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        try:
            personas = db.query(Persona).filter(Persona.user_id == user.id).all()
            return [{
                "id": p.id,
                "name": p.name,
                "age": p.age,
                "appearance": p.appearance,
                "personality": p.personality,
                "backstory": p.backstory,
                "skills": p.skills,
                "goal": p.goal,
                "avatar": p.avatar,
                "is_active": p.is_active,
                "world_id": p.world_id
            } for p in personas]
        except Exception as e:
            print(f"❌ Ошибка в /api/personas: {str(e)}")
            return JSONResponse({"error": str(e)}, 500)

@app.post("/api/personas")
async def create_persona(persona: PersonaCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        new_persona = Persona(**persona.dict(), user_id=user.id)
        db.add(new_persona)
        db.commit()
        db.refresh(new_persona)
        if not user.active_persona_id:
            user.active_persona_id = new_persona.id
            db.commit()
        return {"id": new_persona.id, "name": new_persona.name, "success": True}

@app.put("/api/personas/{persona_id}")
async def update_persona(persona_id: int, persona: PersonaCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        existing = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
        if not existing:
            return JSONResponse({"error": "Персона не найдена или не принадлежит вам"}, 404)
        
        for key, value in persona.dict().items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return {"id": existing.id, "name": existing.name, "success": True}

@app.get("/api/personas/{persona_id}")
async def get_persona(persona_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
        if not persona:
            return JSONResponse({"error": "Персона не найдена"}, 404)
        return {
            "id": persona.id,
            "name": persona.name,
            "age": persona.age,
            "appearance": persona.appearance,
            "personality": persona.personality,
            "backstory": persona.backstory,
            "skills": persona.skills,
            "goal": persona.goal,
            "avatar": persona.avatar,
            "is_active": persona.is_active,
            "world_id": persona.world_id
        }

@app.post("/api/personas/{persona_id}/activate")
async def activate_persona(persona_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
        if not persona:
            raise HTTPException(404, "Персона не найдена")
        user.active_persona_id = persona_id
        db.commit()
        return {"success": True}

@app.delete("/api/personas/{persona_id}")
async def delete_persona(persona_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        persona = db.query(Persona).filter(Persona.id == persona_id, Persona.user_id == user.id).first()
        if not persona:
            raise HTTPException(404, "Персона не найдена")
        db.delete(persona)
        db.commit()
        return {"success": True}

# --- ПАМЯТЬ ---

@app.get("/api/memory")
async def get_memory(token: str, character_id: Optional[int] = None):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        query = db.query(Memory).filter(Memory.user_id == user.id)
        if character_id:
            query = query.filter(Memory.character_id == character_id)
        memories = query.order_by(Memory.importance.desc()).all()
        return [{
            "id": m.id, "content": m.content,
            "importance": m.importance, "memory_type": m.memory_type,
            "is_auto": m.is_auto
        } for m in memories]

@app.post("/api/memory")
async def create_memory(memory: MemoryCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        if not user.active_persona_id:
            return JSONResponse({"error": "Нет активной персоны"}, 400)
        new_memory = Memory(**memory.dict(), user_id=user.id, persona_id=user.active_persona_id)
        db.add(new_memory)
        db.commit()
        db.refresh(new_memory)
        return {"id": new_memory.id, "content": new_memory.content, "success": True}

@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        memory = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id).first()
        if not memory:
            raise HTTPException(404, "Воспоминание не найдено")
        db.delete(memory)
        db.commit()
        return {"success": True}

# --- ЛОРБУК ---

@app.get("/api/lore")
async def get_lore(token: str, search: Optional[str] = None):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        query = db.query(LoreEntry).filter(LoreEntry.user_id == user.id)
        if search:
            query = query.filter(
                (LoreEntry.title.contains(search)) |
                (LoreEntry.content.contains(search))
            )
        lore = query.order_by(LoreEntry.created_at.desc()).all()
        return [{
            "id": l.id, "title": l.title, "content": l.content,
            "category": l.category, "tags": l.tags,
            "character_id": l.character_id, "world_id": l.world_id, "room_id": l.room_id
        } for l in lore]

@app.post("/api/lore")
async def create_lore(lore: LoreCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        new_lore = LoreEntry(**lore.dict(), user_id=user.id)
        db.add(new_lore)
        db.commit()
        db.refresh(new_lore)
        return {"id": new_lore.id, "title": new_lore.title, "success": True}

@app.put("/api/lore/{lore_id}")
async def update_lore(lore_id: int, lore: LoreCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        existing = db.query(LoreEntry).filter(LoreEntry.id == lore_id, LoreEntry.user_id == user.id).first()
        if not existing:
            return JSONResponse({"error": "Запись не найдена"}, 404)
        
        for key, value in lore.dict().items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return {"success": True}

@app.delete("/api/lore/{lore_id}")
async def delete_lore(lore_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        lore = db.query(LoreEntry).filter(LoreEntry.id == lore_id, LoreEntry.user_id == user.id).first()
        if not lore:
            raise HTTPException(404, "Запись не найдена")
        db.delete(lore)
        db.commit()
        return {"success": True}

# --- КОМНАТЫ ---

@app.get("/api/rooms")
async def get_rooms(token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        rooms = db.query(Room).filter(Room.owner_id == user.id).all()
        return [{
            "id": r.id, "name": r.name, "description": r.description,
            "world_id": r.world_id, "lorebook_id": r.lorebook_id,
            "members": r.members or []
        } for r in rooms]

@app.post("/api/rooms")
async def create_room(room: RoomCreate, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        new_room = Room(**room.dict(), owner_id=user.id, members=[user.id])
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        return {"id": new_room.id, "name": new_room.name, "success": True}

@app.delete("/api/rooms/{room_id}")
async def delete_room(room_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        room = db.query(Room).filter(Room.id == room_id, Room.owner_id == user.id).first()
        if not room:
            raise HTTPException(404, "Комната не найдена")
        db.delete(room)
        db.commit()
        return {"success": True}

@app.post("/api/rooms/{room_id}/members")
async def add_room_member(room_id: int, member_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        room = db.query(Room).filter(Room.id == room_id, Room.owner_id == user.id).first()
        if not room:
            raise HTTPException(404, "Комната не найдена")
        members = room.members or []
        if member_id not in members:
            members.append(member_id)
            room.members = members
            db.commit()
        return {"success": True}

@app.delete("/api/rooms/{room_id}/members/{member_id}")
async def remove_room_member(room_id: int, member_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        room = db.query(Room).filter(Room.id == room_id, Room.owner_id == user.id).first()
        if not room:
            raise HTTPException(404, "Комната не найдена")
        members = room.members or []
        if member_id in members:
            members.remove(member_id)
            room.members = members
            db.commit()
        return {"success": True}

# --- API КЛЮЧИ ---

@app.get("/api/keys")
async def get_api_keys(token: str):
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Не авторизован")
    return {"keys": user.api_keys or {}}

@app.put("/api/keys")
async def update_api_keys(keys_data: ApiKeysUpdate, token: str):
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    with SessionLocal() as db:
        db_user = db.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(404, "Пользователь не найден")
        db_user.api_keys = keys_data.keys
        db.commit()
        return {"success": True}

# --- ПРОФИЛЬ ---

@app.get("/api/profile")
async def get_profile(token: str):
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    return {
        "username": user.username,
        "display_name": user.display_name or user.username,
        "avatar": user.avatar,
        "bio": user.bio or ""
    }

@app.put("/api/profile")
async def update_profile(
    token: str,
    display_name: Optional[str] = None,
    bio: Optional[str] = None,
    avatar: Optional[str] = None
):
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    with SessionLocal() as db:
        db_user = db.query(User).filter(User.id == user.id).first()
        if not db_user:
            raise HTTPException(404, "Пользователь не найден")
        if display_name is not None:
            db_user.display_name = display_name
        if bio is not None:
            db_user.bio = bio
        if avatar is not None:
            db_user.avatar = avatar
        db.commit()
        return {"success": True}

# --- ЧАТ (FIXED) ---

@app.post("/api/chat")
async def chat(chat_req: ChatRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        character = db.query(Character).filter(Character.id == chat_req.character_id).first()
        if not character or (character.user_id != user.id and not character.is_public):
            return JSONResponse({"error": "Персонаж не доступен"}, 404)

        character_id = character.id
        character_name = character.name
        character_role = character.role
        character_personality = character.personality
        character_backstory = character.backstory
        character_description = character.description
        character_appearance = character.appearance
        character_greeting = character.greeting

        temperature = chat_req.temperature if hasattr(chat_req, 'temperature') else 0.8
        mode = chat_req.mode if hasattr(chat_req, 'mode') else 'all'

        mode_prompts = {
            'friendship': 'Ты дружелюбный компаньон. Никаких романтических или сексуальных намёков. Просто дружба и поддержка.',
            'flirt': 'Ты слегка флиртуешь, делаешь комплименты, но не навязчиво. Игривый и лёгкий тон.',
            'romance': 'Ты романтичный и нежный. Делаешь красивые комплименты, ухаживаешь, создаёшь атмосферу.',
            'love': 'Ты открыто выражаешь желание, подкатываешь. Допустимы откровенные и страстные сцены. 18+',
            'all': 'Ты сам подстраиваешься под ситуацию. Можешь быть и другом, и романтиком, и страстным -в зависимости от контекста.'
        }

        persona = None
        persona_name = None
        persona_personality = None
        persona_appearance = None
        persona_id = None

        if chat_req.persona_id:
            persona = db.query(Persona).filter(Persona.id == chat_req.persona_id).first()
        elif user.active_persona_id:
            persona = db.query(Persona).filter(Persona.id == user.active_persona_id).first()

        if persona:
            persona_name = persona.name
            persona_personality = persona.personality
            persona_appearance = persona.appearance
            persona_id = persona.id

        # ========== ИЕРАРХИЧЕСКАЯ ПАМЯТЬ ==========
        memories = get_relevant_memory(user.id, character_id=character.id, limit=10)
        memory_text = ""
        if memories:
            memory_text = "\n\nВажные воспоминания:\n"
            for m in memories:
                memory_text += f"[{m['type'].upper()}] {m['content']}\n"
        # ==========================================

        # ========== ЛИЧНАЯ ПАМЯТЬ (ФАКТЫ О ПОЛЬЗОВАТЕЛЕ) ==========
        user_facts = load_user_memories(user.id)
        if user_facts:
            user_facts_text = "\n\nФакты о собеседнике:\n"
            for fact in user_facts:
                user_facts_text += f"- {fact}\n"
        else:
            user_facts_text = ""
        # ===========================================================

        system_prompt = f"Ты - {character_name}."
        if character_role: system_prompt += f"\nРоль: {character_role}"
        if character_personality: system_prompt += f"\nХарактер: {character_personality}"
        if character_backstory: system_prompt += f"\nПредыстория: {character_backstory}"
        if character_description: system_prompt += f"\nОписание: {character_description}"
        if character_appearance: system_prompt += f"\nВнешность: {character_appearance}"

        if mode in mode_prompts:
            system_prompt += f"\n\nРежим общения: {mode_prompts[mode]}"

        if persona:
            system_prompt += f"\n\nТы общаешься с {persona_name}."
            if persona_personality: system_prompt += f"\nХарактер собеседника: {persona_personality}"
            if persona_appearance: system_prompt += f"\nВнешность собеседника: {persona_appearance}"

        system_prompt += memory_text
        system_prompt += user_facts_text

        # ========== ЗАГРУЗКА ИСТОРИИ ЧАТА ==========
        history = db.query(ChatHistory).filter(
            ChatHistory.character_id == character.id,
            ChatHistory.user_id == user.id,
            ChatHistory.user_message != "__SESSION_START__"
        ).order_by(ChatHistory.timestamp.desc()).limit(5).all()
        history.reverse()
        # ===========================================

        messages = [{"role": "system", "content": system_prompt}]

        is_first_message = len(history) == 0
        if is_first_message and character_greeting:
            messages.append({"role": "assistant", "content": character_greeting})

        for h in history:
            messages.append({"role": "user", "content": h.user_message})
            messages.append({"role": "assistant", "content": h.bot_response})
        messages.append({"role": "user", "content": chat_req.message})

        # ========== АВТО-СУММАРИЗАЦИЯ ==========
        if len(messages) > 50:
            summary = summarize_chat_history(messages)
            if summary:
                with SessionLocal() as db_summary:
                    memory = Memory(
                        content=f"Сюжетная память: {summary}",
                        memory_type="story",
                        importance=2.0,
                        is_auto=True,
                        user_id=user.id,
                        character_id=character.id,
                        persona_id=persona_id
                    )
                    db_summary.add(memory)
                    db_summary.commit()
        # =======================================

        api_keys = user.api_keys or {}
        api_key = api_keys.get("polza") or POLZA_API_KEY
        model = api_keys.get("model") or POLZA_MODEL
        
        if not api_key or api_key == "your-default-api-key-here":
            return JSONResponse({
                "error": "API ключ не настроен. Добавьте ключ Polza в настройках профиля."
            }, 400)

        openai.api_key = api_key
        openai.base_url = "https://polza.ai/api/v1/"

        max_tokens = 1500
        if hasattr(chat_req, 'max_tokens'):
            max_tokens = chat_req.max_tokens

        try:
            response = openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            bot_response = response.choices[0].message.content
        except Exception as e:
            bot_response = f"Ошибка AI: {str(e)}"

        chat_entry = ChatHistory(
            user_id=user.id,
            character_id=character.id,
            persona_id=persona_id,
            user_message=chat_req.message,
            bot_response=bot_response
        )
        db.add(chat_entry)
        db.commit()
        db.refresh(chat_entry)

        # ========== СОХРАНЯЕМ ФАКТЫ О ПОЛЬЗОВАТЕЛЕ ==========
        if len(chat_req.message) > 20:
            save_user_fact(user.id, chat_req.message[:200], "chat")
        # ====================================================

        if len(chat_req.message) > 40:
            memory = Memory(
                content=f"Важный момент: {chat_req.message[:200]}...",
                importance=0.7,
                memory_type="auto",
                is_auto=True,
                persona_id=persona_id,
                character_id=character.id,
                user_id=user.id,
                chat_id=chat_entry.id
            )
            db.add(memory)
            db.commit()
            
                    # ========== СОХРАНЯЕМ В ИЕРАРХИЧЕСКУЮ ПАМЯТЬ ==========
        save_hierarchical_memory(
            user_id=user.id,
            content=chat_req.message,
            memory_type="short",
            importance=1.0,
            category="fact",
            character_id=character.id
        )
        # =======================================================

        return {"response": bot_response, "character_id": character_id, "character_name": character_name}

# --- РЕГЕНЕРАЦИЯ ОТВЕТА (FIXED) ---

@app.post("/api/chat/regenerate")
async def regenerate(req: RegenerateRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        character = db.query(Character).filter(Character.id == req.character_id).first()
        if not character or (character.user_id != user.id and not character.is_public):
            return JSONResponse({"error": "Персонаж не доступен"}, 404)

        # Получаем последний диалог для контекста
        history = db.query(ChatHistory).filter(
            ChatHistory.character_id == req.character_id,
            ChatHistory.user_id == user.id,
            ChatHistory.user_message != "__SESSION_START__"
        ).order_by(ChatHistory.timestamp.desc()).limit(10).all()
        history.reverse()

        # Собираем системный промпт
        system_prompt = f"Ты - {character.name}."
        if character.role: system_prompt += f"\nРоль: {character.role}"
        if character.personality: system_prompt += f"\nХарактер: {character.personality}"
        if character.backstory: system_prompt += f"\nПредыстория: {character.backstory}"
        if character.description: system_prompt += f"\nОписание: {character.description}"
        if character.appearance: system_prompt += f"\nВнешность: {character.appearance}"

        mode_prompts = {
            'friendship': 'Ты дружелюбный компаньон. Никаких романтических или сексуальных намёков. Просто дружба и поддержка.',
            'flirt': 'Ты слегка флиртуешь, делаешь комплименты, но не навязчиво. Игривый и лёгкий тон.',
            'romance': 'Ты романтичный и нежный. Делаешь красивые комплименты, ухаживаешь, создаёшь атмосферу.',
            'love': 'Ты открыто выражаешь желание, подкатываешь. Допустимы откровенные и страстные сцены. 18+',
            'all': 'Ты сам подстраиваешься под ситуацию. Можешь быть и другом, и романтиком, и страстным -в зависимости от контекста.'
        }

        if req.mode in mode_prompts:
            system_prompt += f"\n\nРежим общения: {mode_prompts[req.mode]}"

        # Персона
        if req.persona_id:
            persona = db.query(Persona).filter(Persona.id == req.persona_id).first()
            if persona:
                system_prompt += f"\n\nТы общаешься с {persona.name}."
                if persona.personality: system_prompt += f"\nХарактер собеседника: {persona.personality}"
                if persona.appearance: system_prompt += f"\nВнешность собеседника: {persona.appearance}"

        # Память
        memories = db.query(Memory).filter(
            Memory.character_id == req.character_id,
            Memory.user_id == user.id
        ).order_by(Memory.importance.desc()).limit(5).all()

        if memories:
            system_prompt += "\n\nВот что ты помнишь:"
            for m in memories:
                system_prompt += f"\n- {m.content}"

        # Собираем сообщения
        messages = [{"role": "system", "content": system_prompt}]

        for h in history:
            messages.append({"role": "user", "content": h.user_message})
            messages.append({"role": "assistant", "content": h.bot_response})

        messages.append({"role": "user", "content": req.user_message})

        api_keys = user.api_keys or {}
        api_key = api_keys.get("polza") or POLZA_API_KEY
        model = api_keys.get("model") or POLZA_MODEL
        
        if not api_key or api_key == "your-default-api-key-here":
            return JSONResponse({
                "error": "API ключ не настроен. Добавьте ключ Polza в настройках профиля."
            }, 400)

        openai.api_key = api_key
        openai.base_url = "https://polza.ai/api/v1/"

        try:
            response = openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens
            )
            bot_response = response.choices[0].message.content

            # Обновляем последнее сообщение бота в базе
            last_entry = db.query(ChatHistory).filter(
                ChatHistory.character_id == req.character_id,
                ChatHistory.user_id == user.id,
                ChatHistory.user_message == req.user_message
            ).order_by(ChatHistory.timestamp.desc()).first()

            if last_entry:
                last_entry.bot_response = bot_response
                last_entry.timestamp = datetime.utcnow()
                db.commit()

            return {"response": bot_response, "success": True}

        except Exception as e:
            return JSONResponse({"error": f"Ошибка генерации: {str(e)}"}, 500)

# --- ИСТОРИЯ ЧАТА ---

@app.get("/api/chat/history")
async def get_chat_history(token: str, character_id: int, limit: int = 50):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        character = db.query(Character).filter(Character.id == character_id).first()
        if not character or (character.user_id != user.id and not character.is_public):
            return JSONResponse({"error": "Персонаж не доступен"}, 404)

        history = db.query(ChatHistory).filter(
            ChatHistory.character_id == character_id,
            ChatHistory.user_id == user.id,
            ChatHistory.user_message != "__SESSION_START__"
        ).order_by(ChatHistory.timestamp.asc()).limit(limit).all()
        
        result = []
        for h in history:
            result.append({"role": "user", "content": h.user_message})
            result.append({"role": "assistant", "content": h.bot_response})
        return result

# --- РЕДАКТИРОВАНИЕ СООБЩЕНИЯ ---

@app.put("/api/chat/message")
async def edit_message(req: EditMessageRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        chat_entry = db.query(ChatHistory).filter(
            ChatHistory.id == req.message_id,
            ChatHistory.user_id == user.id
        ).first()

        if not chat_entry:
            return JSONResponse({"error": "Сообщение не найдено"}, 404)

        if req.is_bot:
            old_content = chat_entry.bot_response
            chat_entry.bot_response = req.new_content
        else:
            old_content = chat_entry.user_message
            chat_entry.user_message = req.new_content

        chat_entry.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(chat_entry)

        return {
            "success": True,
            "message_id": req.message_id,
            "new_content": req.new_content,
            "old_content": old_content
        }

# --- ОЧИСТКА ЧАТА ---

@app.post("/api/chat/{character_id}/clear")
async def clear_chat(character_id: int, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        character = db.query(Character).filter(Character.id == character_id).first()
        if not character or (character.user_id != user.id and not character.is_public):
            return JSONResponse({"error": "Персонаж не доступен"}, 404)

        new_session_marker = ChatHistory(
            user_id=user.id,
            character_id=character_id,
            user_message="__SESSION_START__",
            bot_response="__SESSION_START__",
            timestamp=datetime.utcnow()
        )
        db.add(new_session_marker)
        db.commit()
        db.refresh(new_session_marker)

        return {
            "success": True,
            "message": "Чат очищен",
            "session_id": new_session_marker.id
        }

# --- СПИСОК ЧАТОВ (СЕССИЙ) ---

@app.get("/api/chat/sessions")
async def get_chat_sessions(token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    with SessionLocal() as db:
        # Получаем все уникальные чаты пользователя
        sessions = db.query(
            ChatHistory.character_id,
            func.max(ChatHistory.timestamp).label('last_time'),
            func.count(ChatHistory.id).label('message_count')
        ).filter(
            ChatHistory.user_id == user.id,
            ChatHistory.user_message != "__SESSION_START__"
        ).group_by(
            ChatHistory.character_id
        ).order_by(
            func.max(ChatHistory.timestamp).desc()
        ).all()
        
        result = []
        for session in sessions:
            character = db.query(Character).filter(
                Character.id == session.character_id
            ).first()
            
            if character:
                # Получаем последнее сообщение
                last_msg = db.query(ChatHistory).filter(
                    ChatHistory.character_id == session.character_id,
                    ChatHistory.user_id == user.id,
                    ChatHistory.user_message != "__SESSION_START__"
                ).order_by(
                    ChatHistory.timestamp.desc()
                ).first()
                
                result.append({
                    "character_id": character.id,
                    "character_name": character.name,
                    "avatar": character.avatar,
                    "last_message": last_msg.user_message if last_msg else "",
                    "last_message_time": session.last_time.strftime("%Y-%m-%d %H:%M") if session.last_time else "",
                    "message_count": session.message_count
                })
        
        return result

# --- ГЕНЕРАЦИЯ ПЕРСОНАЖА ЧЕРЕЗ ИИ (FIXED) ---

@app.post("/api/generate/world")
async def generate_world(req: GenerateRequest, token: str):
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    api_keys = user.api_keys or {}
    api_key = api_keys.get("polza") or POLZA_API_KEY
    model = api_keys.get("model") or POLZA_MODEL
    
    if not api_key or api_key == "your-default-api-key-here":
        return JSONResponse({
            "error": "API ключ не настроен. Добавьте ключ Polza в настройках профиля."
        }, 400)
    
    openai.api_key = api_key
    openai.base_url = "https://polza.ai/api/v1/"
    
    # Определяем, короткий это запрос или длинный
    is_short = len(req.prompt.split()) < 10
    
    if is_short:
        system_prompt = """Ты — помощник по созданию миров для ролевых игр.
        Пользователь дал КОРОТКИЙ запрос. Твоя задача:
        1. Распознать жанр и сеттинг
        2. Додумать недостающие детали (история, правила, атмосфера)
        3. Сделать мир ЖИВЫМ и ИНТЕРЕСНЫМ
        
        Сгенерируй мир в формате JSON с полями:
        name, description, genre, setting, rules.
        
        Заполни ВСЕ поля качественно и подробно!
        description - минимум 2-3 предложения.
        setting - минимум 2-3 предложения.
        rules - минимум 3-5 правил мира.
        
        ВАЖНО: Создай ТОЛЬКО ОДИН мир!
        ВАЖНО: Ответ должен содержать только JSON, без лишнего текста!"""
    else:
        system_prompt = """Ты — помощник по созданию миров для ролевых игр.
        Пользователь дал ПОДРОБНЫЙ запрос. Твоя задача:
        1. Точно следовать всем указаниям пользователя
        2. Не добавлять ничего от себя
        3. Сохранить все детали из запроса
        
        Сгенерируй мир в формате JSON с полями:
        name, description, genre, setting, rules.
        
        Заполни ВСЕ поля качественно и подробно!
        description - минимум 2-3 предложения.
        setting - минимум 2-3 предложения.
        rules - минимум 3-5 правил мира.
        
        ВАЖНО: Создай ТОЛЬКО ОДИН мир!
        ВАЖНО: Ответ должен содержать только JSON, без лишнего текста!"""
    
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Создай мир по запросу: {req.prompt}"}
            ],
            temperature=0.9,
            max_tokens=1500
        )
        result = response.choices[0].message.content
        
        # Пробуем найти JSON в ответе
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            try:
                world_data = json.loads(json_match.group())
            except json.JSONDecodeError:
                # Если JSON невалидный, создаем мир из текста
                lines = [line.strip() for line in result.split('\n') if line.strip()]
                world_data = {
                    "name": lines[0][:50] if lines else "Сгенерированный мир",
                    "description": result[:300],
                    "genre": "Не указан",
                    "setting": result[:200],
                    "rules": "Правила не указаны"
                }
        else:
            # Если JSON не найден, создаем мир из текста
            lines = [line.strip() for line in result.split('\n') if line.strip()]
            world_data = {
                "name": lines[0][:50] if lines else "Сгенерированный мир",
                "description": result[:300],
                "genre": "Не указан",
                "setting": result[:200],
                "rules": "Правила не указаны"
            }
        
        # Сохраняем мир в БД
        with SessionLocal() as db:
            new_world = World(
                created_by=user.id,
                name=world_data.get('name', 'Без названия'),
                description=world_data.get('description', ''),
                genre=world_data.get('genre', ''),
                setting=world_data.get('setting', ''),
                rules=world_data.get('rules', '')
            )
            db.add(new_world)
            db.commit()
            db.refresh(new_world)
            return {"success": True, "id": new_world.id, "name": new_world.name}
            
    except Exception as e:
        return JSONResponse({"error": f"Ошибка генерации: {str(e)}"}, 500)

# ============================================
# HTML ФРОНТЕНД (полный, без изменений)
# ============================================

HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>H.Y.G. - Heartfelt, Yet Goofy</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: #010405;
            color: #ffffff;
            min-height: 100%;
        }
        .cover {
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: #0a0a0a;
            background-image: radial-gradient(ellipse at center, #1a2a1a 0%, #000000 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            z-index: 9999;
            cursor: pointer;
            transition: opacity 800ms ease, visibility 800ms ease;
        }
        .cover.hidden {
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }
        .cover .sub {
            font-size: 22px;
            color: #aaaaaa;
            letter-spacing: 4px;
            margin-bottom: 6px;
        }
        .cover h1 {
            font-size: 72px;
            font-weight: 800;
            background: linear-gradient(135deg, #304c2f, #043267, #304c2f);
            background-size: 300% 300%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradShift 6s ease-in-out infinite;
            margin-bottom: 10px;
        }
        @keyframes gradShift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }
        .cover .descr {
            font-size: 16px;
            color: #666666;
            font-style: italic;
        }
        .cover .arrow {
            margin-top: 40px;
            font-size: 28px;
            color: #666;
            animation: bounce 2s infinite;
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(10px); }
        }
        .hamburger-btn {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 200;
            background: rgba(1, 4, 5, 0.9);
            border: 1px solid rgba(48, 76, 47, 0.3);
            border-radius: 10px;
            padding: 12px 14px;
            cursor: pointer;
            transition: 0.3s;
            display: none;
        }
        .hamburger-btn:hover {
            border-color: #304c2f;
            background: rgba(48, 76, 47, 0.15);
        }
        .hamburger-btn span {
            display: block;
            width: 24px;
            height: 2px;
            background: #ffffff;
            margin: 4px 0;
            transition: 0.3s;
        }
        .hamburger-btn.active span:nth-child(1) {
            transform: rotate(45deg) translate(4px, 4px);
        }
        .hamburger-btn.active span:nth-child(2) {
            opacity: 0;
        }
        .hamburger-btn.active span:nth-child(3) {
            transform: rotate(-45deg) translate(4px, -4px);
        }
        
        .sidebar {
    position: fixed;
    top: 0;
    left: -280px;
    width: 280px;
    height: 100%;
    background: #010405;
    border-right: 1px solid rgba(48, 76, 47, 0.3);
    padding: 30px 20px;
    z-index: 150;
    transition: left 0.3s ease;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
}
.sidebar.open {
    left: 0;
}
        .sidebar .logo {
            font-size: 24px;
            font-weight: 800;
            letter-spacing: 2px;
            padding-bottom: 25px;
            border-bottom: 1px solid rgba(48, 76, 47, 0.2);
            margin-bottom: 20px;
            color: #ffffff;
        }
        .sidebar .logo span { color: #304c2f; }
        .sidebar .menu { flex: 1; }
        .sidebar .menu .menu-label {
            font-size: 11px;
            text-transform: uppercase;
            color: #555;
            letter-spacing: 1px;
            padding: 12px 16px 6px;
        }
        .sidebar .menu a {
            display: block;
            padding: 10px 16px;
            color: #cccccc;
            text-decoration: none;
            border-radius: 8px;
            font-size: 15px;
            transition: 0.3s;
            cursor: pointer;
            margin: 1px 0;
        }
        .sidebar .menu a:hover {
            background: rgba(48, 76, 47, 0.12);
            color: #ffffff;
        }
        .sidebar .menu a.active {
            background: rgba(48, 76, 47, 0.2);
            color: #304c2f;
        }
        .sidebar .menu a .icon {
            margin-right: 10px;
            opacity: 0.6;
        }
        .sidebar .user-info {
            padding: 12px 16px;
            color: #888;
            font-size: 14px;
            border-top: 1px solid rgba(48, 76, 47, 0.2);
            margin-top: 10px;
        }
        .sidebar .auth-btn {
            padding: 12px 16px;
            background: linear-gradient(45deg, #304c2f, #043267);
            border: none;
            border-radius: 25px;
            color: #fff;
            font-size: 15px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
            text-align: center;
            margin-top: 8px;
        }
        .sidebar .auth-btn:hover { transform: scale(1.02); opacity: 0.9; }
        .main {
            margin-left: 0;
            padding: 30px 40px 40px;
            min-height: 100%;
            transition: margin-left 0.3s ease;
        }
        .main.shifted {
            margin-left: 280px;
        }
        .page { display: none; }
        .page.active { display: block; }
        .page-title {
            font-size: 30px;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .page-desc {
            color: #888;
            margin-bottom: 25px;
            font-size: 15px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }
        .card {
            background: rgba(48, 76, 47, 0.06);
            border: 1px solid rgba(48, 76, 47, 0.12);
            border-radius: 14px;
            padding: 18px 16px 16px;
            text-align: center;
            transition: 0.3s;
            cursor: default;
        }
        .card:hover {
            transform: translateY(-4px);
            border-color: #304c2f;
            background: rgba(48, 76, 47, 0.12);
        }
        .card .avatar {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            object-fit: cover;
            margin: 0 auto 10px;
            background: rgba(255,255,255,0.05);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            color: #555;
        }
        .card .avatar img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }
        .card .name {
            font-size: 17px;
            font-weight: 600;
        }
        .card .role {
            font-size: 13px;
            color: #888;
            margin-top: 3px;
        }
        .card .actions {
            margin-top: 12px;
            display: flex;
            gap: 6px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .card .actions button {
            padding: 5px 14px;
            background: rgba(48, 76, 47, 0.25);
            border: none;
            border-radius: 16px;
            color: #ddd;
            font-size: 12px;
            cursor: pointer;
            transition: 0.3s;
        }
        .card .actions button:hover {
            background: rgba(48, 76, 47, 0.4);
            color: #fff;
        }
        .card .actions .danger:hover {
            background: rgba(180, 40, 40, 0.35);
        }
        .form-box {
            max-width: 440px;
            margin: 30px auto;
            background: rgba(255,255,255,0.02);
            padding: 35px 40px 40px;
            border-radius: 18px;
            border: 1px solid rgba(48, 76, 47, 0.15);
        }
        .form-box h2 {
            text-align: center;
            margin-bottom: 18px;
            font-weight: 600;
            font-size: 24px;
        }
        .form-box input,
        .form-box textarea,
        .form-box select {
            width: 100%;
            padding: 13px 16px;
            margin: 8px 0;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            color: #ffffff;
            font-size: 15px;
            transition: 0.3s;
            font-family: inherit;
        }
        .form-box input:focus,
        .form-box textarea:focus,
        .form-box select:focus {
            border-color: #304c2f;
            outline: none;
            background: rgba(255,255,255,0.06);
        }
        .form-box textarea {
            min-height: 90px;
            resize: vertical;
        }
        .form-box select option {
            background: #1a1a1a;
        }
        .form-box .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(45deg, #304c2f, #043267);
            border: none;
            border-radius: 25px;
            color: #fff;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
            margin-top: 12px;
        }
        .form-box .btn:hover { transform: scale(1.01); opacity: 0.92; }
        .form-box .link {
            text-align: center;
            margin-top: 14px;
            color: #888;
            font-size: 14px;
        }
        .form-box .link a {
            color: #304c2f;
            text-decoration: none;
            cursor: pointer;
        }
        .form-box .link a:hover { text-decoration: underline; }
        .form-box .checkbox-label {
            color: #aaa;
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 8px 0;
            font-size: 14px;
        }
        .form-box .checkbox-label input {
            width: auto;
            margin: 0;
        }
        .form-box .file-label {
            display: block;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            border: 1px dashed rgba(255,255,255,0.1);
            border-radius: 10px;
            text-align: center;
            color: #888;
            cursor: pointer;
            transition: 0.3s;
            margin: 8px 0;
            font-size: 14px;
        }
        .form-box .file-label:hover {
            border-color: #304c2f;
            background: rgba(48, 76, 47, 0.05);
        }
        .form-box .file-label input {
            display: none;
        }
        .btn-primary {
            padding: 10px 28px;
            background: linear-gradient(45deg, #304c2f, #043267);
            border: none;
            border-radius: 25px;
            color: #fff;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
        }
        .btn-primary:hover { transform: scale(1.03); opacity: 0.9; }
        .flex-between {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        .chat-container {
            background: rgba(255,255,255,0.02);
            border-radius: 14px;
            padding: 20px;
            border: 1px solid rgba(48,76,47,0.1);
            display: flex;
            flex-direction: column;
            height: calc(100% - 280px);
            min-height: 400px;
        }
        .chat-messages {
            flex: 1;
            min-height: 0;
            overflow-y: auto;
            margin-bottom: 14px;
            padding-right: 4px;
        }
        .chat-messages .msg {
            margin: 6px 0;
            padding: 10px 16px;
            border-radius: 12px;
            max-width: 80%;
            font-size: 15px;
            line-height: 1.5;
        }
        .chat-messages .msg.user {
            background: rgba(4,50,103,0.2);
            margin-left: auto;
            text-align: right;
        }
        .chat-messages .msg.bot {
            background: rgba(48,76,47,0.1);
        }
        .chat-input-area {
            display: flex;
            gap: 10px;
            flex-shrink: 0;
        }
        .chat-input-area input {
            flex: 1;
            padding: 12px 16px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            color: #fff;
            font-size: 15px;
        }
        .chat-input-area input:focus {
            border-color: #304c2f;
            outline: none;
        }
        .chat-input-area .btn {
            padding: 12px 28px;
            background: linear-gradient(45deg, #304c2f, #043267);
            border: none;
            border-radius: 25px;
            color: #fff;
            font-weight: bold;
            cursor: pointer;
            transition: 0.3s;
            font-size: 14px;
        }
        .chat-input-area .btn:hover { opacity: 0.9; }
        .chat-messages::-webkit-scrollbar {
            width: 4px;
        }
        .chat-messages::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.02);
        }
        .chat-messages::-webkit-scrollbar-thumb {
            background: #304c2f;
            border-radius: 4px;
        }
        .search-input {
            width: 100%;
            padding: 12px 16px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            color: #fff;
            font-size: 15px;
            margin-bottom: 18px;
        }
        .search-input:focus {
            border-color: #304c2f;
            outline: none;
        }
        .tab-btn.active {
            color: #304c2f !important;
            background: rgba(48, 76, 47, 0.15) !important;
        }
        .tab-btn:hover {
            color: #ffffff !important;
            background: rgba(48, 76, 47, 0.08) !important;
        }
        .msg-wrapper {
            position: relative;
            display: flex;
            align-items: flex-end;
            gap: 8px;
            margin: 6px 0;
            padding: 4px 0;
            transition: 0.3s;
            width: 100%;
        }
        .msg-wrapper.user { justify-content: flex-end; }
        .msg-wrapper.bot { justify-content: flex-start; }
        .msg-content {
            padding: 10px 16px;
            border-radius: 12px;
            max-width: 80%;
            font-size: 15px;
            line-height: 1.5;
            word-wrap: break-word;
            position: relative;
            transition: 0.3s;
        }
        .msg-wrapper.user .msg-content { background: rgba(4,50,103,0.2); text-align: right; }
        .msg-wrapper.bot .msg-content { background: rgba(48,76,47,0.1); }
        .msg-actions {
            display: flex;
            gap: 4px;
            opacity: 0;
            transition: 0.3s;
            flex-shrink: 0;
            align-items: center;
        }
        .msg-wrapper:hover .msg-actions { opacity: 1; }
        .msg-actions .edit-btn {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            color: #888;
            cursor: pointer;
            font-size: 14px;
            padding: 4px 8px;
            transition: 0.3s;
            line-height: 1;
        }
        .msg-actions .edit-btn:hover {
            background: rgba(48,76,47,0.2);
            border-color: #304c2f;
            color: #fff;
        }
        .msg-actions .regenerate-btn {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            color: #888;
            cursor: pointer;
            font-size: 14px;
            padding: 4px 8px;
            transition: 0.3s;
            line-height: 1;
        }
        .msg-actions .regenerate-btn:hover {
            background: rgba(48,76,47,0.2);
            border-color: #304c2f;
            color: #fff;
        }
        .edit-input {
            flex: 1;
            padding: 8px 12px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(48,76,47,0.3);
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
            font-family: inherit;
            min-width: 200px;
            outline: none;
        }
        .edit-input:focus {
            border-color: #304c2f;
            background: rgba(255,255,255,0.08);
        }
        .edit-actions {
            display: flex;
            gap: 6px;
            flex-shrink: 0;
        }
        .edit-actions button {
            padding: 4px 12px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #888;
            cursor: pointer;
            font-size: 12px;
            transition: 0.3s;
        }
        .edit-actions .save-btn {
            background: rgba(48,76,47,0.2);
            border-color: rgba(48,76,47,0.3);
            color: #fff;
        }
        .edit-actions .save-btn:hover { background: rgba(48,76,47,0.4); }
        .edit-actions .cancel-edit-btn:hover {
            background: rgba(255,50,50,0.15);
            border-color: rgba(255,50,50,0.3);
        }
        @media (max-width: 768px) {
            .main { padding: 20px 16px 30px; }
            .main.shifted { margin-left: 0; }
            .sidebar {
                width: 260px;
                left: -260px;
            }
            .sidebar.open { left: 0; }
            .hamburger-btn { display: block; }
            .cover h1 { font-size: 36px; }
            .grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
            .form-box { padding: 24px 20px; }
        }
        @media (max-width: 450px) {
            .grid { grid-template-columns: 1fr 1fr; }
            .cover h1 { font-size: 28px; }
            .cover .sub { font-size: 16px; }
        }
        /* ===== МОБИЛЬНАЯ АДАПТАЦИЯ ===== */

/* Для экранов меньше 768px (телефоны) */
@media (max-width: 768px) {
    /* Основной контент — меньше отступы */
    .main {
        padding: 15px 12px 30px !important;
    }

    /* Заголовки — меньше */
    .page-title {
        font-size: 22px !important;
    }

    /* Карточки — в 2 колонки */
    .grid {
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 12px !important;
    }

    /* Чат — на всю ширину */
    .chat-container {
        padding: 12px !important;
        height: calc(100vh - 280px) !important;
        min-height: 350px !important;
    }

    /* Сообщения в чате — на всю ширину */
    .chat-messages .msg {
        max-width: 95% !important;
        font-size: 14px !important;
    }

    /* Поле ввода чата — удобное */
    .chat-input-area {
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
    .chat-input-area input {
        font-size: 16px !important; /* Чтобы не зумилось на iOS */
        padding: 12px !important;
        min-width: 100px !important;
        flex: 1 1 60% !important;
    }
    .chat-input-area .btn {
        padding: 12px 20px !important;
        font-size: 14px !important;
        flex: 1 1 30% !important;
    }

    /* Формы — на всю ширину */
    .form-box {
        padding: 20px 16px !important;
        margin: 10px 0 !important;
    }

    /* Кнопки в карточках — в столбик */
    .card .actions {
        flex-direction: column !important;
        gap: 4px !important;
    }
    .card .actions button {
        width: 100% !important;
        padding: 8px !important;
        font-size: 13px !important;
    }

    /* Сайдбар — уже есть, оставляем */
    .sidebar {
        width: 280px !important;
    }

    /* Настройки чата — в столбик */
    #chatSettingsPanel > div {
        grid-template-columns: 1fr !important;
    }

    /* Кнопки в настройках чата — в строку */
    #chatSettingsPanel .flex-between {
        flex-direction: column !important;
        align-items: stretch !important;
    }
    #chatSettingsPanel .flex-between > div {
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    #chatSettingsPanel .flex-between button {
        flex: 1 !important;
        min-width: 70px !important;
        font-size: 11px !important;
        padding: 4px 8px !important;
    }
}

/* Для очень маленьких экранов (меньше 450px) */
@media (max-width: 450px) {
    .grid {
        grid-template-columns: 1fr 1fr !important;
        gap: 8px !important;
    }

    .cover h1 {
        font-size: 28px !important;
    }
    .cover .sub {
        font-size: 16px !important;
    }

    .page-title {
        font-size: 18px !important;
    }

    .form-box input,
    .form-box textarea,
    .form-box select {
        font-size: 16px !important; /* Чтобы не зумилось на iOS */
        padding: 10px 12px !important;
    }

    .card {
        padding: 12px 8px !important;
    }
    .card .name {
        font-size: 14px !important;
    }
    .card .role {
        font-size: 11px !important;
    }
    .card .avatar {
        width: 48px !important;
        height: 48px !important;
        font-size: 24px !important;
    }

    /* Кнопки "Назад" в шапке */
    .flex-between .btn-primary {
        font-size: 12px !important;
        padding: 6px 14px !important;
    }

    /* Кнопка гамбургера — чуть меньше */
    .hamburger-btn {
        padding: 8px 10px !important;
        top: 12px !important;
        left: 12px !important;
    }
    .hamburger-btn span {
        width: 20px !important;
        height: 2px !important;
        margin: 3px 0 !important;
    }

    /* Чат */
    .chat-messages .msg-content {
        font-size: 14px !important;
        padding: 8px 12px !important;
        max-width: 100% !important;
    }
    .msg-actions {
        opacity: 1 !important; /* Всегда показывать кнопки на телефоне */
    }
    .msg-actions button {
        font-size: 12px !important;
        padding: 2px 6px !important;
    }

    /* Поле ввода чата */
    .chat-input-area input {
        font-size: 16px !important;
        padding: 10px 12px !important;
    }
    .chat-input-area .btn {
        font-size: 13px !important;
        padding: 10px 16px !important;
    }
}
    </style>
</head>
<body>

<!-- ===== ЗАСТАВКА ===== -->
<div class="cover" id="cover" onclick="handleCoverClick()">
    <div class="sub">H.Y.G.</div>
    <h1>Добро пожаловать в пространство</h1>
    <div class="descr">Мир, где твои истории оживают.<br>Ты уже часть корабля!</div>
    <div class="arrow">↓</div>
</div>

<!-- ===== ГАМБУРГЕР ===== -->
<div class="hamburger-btn" id="hamburgerBtn" onclick="toggleSidebar()">
    <span></span><span></span><span></span>
</div>

<!-- ===== САЙДБАР ===== -->
<div class="sidebar" id="sidebar">
    <div class="logo">H.<span>Y.</span>G.</div>
    <div class="menu">
        <div class="menu-label">Навигация</div>
        <a class="active" onclick="showPage('home')"><span class="icon">⌂</span>Главная</a>
        <a onclick="showPage('library')"><span class="icon">◈</span>Общее пространство</a>

        <div class="menu-label" style="margin-top:12px;">Личное пространство</div>
        <a onclick="showPage('chats')"><span class="icon">✉</span>Чаты</a>
        <a onclick="showPage('personas')"><span class="icon">◌</span>Персоны</a>
        <a onclick="showPage('memory')"><span class="icon">◈</span>Память</a>
        <a onclick="showPage('rooms')"><span class="icon">⌂</span>Комнаты</a>

        <div class="menu-label" style="margin-top:12px;">Создатель</div>
        <a onclick="showPage('characters')"><span class="icon">✦</span>Персонажи</a>
        <a onclick="showPage('worlds')"><span class="icon">⊙</span>Миры</a>

        <a onclick="showPage('lore')" style="margin-top:12px;"><span class="icon">◈</span>Лорбук</a>
        <a onclick="showPage('profile')"><span class="icon">⚙</span>Квартира</a>
    </div>
    
    <div class="user-info" id="userInfo">Не авторизован</div>
    
    <div style="display:flex; flex-direction:column; gap:8px; margin-top:4px;">
        <button class="auth-btn" id="authBtn" onclick="handleAuth()">Войти</button>
        <button class="auth-btn" id="logoutBtn" onclick="logout()" 
                style="display:none; background:rgba(180,40,40,0.2); border:1px solid rgba(180,40,40,0.3);">
            🚪 Выйти
        </button>
    </div>
</div>

<!-- ===== ОСНОВНОЙ КОНТЕНТ ===== -->
<div class="main" id="mainContent">

    <!-- ===== ГЛАВНАЯ ===== -->
    <div id="page-home" class="page active">
        <div style="text-align:center; padding:40px 0 20px;">
            <h1 style="font-size:44px; background:linear-gradient(45deg,#304c2f,#043267); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">H.Y.G.</h1>
            <p style="color:#aaa; font-size:18px;">Heartfelt, Yet Goofy</p>
            <p style="color:#666; font-style:italic; margin-top:4px;">С душой, но по приколу</p>
            <button class="btn-primary" onclick="showPage('library')" style="margin-top:18px;">Начать игру</button>
        </div>
        <h3 style="color:#888; font-weight:400; font-size:16px;">Популярные персонажи</h3>
        <div class="grid" id="popularGrid"></div>
    </div>

    <!-- ===== ОБЩЕЕ ПРОСТРАНСТВО ===== -->
    <div id="page-library" class="page">
        <div class="page-title">Общее пространство</div>
        <div class="page-desc">Публичные персонажи и миры других пользователей</div>

        <div style="margin-bottom:16px;">
            <input type="text" id="librarySearch" placeholder="Поиск по персонажам и мирам..."
                   style="width:100%; padding:12px 16px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); border-radius:10px; color:#fff; font-size:15px;">
        </div>

        <div class="tabs" style="display:flex; gap:10px; margin-bottom:20px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:10px;">
            <button class="tab-btn active" data-tab="characters" onclick="switchLibraryTab('characters')" style="background:transparent; border:none; color:#888; padding:8px 16px; cursor:pointer; font-size:15px; border-radius:8px;">Персонажи</button>
            <button class="tab-btn" data-tab="worlds" onclick="switchLibraryTab('worlds')" style="background:transparent; border:none; color:#888; padding:8px 16px; cursor:pointer; font-size:15px; border-radius:8px;">Миры</button>
        </div>

        <div class="grid" id="libraryGrid"></div>
        <div id="libraryLoader" style="text-align:center; padding:20px; color:#666; display:none;">Загрузка...</div>
    </div>

    <!-- ===== ЧАТЫ (ЛИЧНОЕ ПРОСТРАНСТВО) ===== -->
    <div id="page-chats" class="page">
        <div class="flex-between">
            <div>
                <div class="page-title">Чаты</div>
                <div class="page-desc">Все твои диалоги с персонажами</div>
            </div>
            <button class="btn-primary" onclick="loadChats()" style="padding:8px 14px; font-size:13px;">🔄 Обновить</button>
        </div>
        <div id="chatHistoryGrid" class="grid"></div>
    </div>

    <!-- ===== ПЕРСОНАЖИ (СОЗДАТЕЛЬ) ===== -->
    <div id="page-characters" class="page">
        <div class="flex-between">
            <div><div class="page-title">Персонажи</div><div class="page-desc">Твои герои</div></div>
            <button class="btn-primary" onclick="showCreateCharacter()">+ Создать</button>
        </div>
        <div class="grid" id="charactersGrid"></div>
    </div>

    <!-- ===== СОЗДАНИЕ ПЕРСОНАЖА ===== -->
    <div id="page-character-create" class="page">
        <div class="flex-between">
            <div><div class="page-title">Создать персонажа</div><div class="page-desc">Придумай своего героя</div></div>
            <button class="btn-primary" onclick="showPage('characters')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="charName" placeholder="Имя">
            <input type="text" id="charRole" placeholder="Роль">
            <textarea id="charDesc" placeholder="Описание"></textarea>
            <textarea id="charPersonality" placeholder="Характер"></textarea>
            <textarea id="charBackstory" placeholder="Предыстория"></textarea>
            <textarea id="charGreeting" placeholder="Приветствие (первое сообщение бота)" style="min-height:60px;"></textarea>
            <input type="text" id="charAvatar" placeholder="Ссылка на аватарку">
            <label class="file-label">
                <span id="charAvatarLabel">Или загрузить изображение</span>
                <input type="file" id="charAvatarFile" accept="image/*" onchange="uploadAvatar('charAvatarFile','charAvatar','charAvatarLabel')">
            </label>
            <select id="charWorld" style="width:100%; padding:13px 16px; margin:8px 0; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); border-radius:10px; color:#fff; font-size:15px;">
                <option value="">Без мира</option>
            </select>
            <label class="checkbox-label"><input type="checkbox" id="charPublic"> Публичный</label>
            <div style="margin: 8px 0;">
                <label style="color:#aaa; font-size:13px; display:block; margin-bottom:6px;">✨ Быстрая генерация персонажа</label>

                <div style="display:flex; gap:10px;">
                    <input type="text" id="generatePrompt"
                           placeholder="Например: Опиши персонажа..."
                           style="flex:1; padding:10px 14px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); border-radius:10px; color:#fff; font-size:14px;">
                    <button onclick="generateCharacter()" class="btn-primary" style="padding:8px 20px; white-space:nowrap;">✨ Создать</button>
                </div>

                <div style="display:flex; gap:8px; margin-top:6px; flex-wrap:wrap;">
                    <span style="color:#555; font-size:11px;">Примеры:</span>
                    <span onclick="document.getElementById('generatePrompt').value='Максим Кац, российский политик'"
                          style="color:#666; font-size:11px; cursor:pointer; background:rgba(255,255,255,0.03); padding:2px 8px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
                        🎯 Быстрый
                    </span>
                    <span onclick="document.getElementById('generatePrompt').value='Гарри Поттер - молодой волшебник из Хогвартса, храбрый и верный друзьям. Говорит с британским акцентом, часто с сарказмом.'"
                          style="color:#666; font-size:11px; cursor:pointer; background:rgba(255,255,255,0.03); padding:2px 8px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
                        📚 Детальный
                    </span>
                    <span onclick="document.getElementById('generatePrompt').value='Тёмный эльф-лучник из Лесного Королевства. Мудрый, спокойный, любит звёзды. Говорит загадочно и с лёгкой иронией.'"
                          style="color:#666; font-size:11px; cursor:pointer; background:rgba(255,255,255,0.03); padding:2px 8px; border-radius:8px; border:1px solid rgba(255,255,255,0.05);">
                        🧝 Оригинальный
                    </span>
                </div>

                <div style="margin-top:4px;">
                    <span style="color:#444; font-size:10px;">
                        💡 Короткий запрос (до 10 слов) — AI додумает детали.
                        Длинный — точно выполнит инструкцию.
                    </span>
                </div>
            </div>
            <button class="btn" onclick="saveCharacter()">Сохранить</button>
        </div>
    </div>

    <!-- ===== РЕДАКТИРОВАНИЕ ПЕРСОНАЖА ===== -->
    <div id="page-character-edit" class="page">
        <div class="flex-between">
            <div><div class="page-title">Редактировать персонажа</div><div class="page-desc">Измени данные своего героя</div></div>
            <button class="btn-primary" onclick="showPage('characters')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="editCharName" placeholder="Имя">
            <input type="text" id="editCharRole" placeholder="Роль">
            <textarea id="editCharDesc" placeholder="Описание"></textarea>
            <textarea id="editCharPersonality" placeholder="Характер"></textarea>
            <textarea id="editCharBackstory" placeholder="Предыстория"></textarea>
            <textarea id="editCharGreeting" placeholder="Приветствие" style="min-height:60px;"></textarea>
            <input type="text" id="editCharAvatar" placeholder="Ссылка на аватарку">
            <label class="file-label">
                <span id="editCharAvatarLabel">Или загрузить изображение</span>
                <input type="file" id="editCharAvatarFile" accept="image/*" onchange="uploadAvatar('editCharAvatarFile','editCharAvatar','editCharAvatarLabel')">
            </label>
            <select id="editCharWorld" style="width:100%; padding:13px 16px; margin:8px 0; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); border-radius:10px; color:#fff; font-size:15px;">
                <option value="">Без мира</option>
            </select>
            <label class="checkbox-label"><input type="checkbox" id="editCharPublic"> Публичный</label>
            <div style="display:flex; gap:10px; margin:8px 0;">
                <input type="text" id="editGeneratePrompt"
                       placeholder="Опиши нового персонажа для перегенерации..."
                       style="flex:1; padding:10px 14px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); border-radius:10px; color:#fff; font-size:14px;">
                <button onclick="regenerateCharacter()" class="btn-primary" style="padding:8px 20px; white-space:nowrap; display:flex; align-items:center; gap:6px;">
                    <span style="font-size:16px;">↻</span> Перегенерировать
                </button>
            </div>
            <button class="btn" onclick="updateCharacter()">Сохранить изменения</button>
        </div>
    </div>

    <!-- ===== МИРЫ (СОЗДАТЕЛЬ) ===== -->
    <div id="page-worlds" class="page">
        <div class="flex-between">
            <div><div class="page-title">Миры</div><div class="page-desc">Твои вселенные</div></div>
            <button class="btn-primary" onclick="showCreateWorld()">+ Создать</button>
        </div>
        <div class="grid" id="worldsGrid"></div>
    </div>

    <!-- ===== СОЗДАНИЕ МИРА ===== -->
    <div id="page-world-create" class="page">
        <div class="flex-between">
            <div><div class="page-title">Создать мир</div><div class="page-desc">Придумай новую вселенную</div></div>
            <button class="btn-primary" onclick="showPage('worlds')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="worldName" placeholder="Название">
            <input type="text" id="worldGenre" placeholder="Жанр">
            <textarea id="worldDesc" placeholder="Описание"></textarea>
            <textarea id="worldSetting" placeholder="Сеттинг"></textarea>
            <textarea id="worldRules" placeholder="Правила мира"></textarea>
            <input type="text" id="worldAvatar" placeholder="Ссылка на обложку">
            <label class="file-label">
                <span id="worldAvatarLabel">Или загрузить изображение</span>
                <input type="file" id="worldAvatarFile" accept="image/*" onchange="uploadAvatar('worldAvatarFile','worldAvatar','worldAvatarLabel')">
            </label>
            <label class="checkbox-label"><input type="checkbox" id="worldPublic"> Публичный</label>
            <div style="margin: 8px 0;">
                <label style="color:#aaa; font-size:13px; display:block; margin-bottom:6px;">✨ Быстрая генерация мира</label>

                <div style="display:flex; gap:10px;">
                    <input type="text" id="generateWorldPrompt"
                           placeholder="Например: средневековое фэнтези с драконами"
                           style="flex:1; padding:10px 14px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); border-radius:10px; color:#fff; font-size:14px;">
                    <button onclick="generateWorld()" class="btn-primary" style="padding:8px 20px; white-space:nowrap;">✨ Создать</button>
                </div>

                <div style="margin-top:4px;">
                    <span style="color:#444; font-size:10px;">
                        💡 Короткий запрос (до 10 слов) — AI додумает детали.
                        Длинный — точно выполнит инструкцию.
                    </span>
                </div>
            </div>
            <button class="btn" onclick="saveWorld()">Сохранить</button>
        </div>
    </div>

    <!-- ===== РЕДАКТИРОВАНИЕ МИРА ===== -->
    <div id="page-world-edit" class="page">
        <div class="flex-between">
            <div><div class="page-title">Редактировать мир</div><div class="page-desc">Измени данные своей вселенной</div></div>
            <button class="btn-primary" onclick="showPage('worlds')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="editWorldName" placeholder="Название">
            <input type="text" id="editWorldGenre" placeholder="Жанр">
            <textarea id="editWorldDesc" placeholder="Описание"></textarea>
            <textarea id="editWorldSetting" placeholder="Сеттинг"></textarea>
            <textarea id="editWorldRules" placeholder="Правила мира"></textarea>
            <input type="text" id="editWorldAvatar" placeholder="Ссылка на обложку">
            <label class="file-label">
                <span id="editWorldAvatarLabel">Или загрузить изображение</span>
                <input type="file" id="editWorldAvatarFile" accept="image/*" onchange="uploadAvatar('editWorldAvatarFile','editWorldAvatar','editWorldAvatarLabel')">
            </label>
            <label class="checkbox-label"><input type="checkbox" id="editWorldPublic"> Публичный</label>
            <button class="btn" onclick="updateWorld()">Сохранить изменения</button>
        </div>
    </div>

    <!-- ===== ПЕРСОНЫ (ЛИЧНОЕ ПРОСТРАНСТВО) ===== -->
    <div id="page-personas" class="page">
        <div class="flex-between">
            <div><div class="page-title">Персоны</div><div class="page-desc">Кто ты в диалогах</div></div>
            <button class="btn-primary" onclick="showCreatePersona()">+ Создать</button>
        </div>
        <div class="grid" id="personasGrid"></div>
    </div>

    <!-- ===== СОЗДАНИЕ ПЕРСОНЫ ===== -->
    <div id="page-persona-create" class="page">
        <div class="flex-between">
            <div><div class="page-title">Создать персону</div><div class="page-desc">Кем ты будешь в историях</div></div>
            <button class="btn-primary" onclick="showPage('personas')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="personaName" placeholder="Имя">
            <input type="number" id="personaAge" placeholder="Возраст">
            <textarea id="personaAppearance" placeholder="Внешность"></textarea>
            <textarea id="personaPersonality" placeholder="Характер"></textarea>
            <textarea id="personaBackstory" placeholder="Предыстория"></textarea>
            <textarea id="personaSkills" placeholder="Навыки"></textarea>
            <input type="text" id="personaGoal" placeholder="Цель">
            <input type="text" id="personaAvatar" placeholder="Ссылка на аватарку">
            <label class="file-label">
                <span id="personaAvatarLabel">Или загрузить изображение</span>
                <input type="file" id="personaAvatarFile" accept="image/*" onchange="uploadAvatar('personaAvatarFile','personaAvatar','personaAvatarLabel')">
            </label>
            <button class="btn" onclick="savePersona()">Сохранить</button>
        </div>
    </div>

    <!-- ===== РЕДАКТИРОВАНИЕ ПЕРСОНЫ ===== -->
    <div id="page-persona-edit" class="page">
        <div class="flex-between">
            <div><div class="page-title">Редактировать персону</div><div class="page-desc">Измени данные своей персоны</div></div>
            <button class="btn-primary" onclick="showPage('personas')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="editPersonaName" placeholder="Имя">
            <input type="number" id="editPersonaAge" placeholder="Возраст">
            <textarea id="editPersonaAppearance" placeholder="Внешность"></textarea>
            <textarea id="editPersonaPersonality" placeholder="Характер"></textarea>
            <textarea id="editPersonaBackstory" placeholder="Предыстория"></textarea>
            <textarea id="editPersonaSkills" placeholder="Навыки"></textarea>
            <input type="text" id="editPersonaGoal" placeholder="Цель">
            <input type="text" id="editPersonaAvatar" placeholder="Ссылка на аватарку">
            <label class="file-label">
                <span id="editPersonaAvatarLabel">Или загрузить изображение</span>
                <input type="file" id="editPersonaAvatarFile" accept="image/*" onchange="uploadAvatar('editPersonaAvatarFile','editPersonaAvatar','editPersonaAvatarLabel')">
            </label>
            <button class="btn" onclick="updatePersona()">Сохранить изменения</button>
        </div>
    </div>

    <!-- ===== ПАМЯТЬ ===== -->
    <div id="page-memory" class="page">
        <div class="flex-between">
            <div><div class="page-title">Память</div><div class="page-desc">Воспоминания ботов</div></div>
            <button class="btn-primary" onclick="showCreateMemory()">+ Добавить</button>
        </div>
        <div class="grid" id="memoryGrid"></div>
    </div>

    <!-- ===== СОЗДАНИЕ ПАМЯТИ ===== -->
    <div id="page-memory-create" class="page">
        <div class="flex-between">
            <div><div class="page-title">Добавить воспоминание</div><div class="page-desc">Запиши важный момент</div></div>
            <button class="btn-primary" onclick="showPage('memory')">Назад</button>
        </div>
        <div class="form-box">
            <textarea id="memoryContent" placeholder="Что бот должен запомнить?" style="min-height:100px;"></textarea>
            <input type="number" id="memoryImportance" placeholder="Важность (0.1 - 2.0)" value="1.0" step="0.1">
            <select class="select-styled" id="memoryCharacter">
                <option value="">Выбери персонажа</option>
            </select>
            <button class="btn" onclick="saveMemory()">Сохранить</button>
        </div>
    </div>

    <!-- ===== КОМНАТЫ ===== -->
    <div id="page-rooms" class="page">
        <div class="flex-between">
            <div><div class="page-title">Комнаты</div><div class="page-desc">Общие пространства</div></div>
            <button class="btn-primary" onclick="showCreateRoom()">+ Создать</button>
        </div>
        <div class="grid" id="roomsGrid"></div>
    </div>

    <!-- ===== СОЗДАНИЕ КОМНАТЫ ===== -->
    <div id="page-room-create" class="page">
        <div class="flex-between">
            <div><div class="page-title">Создать комнату</div><div class="page-desc">Новое общее пространство</div></div>
            <button class="btn-primary" onclick="showPage('rooms')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="roomName" placeholder="Название">
            <textarea id="roomDesc" placeholder="Описание"></textarea>
            <button class="btn" onclick="saveRoom()">Сохранить</button>
        </div>
    </div>

    <!-- ===== ЛОРБУК ===== -->
    <div id="page-lore" class="page">
        <div class="flex-between">
            <div><div class="page-title">Лорбук</div><div class="page-desc">Энциклопедия миров</div></div>
            <button class="btn-primary" onclick="showCreateLore()">+ Добавить</button>
        </div>
        <input class="search-input" id="loreSearch" placeholder="Поиск по лорбуку...">
        <div class="grid" id="loreGrid"></div>
    </div>

    <!-- ===== СОЗДАНИЕ ЛОРА ===== -->
    <div id="page-lore-create" class="page">
        <div class="flex-between">
            <div><div class="page-title">Создать запись</div><div class="page-desc">Добавь новую информацию</div></div>
            <button class="btn-primary" onclick="showPage('lore')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="loreTitle" placeholder="Заголовок">
            <input type="text" id="loreCategory" placeholder="Категория">
            <textarea id="loreContent" placeholder="Содержание" style="min-height:120px;"></textarea>
            <input type="text" id="loreTags" placeholder="Теги (через запятую)">
            <select class="select-styled" id="loreCharacter" style="margin-top:8px;">
                <option value="">Без персонажа</option>
            </select>
            <select class="select-styled" id="loreWorld">
                <option value="">Без мира</option>
            </select>
            <select class="select-styled" id="loreRoom">
                <option value="">Без комнаты</option>
            </select>
            <button class="btn" onclick="saveLore()">Сохранить</button>
        </div>
    </div>

    <!-- ===== РЕДАКТИРОВАНИЕ ЛОРА ===== -->
    <div id="page-lore-edit" class="page">
        <div class="flex-between">
            <div><div class="page-title">Редактировать запись</div><div class="page-desc">Измени информацию</div></div>
            <button class="btn-primary" onclick="showPage('lore')">Назад</button>
        </div>
        <div class="form-box">
            <input type="text" id="editLoreTitle" placeholder="Заголовок">
            <input type="text" id="editLoreCategory" placeholder="Категория">
            <textarea id="editLoreContent" placeholder="Содержание" style="min-height:120px;"></textarea>
            <input type="text" id="editLoreTags" placeholder="Теги (через запятую)">
            <select class="select-styled" id="editLoreCharacter" style="margin-top:8px;">
                <option value="">Без персонажа</option>
            </select>
            <select class="select-styled" id="editLoreWorld">
                <option value="">Без мира</option>
            </select>
            <select class="select-styled" id="editLoreRoom">
                <option value="">Без комнаты</option>
            </select>
            <input type="hidden" id="editLoreId" value="">
            <button class="btn" onclick="updateLore()">Сохранить изменения</button>
        </div>
    </div>

    <!-- ===== ЧАТ ===== -->
    <div id="page-chat" class="page">
        <div class="flex-between" style="margin-bottom:10px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <button onclick="showPage('chats')" style="background:transparent; border:none; color:#888; font-size:28px; cursor:pointer; transition:0.3s; padding:0 8px;"
                        onmouseover="this.style.color='#fff'" onmouseout="this.style.color='#888'">
                    ←
                </button>
                <div>
                    <div class="page-title" id="chatTitle">Чат</div>
                    <div class="page-desc" id="chatSubtitle">Выбери персонажа и начни диалог</div>
                </div>
            </div>
            <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                <button class="btn-primary" onclick="toggleChatSettings()" style="padding:8px 14px; font-size:13px;">Настройки</button>
                <button class="btn-primary" onclick="openChatMemory()" style="padding:8px 14px; font-size:13px;">Память</button>
            </div>
        </div>

        <!-- Панель настроек -->
        <div id="chatSettingsPanel" style="display:none; background:rgba(255,255,255,0.03); border:1px solid rgba(48,76,47,0.15); border-radius:14px; padding:16px 20px; margin-bottom:16px;">
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                <div>
                    <label style="color:#aaa; font-size:13px;">Температура (креативность)</label>
                    <input type="range" id="chatTemperature" min="0" max="1.5" step="0.1" value="0.8" style="width:100%; accent-color:#304c2f;">
                    <span id="tempValue" style="color:#888; font-size:13px;">0.8</span>
                </div>
                <div>
                    <label style="color:#aaa; font-size:13px;">Длина ответов</label>
                    <div style="display:flex; gap:6px; margin-top:4px; flex-wrap:wrap;">
                        <button class="chat-len-btn" data-len="short" onclick="setChatLength('short')" style="padding:4px 12px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:#888; cursor:pointer; font-size:12px;">Короткие</button>
                        <button class="chat-len-btn active" data-len="medium" onclick="setChatLength('medium')" style="padding:4px 12px; border-radius:12px; border:1px solid rgba(48,76,47,0.3); background:rgba(48,76,47,0.15); color:#fff; cursor:pointer; font-size:12px;">Средние</button>
                        <button class="chat-len-btn" data-len="long" onclick="setChatLength('long')" style="padding:4px 12px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:#888; cursor:pointer; font-size:12px;">Длинные</button>
                    </div>
                </div>
                <div>
                    <label style="color:#aaa; font-size:13px;">Режим общения</label>
                    <select id="chatMode" style="width:100%; padding:6px 10px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); border-radius:8px; color:#fff; font-size:13px;">
                        <option value="friendship">Дружба</option>
                        <option value="flirt">Флирт</option>
                        <option value="romance">Романтика</option>
                        <option value="love">Любовное (18+)</option>
                        <option value="all" selected>Всё и сразу</option>
                    </select>
                </div>
                <div>
                    <label style="color:#aaa; font-size:13px;">Персона</label>
                    <select id="chatPersonaSelect" style="width:100%; padding:6px 10px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); border-radius:8px; color:#fff; font-size:13px;">
                        <option value="">Без персоны</option>
                    </select>
                </div>
            </div>
            <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
                <button onclick="openChatLore()" style="padding:4px 14px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:#888; cursor:pointer; font-size:12px; transition:0.3s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">Лорбук</button>
                <button onclick="openChatMemory()" style="padding:4px 14px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:#888; cursor:pointer; font-size:12px; transition:0.3s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">Память</button>
                <button onclick="openCharacterEditor()" style="padding:4px 14px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:#888; cursor:pointer; font-size:12px; transition:0.3s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">Редактор</button>
                <button onclick="clearChat()" style="padding:4px 14px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:#888; cursor:pointer; font-size:12px; transition:0.3s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">Начать заново</button>
                <button onclick="saveCurrentChat()" style="padding:4px 14px; border-radius:12px; border:1px solid rgba(48,76,47,0.3); background:rgba(48,76,47,0.1); color:#888; cursor:pointer; font-size:12px; transition:0.3s;" onmouseover="this.style.background='rgba(48,76,47,0.2)'; this.style.color='#fff'" onmouseout="this.style.background='rgba(48,76,47,0.1)'; this.style.color='#888'">💾 Сохранить чат</button>
                <button onclick="showChatHistory()" style="padding:4px 14px; border-radius:12px; border:1px solid rgba(255,255,255,0.1); background:transparent; color:#888; cursor:pointer; font-size:12px; transition:0.3s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'; this.style.color='#fff'" onmouseout="this.style.background='transparent'; this.style.color='#888'">📜 История чата</button>
            </div>
        </div>

        <!-- КОНТЕЙНЕР ЧАТА -->
        <div class="chat-container">
            <div class="chat-messages" id="chatMessages">
                <div style="color:#666;text-align:center;padding:36px 0;" id="chatPlaceholder">Выбери персонажа и начни диалог</div>
            </div>
            <div class="chat-input-area">
                <input type="text" id="chatInput" placeholder="Напиши сообщение..." onkeypress="if(event.key==='Enter') sendMessage()">
                <button class="btn" onclick="sendMessage()">Отправить</button>
            </div>
        </div>
    </div>

    <!-- ===== КВАРТИРА (ПРОФИЛЬ) ===== -->
    <div id="page-profile" class="page">
        <div class="page-title">Квартира</div>
        <div class="page-desc" id="profileName">Добро пожаловать!</div>

        <div class="form-box" style="max-width:500px;">
            <div style="text-align:center; margin-bottom:16px;">
                <div style="width:80px;height:80px;border-radius:50%;overflow:hidden;margin:0 auto;background:rgba(255,255,255,0.05);border:2px solid rgba(48,76,47,0.3);">
                    <img id="profileAvatarPreview" src="" style="width:100%;height:100%;object-fit:cover;display:none;">
                    <div id="profileAvatarPlaceholder" style="display:flex;align-items:center;justify-content:center;height:100%;color:#555;font-size:32px;">◌</div>
                </div>
                <label class="file-label" style="margin-top:8px;display:inline-block;padding:6px 18px;font-size:13px;">
                    <span id="profileAvatarLabel">Сменить аватар</span>
                    <input type="file" id="profileAvatarFile" accept="image/*" onchange="uploadAvatar('profileAvatarFile','profileAvatar','profileAvatarLabel')">
                </label>
                <input type="hidden" id="profileAvatar" value="">
            </div>
            <input type="text" id="profileUsername" placeholder="Имя пользователя (логин)" disabled style="opacity:0.6;">
            <input type="text" id="profileDisplayName" placeholder="Юзернейм (как тебя искать)">
            <textarea id="profileBio" placeholder="Описание профиля" style="min-height:70px;"></textarea>
            <button class="btn" onclick="saveProfile()">Сохранить профиль</button>
        </div>

        <div style="margin-top:20px;">
            <h3 style="color:#aaa; font-weight:400; font-size:16px; margin-bottom:10px;">API Ключи</h3>
            <div class="form-box" style="max-width:500px;">
                <input type="text" id="apiPolza" placeholder="Polza API Key">
                <input type="text" id="apiModel" placeholder="Модель (по умолчанию deepseek/deepseek-v4-flash)">
                <button class="btn" onclick="saveApiKeys()">Сохранить ключи</button>
            </div>
        </div>
    </div>

    <!-- ===== ВХОД ===== -->
    <div id="page-login" class="page">
        <div class="form-box">
            <h2>Вход</h2>
            <input type="text" id="loginUser" placeholder="Имя пользователя">
            <input type="password" id="loginPass" placeholder="Пароль">
            <button class="btn" onclick="login()">Войти</button>
            <div class="link">Нет аккаунта? <a onclick="showPage('register')">Зарегистрироваться</a></div>
        </div>
    </div>

    <!-- ===== РЕГИСТРАЦИЯ ===== -->
    <div id="page-register" class="page">
        <div class="form-box">
            <h2>Регистрация</h2>
            <input type="text" id="regUser" placeholder="Имя пользователя">
            <input type="password" id="regPass" placeholder="Пароль">
            <input type="password" id="regPass2" placeholder="Повтори пароль">
            <button class="btn" onclick="register()">Зарегистрироваться</button>
            <div class="link">Уже есть аккаунт? <a onclick="showPage('login')">Войти</a></div>
        </div>
    </div>

</div>

<!-- ===== МОДАЛЬНОЕ ОКНО ВЫБОРА ПЕРСОНЫ ===== -->
<div id="personaModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:9999; justify-content:center; align-items:center;">
    <div style="background:#1a1a1a; border-radius:20px; padding:30px; max-width:400px; width:90%; border:1px solid rgba(48,76,47,0.3); max-height:80vh; overflow-y:auto;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <h2 style="color:#fff; font-size:20px;">Выбери персону</h2>
            <button onclick="closePersonaModal()" style="background:transparent; border:none; color:#888; font-size:24px; cursor:pointer;">✕</button>
        </div>
        <p style="color:#888; font-size:14px; margin-bottom:16px;">Кем ты будешь в этом диалоге?</p>
        <div id="personaModalList" style="display:flex; flex-direction:column; gap:8px;"></div>
        <div style="margin-top:16px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.05);">
            <button onclick="closePersonaModal()" style="width:100%; padding:10px; background:transparent; border:1px solid rgba(255,255,255,0.1); border-radius:10px; color:#888; cursor:pointer;">Отмена</button>
        </div>
    </div>
</div>

<!-- ===== ИСТОРИЯ ЧАТОВ (МОДАЛЬНОЕ ОКНО) ===== -->
<div id="chatHistoryModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:9999; justify-content:center; align-items:center;">
    <div style="background:#1a1a1a; border-radius:20px; padding:30px; max-width:600px; width:90%; border:1px solid rgba(48,76,47,0.3); max-height:80vh; overflow-y:auto;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <h2 style="color:#fff; font-size:20px;">📜 История чата</h2>
            <button onclick="closeChatHistory()" style="background:transparent; border:none; color:#888; font-size:24px; cursor:pointer;">✕</button>
        </div>
        <div id="chatHistoryList" style="display:flex; flex-direction:column; gap:8px;">
            <!-- Список сохранённых чатов -->
        </div>
    </div>
</div>

<script>
// ============================================
// ПОЛНЫЙ JAVASCRIPT (без изменений)
// ============================================

// ============================================
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ============================================
let currentUser = null;
let userId = null;
let authToken = null;
let loreSearchTimeout = null;
let libraryTab = 'characters';
let libraryOffset = 0;
let libraryLoading = false;
let libraryHasMore = true;
let chatCharacterId = null;
let chatCharacterName = null;
let chatCharacterAvatar = null;
let chatGreetingSent = false;
let messageIdCounter = 0;
let editingCharacterId = null;
let editingWorldId = null;
let editingPersonaId = null;
let editingLoreId = null;
let _personaModalCallback = null;
let _pendingChatCharId = null;

// ============================================
// ЗАСТАВКА
// ============================================
function handleCoverClick() {
    console.log('Клик по заставке!');
    var cover = document.getElementById('cover');
    if (cover) {
        cover.classList.add('hidden');
        cover.style.display = 'none';
    }

    if (currentUser) {
        var btn = document.querySelector('.hamburger-btn');
        if (btn) btn.style.display = 'block';
        showPage('home');
    } else {
        showPage('login');
    }
}

// ============================================
// ЗАГРУЗКА СОСТОЯНИЯ
// ============================================
const saved = localStorage.getItem('hyg_user');
if (saved) {
    try {
        const d = JSON.parse(saved);
        currentUser = d.username;
        userId = d.id;
        authToken = d.token;
        
        document.getElementById('authBtn').textContent = currentUser;
        document.getElementById('authBtn').style.display = 'none';
        document.getElementById('logoutBtn').style.display = 'block';
        document.getElementById('userInfo').textContent = '◌ ' + currentUser;
        document.getElementById('profileName').textContent = 'Добро пожаловать, ' + currentUser + '!';
        document.getElementById('cover').classList.add('hidden');
        document.querySelector('.hamburger-btn').style.display = 'block';
        loadProfile();
    } catch(e) {
        console.error('Ошибка загрузки сохраненных данных:', e);
        localStorage.removeItem('hyg_user');
    }
} else {
    document.getElementById('authBtn').style.display = 'block';
    document.getElementById('logoutBtn').style.display = 'none';
}

// ============================================
// САЙДБАР
// ============================================
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const btn = document.getElementById('hamburgerBtn');
    const main = document.getElementById('mainContent');
    sidebar.classList.toggle('open');
    btn.classList.toggle('active');
    main.classList.toggle('shifted');
}

document.addEventListener('click', function(e) {
    const sidebar = document.getElementById('sidebar');
    const btn = document.getElementById('hamburgerBtn');
    if (sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        !btn.contains(e.target)) {
        sidebar.classList.remove('open');
        btn.classList.remove('active');
        document.getElementById('mainContent').classList.remove('shifted');
    }
});

// ============================================
// НАВИГАЦИЯ
// ============================================
function showPage(id) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById('page-' + id);
    if (target) target.classList.add('active');

    document.querySelectorAll('.sidebar .menu a').forEach(a => a.classList.remove('active'));
    const menuItem = document.querySelector('.sidebar .menu a[data-page="' + id + '"]');
    if (menuItem) {
        menuItem.classList.add('active');
    } else {
        const parentMap = {
            'character-create': 'characters',
            'character-edit': 'characters',
            'world-create': 'worlds',
            'world-edit': 'worlds',
            'persona-create': 'personas',
            'persona-edit': 'personas',
            'memory-create': 'memory',
            'room-create': 'rooms',
            'lore-create': 'lore',
            'lore-edit': 'lore'
        };
        const parent = parentMap[id];
        if (parent) {
            const parentItem = document.querySelector('.sidebar .menu a[data-page="' + parent + '"]');
            if (parentItem) parentItem.classList.add('active');
        }
    }

    if (window.innerWidth <= 768) {
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('hamburgerBtn').classList.remove('active');
        document.getElementById('mainContent').classList.remove('shifted');
    }

    if (id === 'characters') loadCharacters();
    if (id === 'library') {
        libraryOffset = 0;
        libraryHasMore = true;
        document.getElementById('libraryGrid').innerHTML = '';
        switchLibraryTab(libraryTab);
    }
    if (id === 'worlds') loadWorlds();
    if (id === 'personas') loadPersonas();
    if (id === 'memory') { loadMemory(); loadMemoryCharacters(); }
    if (id === 'lore') { loadLore(); loadLoreSelects(); }
    if (id === 'rooms') loadRooms();
    if (id === 'home') loadPopular();
    if (id === 'chats') loadChats();
}

function handleAuth() {
    if (currentUser) showPage('profile');
    else showPage('login');
}

// ============================================
// АВТОРИЗАЦИЯ
// ============================================
async function register() {
    const u = document.getElementById('regUser').value.trim();
    const p = document.getElementById('regPass').value;
    const p2 = document.getElementById('regPass2').value;
    if (u.length < 3) { alert('Имя минимум 3 символа'); return; }
    if (p.length < 4) { alert('Пароль минимум 4 символа'); return; }
    if (p !== p2) { alert('Пароли не совпадают'); return; }
    try {
        const r = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: u, password: p })
        });
        const d = await r.json();
        if (d.success) {
            currentUser = d.username;
            userId = d.user_id;
            authToken = d.token;
            
            document.getElementById('authBtn').style.display = 'none';
            document.getElementById('logoutBtn').style.display = 'block';
            document.getElementById('authBtn').textContent = currentUser;
            document.getElementById('userInfo').textContent = '◌ ' + currentUser;
            document.getElementById('profileName').textContent = 'Добро пожаловать, ' + currentUser + '!';
            
            localStorage.setItem('hyg_user', JSON.stringify({ 
                username: currentUser, 
                id: userId, 
                token: authToken 
            }));
            
            document.getElementById('cover').classList.add('hidden');
            document.querySelector('.hamburger-btn').style.display = 'block';
            showPage('home');
            loadProfile();
        } else {
            alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
        }
    } catch(e) { 
        alert('Ошибка: ' + e.message); 
    }
}

async function login() {
    const u = document.getElementById('loginUser').value.trim();
    const p = document.getElementById('loginPass').value;
    if (!u || !p) { alert('Введите имя и пароль'); return; }
    try {
        const r = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: u, password: p })
        });
        const d = await r.json();
        if (d.success) {
            currentUser = d.username;
            userId = d.user_id;
            authToken = d.token;
            
            document.getElementById('authBtn').style.display = 'none';
            document.getElementById('logoutBtn').style.display = 'block';
            document.getElementById('authBtn').textContent = currentUser;
            document.getElementById('userInfo').textContent = '◌ ' + currentUser;
            document.getElementById('profileName').textContent = 'Добро пожаловать, ' + currentUser + '!';
            
            localStorage.setItem('hyg_user', JSON.stringify({ 
                username: currentUser, 
                id: userId, 
                token: authToken 
            }));
            
            document.getElementById('cover').classList.add('hidden');
            document.querySelector('.hamburger-btn').style.display = 'block';
            showPage('home');
            loadProfile();
        } else {
            alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
        }
    } catch(e) { 
        alert('Ошибка: ' + e.message);
    }
}

async function logout() {
    if (!authToken) {
        currentUser = null;
        userId = null;
        authToken = null;
        localStorage.removeItem('hyg_user');
        document.getElementById('authBtn').style.display = 'block';
        document.getElementById('logoutBtn').style.display = 'none';
        document.getElementById('userInfo').textContent = 'Не авторизован';
        document.querySelector('.hamburger-btn').style.display = 'none';
        showPage('home');
        document.getElementById('cover').classList.remove('hidden');
        return;
    }
    
    try {
        await fetch('/api/logout?token=' + encodeURIComponent(authToken), {
            method: 'POST'
        });
    } catch(e) {
        console.error('Ошибка при выходе:', e);
    }
    
    currentUser = null;
    userId = null;
    authToken = null;
    localStorage.removeItem('hyg_user');
    
    document.getElementById('authBtn').style.display = 'block';
    document.getElementById('logoutBtn').style.display = 'none';
    document.getElementById('userInfo').textContent = 'Не авторизован';
    document.querySelector('.hamburger-btn').style.display = 'none';
    showPage('home');
    document.getElementById('cover').classList.remove('hidden');
}

// ============================================
// ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ЗАПРОСОВ С ТОКЕНОМ
// ============================================
function getAuthUrl(url) {
    if (authToken) {
        const separator = url.includes('?') ? '&' : '?';
        return url + separator + 'token=' + encodeURIComponent(authToken);
    }
    return url;
}

// ============================================
// API КЛЮЧИ
// ============================================
async function loadApiKeys() {
    if (!authToken) return;
    try {
        const r = await fetch(getAuthUrl('/api/keys'));
        const d = await r.json();
        if (d.keys) {
            document.getElementById('apiPolza').value = d.keys.polza || '';
            document.getElementById('apiModel').value = d.keys.model || '';
        }
    } catch(e) {}
}

async function saveApiKeys() {
    if (!authToken) { alert('Войдите чтобы сохранить ключи'); return; }
    const keys = {
        polza: document.getElementById('apiPolza').value.trim(),
        model: document.getElementById('apiModel').value.trim() || 'deepseek/deepseek-v4-flash'
    };
    try {
        await fetch(getAuthUrl('/api/keys'), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keys: keys })
        });
        alert('Ключи сохранены!');
    } catch(e) { alert('Ошибка: ' + e.message); }
}

// ============================================
// ПРОФИЛЬ
// ============================================
async function loadProfile() {
    if (!authToken) return;
    try {
        const r = await fetch(getAuthUrl('/api/profile'));
        const data = await r.json();
        document.getElementById('profileUsername').value = data.username;
        document.getElementById('profileDisplayName').value = data.display_name || data.username;
        document.getElementById('profileBio').value = data.bio || '';
        if (data.avatar) {
            document.getElementById('profileAvatarPreview').src = data.avatar;
            document.getElementById('profileAvatarPreview').style.display = 'block';
            document.getElementById('profileAvatarPlaceholder').style.display = 'none';
            document.getElementById('profileAvatar').value = data.avatar;
        }
        loadApiKeys();
    } catch(e) {}
}

async function saveProfile() {
    if (!authToken) { alert('Войдите чтобы сохранить профиль'); return; }
    const data = {
        display_name: document.getElementById('profileDisplayName').value.trim() || document.getElementById('profileUsername').value,
        bio: document.getElementById('profileBio').value.trim(),
        avatar: document.getElementById('profileAvatar').value
    };
    try {
        await fetch(getAuthUrl('/api/profile'), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        alert('Профиль сохранён!');
    } catch(e) { alert('Ошибка: ' + e.message); }
}

// ============================================
// ЗАГРУЗКА АВАТАРКИ
// ============================================
async function uploadAvatar(fileId, targetId, labelId) {
    const fileInput = document.getElementById(fileId);
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const r = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await r.json();
        if (data.url) {
            document.getElementById(targetId).value = data.url;
            document.getElementById(labelId).textContent = '✓ Загружено';
            if (fileId === 'profileAvatarFile') {
                document.getElementById('profileAvatarPreview').src = data.url;
                document.getElementById('profileAvatarPreview').style.display = 'block';
                document.getElementById('profileAvatarPlaceholder').style.display = 'none';
            }
        }
    } catch(e) {
        alert('Ошибка загрузки: ' + e.message);
        document.getElementById(labelId).textContent = 'Ошибка загрузки';
    }
}

// ============================================
// ПЕРСОНАЖИ
// ============================================
async function loadCharacters() {
    if (!authToken) {
        document.getElementById('charactersGrid').innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Войдите чтобы увидеть персонажей</div>';
        return;
    }
    try {
        const r = await fetch(getAuthUrl('/api/characters'));
        const chars = await r.json();
        const grid = document.getElementById('charactersGrid');
        if (!chars || !chars.length) {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">У вас пока нет персонажей</div>';
            return;
        }
        grid.innerHTML = chars.map(c => `
            <div class="card" ondblclick="startChat(${c.id})" style="cursor:pointer;">
                <div class="avatar">${c.avatar ? '<img src="'+c.avatar+'">' : '✦'}</div>
                <div class="name">${c.name}</div>
                <div class="role">${c.role || 'Без роли'}</div>
                <div class="role" style="font-size:11px; color:#555;">${c.world_id ? '🌍 В мире' : ''}</div>
                <div class="actions">
                    <button onclick="event.stopPropagation(); showEditCharacter(${c.id})" style="background:rgba(48,76,47,0.3);">✏️ Редактировать</button>
                    <button onclick="event.stopPropagation(); deleteCharacter(${c.id})" class="danger">Удалить</button>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error(e); }
}

function showCreateCharacter() {
    ['charName','charRole','charDesc','charPersonality','charBackstory','charGreeting','charAvatar'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('charPublic').checked = false;
    document.getElementById('charAvatarLabel').textContent = 'Или загрузить изображение';
    loadWorldsSelect('charWorld');
    showPage('character-create');
}

function showEditCharacter(charId) {
    editingCharacterId = charId;
    showPage('character-edit');
    loadWorldsSelect('editCharWorld');
    fetch(getAuthUrl('/api/characters/' + charId))
        .then(function(r) { return r.json(); })
        .then(function(char) {
            if (char.error) {
                alert(char.error);
                showPage('characters');
                return;
            }
            document.getElementById('editCharName').value = char.name || '';
            document.getElementById('editCharRole').value = char.role || '';
            document.getElementById('editCharDesc').value = char.description || '';
            document.getElementById('editCharPersonality').value = char.personality || '';
            document.getElementById('editCharBackstory').value = char.backstory || '';
            document.getElementById('editCharGreeting').value = char.greeting || '';
            document.getElementById('editCharAvatar').value = char.avatar || '';
            document.getElementById('editCharPublic').checked = char.is_public || false;
            document.getElementById('editCharAvatarLabel').textContent = char.avatar ? '✓ Загружено' : 'Или загрузить изображение';
            if (char.world_id) {
                document.getElementById('editCharWorld').value = char.world_id;
            }
        })
        .catch(function(e) {
            alert('Ошибка загрузки персонажа: ' + e.message);
            showPage('characters');
        });
}

async function updateCharacter() {
    if (!authToken) { alert('Войдите чтобы редактировать персонажа'); return; }
    if (!editingCharacterId) { alert('Персонаж не выбран'); return; }
    const data = {
        name: document.getElementById('editCharName').value.trim(),
        role: document.getElementById('editCharRole').value.trim() || null,
        description: document.getElementById('editCharDesc').value.trim() || null,
        personality: document.getElementById('editCharPersonality').value.trim() || null,
        backstory: document.getElementById('editCharBackstory').value.trim() || null,
        greeting: document.getElementById('editCharGreeting').value.trim() || null,
        avatar: document.getElementById('editCharAvatar').value.trim() || null,
        is_public: document.getElementById('editCharPublic').checked,
        world_id: parseInt(document.getElementById('editCharWorld').value) || null
    };
    if (!data.name) { alert('Введите имя'); return; }
    try {
        const r = await fetch(getAuthUrl('/api/characters/' + editingCharacterId), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const d = await r.json();
        if (d.success) {
            alert('Персонаж обновлён!');
            showPage('characters');
        } else {
            alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    }
}

async function saveCharacter() {
    if (!authToken) { alert('Войдите чтобы создать персонажа'); return; }
    const data = {
        name: document.getElementById('charName').value.trim(),
        role: document.getElementById('charRole').value.trim() || null,
        description: document.getElementById('charDesc').value.trim() || null,
        personality: document.getElementById('charPersonality').value.trim() || null,
        backstory: document.getElementById('charBackstory').value.trim() || null,
        greeting: document.getElementById('charGreeting').value.trim() || null,
        avatar: document.getElementById('charAvatar').value.trim() || null,
        is_public: document.getElementById('charPublic').checked,
        world_id: parseInt(document.getElementById('charWorld').value) || null
    };
    if (!data.name) { alert('Введите имя'); return; }
    try {
        const r = await fetch(getAuthUrl('/api/characters'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const d = await r.json();
        if (d.success) { alert('Персонаж создан!'); showPage('characters'); }
        else alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
    } catch(e) { alert('Ошибка: ' + e.message); }
}

async function deleteCharacter(id) {
    if (!confirm('Удалить персонажа?')) return;
    try {
        const r = await fetch(getAuthUrl('/api/characters/' + id), {
            method: 'DELETE'
        });
        const data = await r.json();
        if (data.success) {
            loadCharacters();
        } else {
            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка удаления: ' + e.message);
    }
}

async function loadWorldsSelect(selectId) {
    if (!authToken) return;
    try {
        const r = await fetch(getAuthUrl('/api/worlds'));
        const worlds = await r.json();
        const sel = document.getElementById(selectId);
        if (!sel) return;
        sel.innerHTML = '<option value="">Без мира</option>';
        worlds.forEach(w => {
            sel.innerHTML += '<option value="' + w.id + '">' + w.name + '</option>';
        });
    } catch(e) {
        console.error('Ошибка загрузки миров:', e);
    }
}

// ============================================
// БИБЛИОТЕКА (ОБЩЕЕ ПРОСТРАНСТВО)
// ============================================
function switchLibraryTab(tab) {
    libraryTab = tab;
    libraryOffset = 0;
    libraryHasMore = true;
    document.getElementById('librarySearch').value = '';
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.tab-btn[data-tab="' + tab + '"]').classList.add('active');
    document.getElementById('libraryGrid').innerHTML = '';
    loadLibrary();
}

let librarySearchTimeout = null;

async function loadLibrary() {
    if (libraryLoading || !libraryHasMore) return;
    libraryLoading = true;
    document.getElementById('libraryLoader').style.display = 'block';

    try {
        const search = document.getElementById('librarySearch')?.value || '';
        const endpoint = libraryTab === 'characters' ? '/api/characters/public' : '/api/worlds/public';
        const url = endpoint + '?limit=20&offset=' + libraryOffset + '&search=' + encodeURIComponent(search);
        const r = await fetch(url);
        const data = await r.json();

        const grid = document.getElementById('libraryGrid');

        if (data.items.length === 0) {
            libraryHasMore = false;
            if (libraryOffset === 0) {
                grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">' +
                    (search ? 'Ничего не найдено по запросу "' + search + '"' : 'Публичных записей пока нет') +
                    '</div>';
            }
        } else {
            data.items.forEach(function(item) {
                const card = document.createElement('div');
                card.className = 'card';
                if (libraryTab === 'characters') {
                    card.innerHTML = `
                        <div class="avatar">${item.avatar ? '<img src="'+item.avatar+'">' : '✦'}</div>
                        <div class="name">${item.name}</div>
                        <div class="role">${item.role || 'Без роли'}</div>
                        <div class="actions">
                            <button onclick="startChat(${item.id})">Чат</button>
                        </div>
                    `;
                } else {
                    card.innerHTML = `
                        <div class="avatar">${item.avatar ? '<img src="'+item.avatar+'">' : '⊙'}</div>
                        <div class="name">${item.name}</div>
                        <div class="role">${item.description || 'Без описания'}</div>
                    `;
                }
                grid.appendChild(card);
            });

            libraryOffset += data.items.length;
            libraryHasMore = data.items.length === data.limit;
        }
    } catch(e) {
        console.error(e);
    }

    libraryLoading = false;
    document.getElementById('libraryLoader').style.display = 'none';
}

document.getElementById('librarySearch')?.addEventListener('input', function() {
    clearTimeout(librarySearchTimeout);
    librarySearchTimeout = setTimeout(function() {
        libraryOffset = 0;
        libraryHasMore = true;
        document.getElementById('libraryGrid').innerHTML = '';
        loadLibrary();
    }, 400);
});

window.addEventListener('scroll', function() {
    if (document.getElementById('page-library').classList.contains('active')) {
        const loader = document.getElementById('libraryLoader');
        if (loader) {
            const rect = loader.getBoundingClientRect();
            if (rect.top < window.innerHeight + 100) {
                loadLibrary();
            }
        }
    }
});

// ============================================
// ЧАТ
// ============================================

function startChat(charId) {
    console.log('✅ startChat вызван, charId:', charId);

    var savedPersona = localStorage.getItem('chat_persona_' + charId);
    console.log('✅ savedPersona:', savedPersona);

    if (savedPersona) {
        console.log('✅ Персона уже выбрана, открываем чат');
        startChatWithPersona(charId, parseInt(savedPersona));
    } else {
        console.log('✅ Персоны нет, показываем модалку');
        _pendingChatCharId = charId;
        openPersonaModal(function(selectedPersonaId) {
            console.log('✅ Callback вызван с ID:', selectedPersonaId);
            if (selectedPersonaId) {
                localStorage.setItem('chat_persona_' + charId, selectedPersonaId);
                startChatWithPersona(charId, selectedPersonaId);
            } else {
                console.log('❌ Выбор персоны отменён');
            }
        });
    }
}

function startChatWithPersona(charId, personaId) {
    chatCharacterId = charId;
    chatGreetingSent = false;

    if (personaId) {
        localStorage.setItem('chat_persona_' + charId, personaId);
    }

    showPage('chat');

    fetch(getAuthUrl('/api/characters'))
        .then(function(r) { return r.json(); })
        .then(function(chars) {
            var char = chars.find(function(c) { return c.id === charId; });
            if (char) {
                chatCharacterName = char.name;
                chatCharacterAvatar = char.avatar || '';
                document.getElementById('chatTitle').textContent = 'Чат с ' + char.name;
                document.getElementById('chatSubtitle').textContent = char.role || 'Персонаж';
                var div = document.getElementById('chatMessages');
                div.innerHTML = '';

                if (personaId) {
                    var sel = document.getElementById('chatPersonaSelect');
                    for (var i = 0; i < sel.options.length; i++) {
                        if (sel.options[i].value == personaId) {
                            sel.value = personaId;
                            break;
                        }
                    }
                }

                loadChatHistory(charId);
            }
        })
        .catch(function(e) { console.error(e); });

    loadChatPersonas();
}

async function loadChatHistory(characterId) {
    if (!authToken) return;
    try {
        var savedPersonaId = localStorage.getItem('chat_persona_' + characterId);
        if (savedPersonaId) {
            var sel = document.getElementById('chatPersonaSelect');
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value == savedPersonaId) {
                    sel.value = savedPersonaId;
                    break;
                }
            }
        }

        var r = await fetch(getAuthUrl('/api/chat/history?character_id=' + characterId));
        var history = await r.json();
        var div = document.getElementById('chatMessages');
        div.innerHTML = '';

        if (history.length === 0) {
            fetch(getAuthUrl('/api/characters'))
                .then(function(r) { return r.json(); })
                .then(function(chars) {
                    var char = chars.find(function(c) { return c.id === characterId; });
                    if (char && char.greeting && !chatGreetingSent) {
                        var msgId = 'msg_' + (++messageIdCounter);
                        addBotMessage(char.greeting, msgId);
                        chatGreetingSent = true;
                    }
                });
            return;
        }

        for (var i = 0; i < history.length; i += 2) {
            if (i < history.length) {
                var userMsg = history[i];
                if (userMsg.role === 'user') {
                    var userMsgId = 'msg_' + (++messageIdCounter);
                    addUserMessage(userMsg.content, userMsgId);
                }
            }
            if (i + 1 < history.length) {
                var botMsg = history[i + 1];
                if (botMsg.role === 'assistant') {
                    var botMsgId = 'msg_' + (++messageIdCounter);
                    addBotMessage(botMsg.content, botMsgId);
                }
            }
        }

        div.scrollTop = div.scrollHeight;
    } catch(e) {
        console.error('Ошибка загрузки истории:', e);
    }
}

function addUserMessage(text, messageId = null) {
    var div = document.getElementById('chatMessages');
    var avatar = document.getElementById('profileAvatarPreview')?.src || '';

    if (!messageId) {
        messageId = 'msg_' + (++messageIdCounter);
    }

    var wrapper = document.createElement('div');
    wrapper.className = 'msg-wrapper user';
    wrapper.dataset.messageId = messageId;
    wrapper.dataset.isBot = 'false';

    var content = document.createElement('div');
    content.className = 'msg-content';
    content.textContent = text;

    var actions = document.createElement('div');
    actions.className = 'msg-actions';
    actions.innerHTML = '<button class="edit-btn" onclick="startEditMessage(this)" title="Редактировать сообщение">✏️</button>';

    var avatarDiv = document.createElement('div');
    avatarDiv.className = 'msg-avatar';
    avatarDiv.style.cssText = 'width:32px; height:32px; border-radius:50%; overflow:hidden; background:rgba(255,255,255,0.05); flex-shrink:0; cursor:pointer; transition:0.3s;';
    avatarDiv.title = 'Сменить персону';
    avatarDiv.onclick = openPersonaModalFromChat;

    if (avatar) {
        avatarDiv.innerHTML = '<img src="' + avatar + '" style="width:100%;height:100%;object-fit:cover;">';
    } else {
        avatarDiv.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:16px;">◌</div>';
    }

    wrapper.appendChild(actions);
    wrapper.appendChild(content);
    wrapper.appendChild(avatarDiv);
    div.appendChild(wrapper);
    div.scrollTop = div.scrollHeight;

    return messageId;
}

function addBotMessage(text, messageId = null) {
    var div = document.getElementById('chatMessages');
    var avatar = chatCharacterAvatar || '';

    if (!messageId) {
        messageId = 'msg_' + (++messageIdCounter);
    }

    var wrapper = document.createElement('div');
    wrapper.className = 'msg-wrapper bot';
    wrapper.dataset.messageId = messageId;
    wrapper.dataset.isBot = 'true';

    var avatarDiv = document.createElement('div');
    avatarDiv.style.cssText = 'width:32px; height:32px; border-radius:50%; overflow:hidden; background:rgba(255,255,255,0.05); flex-shrink:0;';

    if (avatar) {
        avatarDiv.innerHTML = '<img src="' + avatar + '" style="width:100%;height:100%;object-fit:cover;">';
    } else {
        avatarDiv.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:16px;">✦</div>';
    }

    var content = document.createElement('div');
    content.className = 'msg-content';
    content.textContent = text;

    var actions = document.createElement('div');
    actions.className = 'msg-actions';
    actions.innerHTML = `
        <button class="edit-btn" onclick="startEditMessage(this)" title="Редактировать сообщение">✏️</button>
        <button class="regenerate-btn" onclick="regenerateMessage(this)" title="Сгенерировать заново">🔄</button>
    `;

    wrapper.appendChild(avatarDiv);
    wrapper.appendChild(content);
    wrapper.appendChild(actions);
    div.appendChild(wrapper);
    div.scrollTop = div.scrollHeight;

    return messageId;
}

// ============================================
// РЕГЕНЕРАЦИЯ ОТВЕТА
// ============================================

async function regenerateMessage(btn) {
    const wrapper = btn.closest('.msg-wrapper');
    if (!wrapper) return;

    const allMessages = document.querySelectorAll('.msg-wrapper');
    let userMessage = null;
    let userMessageText = '';

    for (let i = 0; i < allMessages.length; i++) {
        if (allMessages[i] === wrapper) {
            for (let j = i - 1; j >= 0; j--) {
                if (allMessages[j].dataset.isBot === 'false') {
                    userMessage = allMessages[j];
                    userMessageText = userMessage.querySelector('.msg-content').textContent;
                    break;
                }
            }
            break;
        }
    }

    if (!userMessage) {
        alert('Не найдено сообщение пользователя для регенерации');
        return;
    }

    if (!chatCharacterId) {
        alert('Персонаж не выбран');
        return;
    }

    const content = wrapper.querySelector('.msg-content');
    const originalText = content.textContent;
    content.textContent = '🔄 Генерация нового ответа...';
    content.style.opacity = '0.6';

    try {
        const temperature = parseFloat(document.getElementById('chatTemperature').value) || 0.8;
        const mode = document.getElementById('chatMode').value;
        const personaId = document.getElementById('chatPersonaSelect').value;

        const r = await fetch(getAuthUrl('/api/chat/regenerate'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                character_id: chatCharacterId,
                persona_id: personaId ? parseInt(personaId) : null,
                user_message: userMessageText,
                temperature: temperature,
                mode: mode,
                max_tokens: 1500
            })
        });

        const data = await r.json();

        if (data.success && data.response) {
            content.textContent = data.response;
            content.style.opacity = '1';

            let regenNote = content.querySelector('.regen-note');
            if (!regenNote) {
                regenNote = document.createElement('span');
                regenNote.className = 'regen-note';
                regenNote.style.cssText = 'font-size:11px; color:#666; margin-left:8px;';
                content.appendChild(regenNote);
            }
            regenNote.textContent = '🔄 регенерировано';
        } else {
            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            content.textContent = originalText;
            content.style.opacity = '1';
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
        content.textContent = originalText;
        content.style.opacity = '1';
    }
}

// ============================================
// РЕДАКТИРОВАНИЕ СООБЩЕНИЙ
// ============================================

function startEditMessage(btn) {
    var wrapper = btn.closest('.msg-wrapper');
    if (!wrapper) return;

    var content = wrapper.querySelector('.msg-content');
    if (!content) return;

    var originalText = content.textContent;
    var isBot = wrapper.dataset.isBot === 'true';
    var messageId = wrapper.dataset.messageId;

    var actions = wrapper.querySelector('.msg-actions');
    if (actions) actions.style.display = 'none';

    var editContainer = document.createElement('div');
    editContainer.className = 'edit-container';
    editContainer.style.cssText = 'display:flex; gap:8px; align-items:center; flex:1; width:100%;';

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'edit-input';
    input.value = originalText;
    input.style.cssText = 'flex:1; padding:8px 12px; background:rgba(255,255,255,0.06); border:1px solid rgba(48,76,47,0.3); border-radius:8px; color:#fff; font-size:14px; font-family:inherit; outline:none;';
    input.onkeypress = function(e) {
        if (e.key === 'Enter') saveEdit(this);
        if (e.key === 'Escape') cancelEdit(this);
    };

    var editActions = document.createElement('div');
    editActions.className = 'edit-actions';
    editActions.innerHTML = `
        <button class="save-btn" onclick="saveEdit(this)">💾 Сохранить</button>
        <button class="cancel-edit-btn" onclick="cancelEdit(this)">✕ Отмена</button>
    `;

    editContainer.appendChild(input);
    editContainer.appendChild(editActions);

    content.style.display = 'none';
    content.parentNode.insertBefore(editContainer, content.nextSibling);

    setTimeout(function() {
        input.focus();
        input.select();
    }, 50);
}

async function saveEdit(btn) {
    var editContainer = btn.closest('.edit-container');
    if (!editContainer) return;

    var wrapper = editContainer.closest('.msg-wrapper');
    if (!wrapper) return;

    var input = editContainer.querySelector('.edit-input');
    if (!input) return;

    var newText = input.value.trim();
    if (!newText) {
        alert('Сообщение не может быть пустым');
        return;
    }

    var content = wrapper.querySelector('.msg-content');
    var isBot = wrapper.dataset.isBot === 'true';
    var messageId = wrapper.dataset.messageId;
    var originalText = content.textContent;

    content.textContent = '⏳ Сохранение...';
    content.style.display = 'block';
    editContainer.remove();
    var actions = wrapper.querySelector('.msg-actions');
    if (actions) actions.style.display = 'flex';

    try {
        var r = await fetch(getAuthUrl('/api/chat/message'), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message_id: parseInt(messageId.replace('msg_', '')),
                new_content: newText,
                is_bot: isBot
            })
        });

        var data = await r.json();

        if (data.success) {
            content.textContent = newText;
            var editNote = document.createElement('span');
            editNote.style.cssText = 'font-size:11px; color:#666; margin-left:8px;';
            editNote.textContent = '✎ отредактировано';

            var oldNote = content.querySelector('.edit-note');
            if (oldNote) oldNote.remove();

            var textNode = document.createTextNode(content.textContent);
            content.innerHTML = '';
            content.appendChild(textNode);
            content.appendChild(editNote);
        } else {
            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            content.textContent = originalText;
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
        content.textContent = originalText;
    }
}

function cancelEdit(btn) {
    var editContainer = btn.closest('.edit-container');
    if (!editContainer) return;

    var wrapper = editContainer.closest('.msg-wrapper');
    if (!wrapper) return;

    var content = wrapper.querySelector('.msg-content');
    if (!content) return;

    content.style.display = 'block';
    editContainer.remove();

    var actions = wrapper.querySelector('.msg-actions');
    if (actions) actions.style.display = 'flex';
}

async function loadChatPersonas() {
    if (!authToken) return;
    try {
        var r = await fetch(getAuthUrl('/api/personas'));
        var personas = await r.json();
        var sel = document.getElementById('chatPersonaSelect');
        sel.innerHTML = '<option value="">Без персоны</option>';
        personas.forEach(function(p) {
            sel.innerHTML += '<option value="' + p.id + '" ' + (p.is_active ? 'selected' : '') + '>' + p.name + '</option>';
        });
    } catch(e) {}
}

async function sendMessage() {
    var input = document.getElementById('chatInput');
    var msg = input.value.trim();
    if (!msg) return;
    if (!authToken) { alert('Войдите чтобы общаться'); return; }
    if (!chatCharacterId) { alert('Выберите персонажа'); return; }

    var msgId = 'msg_' + (++messageIdCounter);
    addUserMessage(msg, msgId);
    input.value = '';
    var div = document.getElementById('chatMessages');
    div.innerHTML += '<div class="msg bot" id="typingIndicator">' +
        '<div style="display:flex; align-items:flex-end; gap:8px;">' +
            '<div style="width:32px; height:32px; border-radius:50%; overflow:hidden; background:rgba(255,255,255,0.05); flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:16px;">✦</div>' +
            '<div style="background:rgba(48,76,47,0.1); padding:10px 16px; border-radius:12px;">Печатает...</div>' +
        '</div>' +
    '</div>';
    div.scrollTop = div.scrollHeight;

    try {
        var temperature = parseFloat(document.getElementById('chatTemperature').value) || 0.8;
        var mode = document.getElementById('chatMode').value;
        var personaId = document.getElementById('chatPersonaSelect').value;

        var r = await fetch(getAuthUrl('/api/chat'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: msg,
                character_id: chatCharacterId,
                persona_id: personaId ? parseInt(personaId) : null,
                temperature: temperature,
                mode: mode
            })
        });
        var d = await r.json();
        var ind = document.getElementById('typingIndicator');
        if (ind) ind.remove();
        if (d.response) {
            var botMsgId = 'msg_' + (++messageIdCounter);
            addBotMessage(d.response, botMsgId);
        } else {
            div.innerHTML += '<div class="msg bot" style="color:#ff4444;">' + (d.error || 'Ошибка') + '</div>';
        }
    } catch(e) {
        var ind = document.getElementById('typingIndicator');
        if (ind) ind.remove();
        div.innerHTML += '<div class="msg bot" style="color:#ff4444;">Ошибка: ' + e.message + '</div>';
    }
}

function toggleChatSettings() {
    var panel = document.getElementById('chatSettingsPanel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function setChatLength(len) {
    document.querySelectorAll('.chat-len-btn').forEach(function(b) {
        b.classList.remove('active');
        b.style.background = 'transparent';
        b.style.color = '#888';
        b.style.borderColor = 'rgba(255,255,255,0.1)';
    });
    var btn = document.querySelector('.chat-len-btn[data-len="' + len + '"]');
    if (btn) {
        btn.classList.add('active');
        btn.style.background = 'rgba(48,76,47,0.15)';
        btn.style.color = '#fff';
        btn.style.borderColor = 'rgba(48,76,47,0.3)';
    }
}

document.getElementById('chatTemperature')?.addEventListener('input', function() {
    document.getElementById('tempValue').textContent = this.value;
});

function openChatMemory() {
    if (!chatCharacterId) { alert('Выберите персонажа'); return; }
    showPage('memory');
    setTimeout(function() {
        var sel = document.getElementById('memoryCharacter');
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].value == chatCharacterId) {
                sel.value = chatCharacterId;
                break;
            }
        }
        loadMemory();
    }, 300);
}

function openChatLore() {
    if (!chatCharacterId) { alert('Выберите персонажа'); return; }
    showPage('lore');
    setTimeout(function() {
        var sel = document.getElementById('loreCharacter');
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].value == chatCharacterId) {
                sel.value = chatCharacterId;
                break;
            }
        }
        loadLore();
    }, 300);
}

function openCharacterEditor() {
    if (!chatCharacterId) { alert('Выберите персонажа'); return; }
    showEditCharacter(chatCharacterId);
}

// ============================================
// МИРЫ
// ============================================
async function loadWorlds() {
    if (!authToken) {
        document.getElementById('worldsGrid').innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Войдите чтобы увидеть миры</div>';
        return;
    }
    try {
        var r = await fetch(getAuthUrl('/api/worlds'));
        var worlds = await r.json();
        var grid = document.getElementById('worldsGrid');
        if (!worlds || !worlds.length) {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">У вас пока нет миров</div>';
            return;
        }
        grid.innerHTML = worlds.map(function(w) {
            return `
                <div class="card">
                    <div class="avatar">${w.avatar ? '<img src="'+w.avatar+'">' : '⊙'}</div>
                    <div class="name">${w.name}</div>
                    <div class="role">${w.genre || 'Без жанра'}</div>
                    <div class="actions">
                        <button onclick="event.stopPropagation(); showEditWorld(${w.id})" style="background:rgba(48,76,47,0.3);">✏️ Редактировать</button>
                        <button onclick="event.stopPropagation(); deleteWorld(${w.id})" class="danger">Удалить</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch(e) { console.error(e); }
}

function showCreateWorld() {
    ['worldName','worldGenre','worldDesc','worldSetting','worldRules','worldAvatar'].forEach(function(id) {
        document.getElementById(id).value = '';
    });
    document.getElementById('worldPublic').checked = false;
    document.getElementById('worldAvatarLabel').textContent = 'Или загрузить изображение';
    showPage('world-create');
}

function showEditWorld(worldId) {
    editingWorldId = worldId;
    showPage('world-edit');
    fetch(getAuthUrl('/api/worlds/' + worldId))
        .then(function(r) { return r.json(); })
        .then(function(world) {
            if (world.error) {
                alert(world.error);
                showPage('worlds');
                return;
            }
            document.getElementById('editWorldName').value = world.name || '';
            document.getElementById('editWorldGenre').value = world.genre || '';
            document.getElementById('editWorldDesc').value = world.description || '';
            document.getElementById('editWorldSetting').value = world.setting || '';
            document.getElementById('editWorldRules').value = world.rules || '';
            document.getElementById('editWorldAvatar').value = world.avatar || '';
            document.getElementById('editWorldPublic').checked = world.is_public || false;
            document.getElementById('editWorldAvatarLabel').textContent = world.avatar ? '✓ Загружено' : 'Или загрузить изображение';
        })
        .catch(function(e) {
            alert('Ошибка загрузки мира: ' + e.message);
            showPage('worlds');
        });
}

async function updateWorld() {
    if (!authToken) { alert('Войдите чтобы редактировать мир'); return; }
    if (!editingWorldId) { alert('Мир не выбран'); return; }
    var data = {
        name: document.getElementById('editWorldName').value.trim(),
        genre: document.getElementById('editWorldGenre').value.trim() || null,
        description: document.getElementById('editWorldDesc').value.trim() || null,
        setting: document.getElementById('editWorldSetting').value.trim() || null,
        rules: document.getElementById('editWorldRules').value.trim() || null,
        avatar: document.getElementById('editWorldAvatar').value.trim() || null,
        is_public: document.getElementById('editWorldPublic').checked
    };
    if (!data.name) { alert('Введите название'); return; }
    try {
        var r = await fetch(getAuthUrl('/api/worlds/' + editingWorldId), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var d = await r.json();
        if (d.success) {
            alert('Мир обновлён!');
            showPage('worlds');
        } else {
            alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    }
}

async function saveWorld() {
    if (!authToken) { alert('Войдите чтобы создать мир'); return; }
    var data = {
        name: document.getElementById('worldName').value.trim(),
        genre: document.getElementById('worldGenre').value.trim() || null,
        description: document.getElementById('worldDesc').value.trim() || null,
        setting: document.getElementById('worldSetting').value.trim() || null,
        rules: document.getElementById('worldRules').value.trim() || null,
        avatar: document.getElementById('worldAvatar').value.trim() || null,
        is_public: document.getElementById('worldPublic').checked
    };
    if (!data.name) { alert('Введите название'); return; }
    try {
        var r = await fetch(getAuthUrl('/api/worlds'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var d = await r.json();
        if (d.success) { alert('Мир создан!'); showPage('worlds'); }
        else alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
    } catch(e) { alert('Ошибка: ' + e.message); }
}

async function deleteWorld(id) {
    if (!confirm('Удалить мир?')) return;
    try {
        await fetch(getAuthUrl('/api/worlds/' + id), { method: 'DELETE' });
        loadWorlds();
    } catch(e) { alert('Ошибка удаления'); }
}

// ============================================
// ПЕРСОНЫ
// ============================================
async function loadPersonas() {
    if (!authToken) {
        document.getElementById('personasGrid').innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Войдите чтобы увидеть персон</div>';
        return;
    }
    try {
        var r = await fetch(getAuthUrl('/api/personas'));
        var personas = await r.json();
        var grid = document.getElementById('personasGrid');
        if (!personas || !personas.length) {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">У вас пока нет персон</div>';
            return;
        }
        grid.innerHTML = personas.map(function(p) {
            return `
                <div class="card">
                    <div class="avatar">${p.avatar ? '<img src="'+p.avatar+'">' : '◌'}</div>
                    <div class="name">${p.name} ${p.is_active ? '●' : ''}</div>
                    <div class="role">${p.age || 'Возраст не указан'}</div>
                    <div class="actions">
                        <button onclick="event.stopPropagation(); showEditPersona(${p.id})" style="background:rgba(48,76,47,0.3);">✏️ Редактировать</button>
                        ${!p.is_active ? '<button onclick="event.stopPropagation(); activatePersona('+p.id+')">Активировать</button>' : ''}
                        <button onclick="event.stopPropagation(); deletePersona(${p.id})" class="danger">Удалить</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch(e) { console.error(e); }
}

function showCreatePersona() {
    ['personaName','personaAge','personaAppearance','personaPersonality','personaBackstory','personaSkills','personaGoal','personaAvatar'].forEach(function(id) {
        document.getElementById(id).value = '';
    });
    document.getElementById('personaAvatarLabel').textContent = 'Или загрузить изображение';
    showPage('persona-create');
}

function showEditPersona(personaId) {
    editingPersonaId = personaId;
    showPage('persona-edit');
    fetch(getAuthUrl('/api/personas/' + personaId))
        .then(function(r) { return r.json(); })
        .then(function(persona) {
            if (persona.error) {
                alert(persona.error);
                showPage('personas');
                return;
            }
            document.getElementById('editPersonaName').value = persona.name || '';
            document.getElementById('editPersonaAge').value = persona.age || '';
            document.getElementById('editPersonaAppearance').value = persona.appearance || '';
            document.getElementById('editPersonaPersonality').value = persona.personality || '';
            document.getElementById('editPersonaBackstory').value = persona.backstory || '';
            document.getElementById('editPersonaSkills').value = persona.skills || '';
            document.getElementById('editPersonaGoal').value = persona.goal || '';
            document.getElementById('editPersonaAvatar').value = persona.avatar || '';
            document.getElementById('editPersonaAvatarLabel').textContent = persona.avatar ? '✓ Загружено' : 'Или загрузить изображение';
        })
        .catch(function(e) {
            alert('Ошибка загрузки персоны: ' + e.message);
            showPage('personas');
        });
}

async function updatePersona() {
    if (!authToken) { alert('Войдите чтобы редактировать персону'); return; }
    if (!editingPersonaId) { alert('Персона не выбрана'); return; }
    var data = {
        name: document.getElementById('editPersonaName').value.trim(),
        age: parseInt(document.getElementById('editPersonaAge').value) || null,
        appearance: document.getElementById('editPersonaAppearance').value.trim() || null,
        personality: document.getElementById('editPersonaPersonality').value.trim() || null,
        backstory: document.getElementById('editPersonaBackstory').value.trim() || null,
        skills: document.getElementById('editPersonaSkills').value.trim() || null,
        goal: document.getElementById('editPersonaGoal').value.trim() || null,
        avatar: document.getElementById('editPersonaAvatar').value.trim() || null
    };
    if (!data.name) { alert('Введите имя'); return; }
    try {
        var r = await fetch(getAuthUrl('/api/personas/' + editingPersonaId), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var d = await r.json();
        if (d.success) {
            alert('Персона обновлена!');
            showPage('personas');
        } else {
            alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    }
}

async function savePersona() {
    if (!authToken) { alert('Войдите чтобы создать персону'); return; }
    var data = {
        name: document.getElementById('personaName').value.trim(),
        age: parseInt(document.getElementById('personaAge').value) || null,
        appearance: document.getElementById('personaAppearance').value.trim() || null,
        personality: document.getElementById('personaPersonality').value.trim() || null,
        backstory: document.getElementById('personaBackstory').value.trim() || null,
        skills: document.getElementById('personaSkills').value.trim() || null,
        goal: document.getElementById('personaGoal').value.trim() || null,
        avatar: document.getElementById('personaAvatar').value.trim() || null
    };
    if (!data.name) { alert('Введите имя'); return; }
    try {
        var r = await fetch(getAuthUrl('/api/personas'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var d = await r.json();
        if (d.success) { alert('Персона создана!'); showPage('personas'); }
        else alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
    } catch(e) { alert('Ошибка: ' + e.message); }
}

async function activatePersona(id) {
    try {
        await fetch(getAuthUrl('/api/personas/' + id + '/activate'), { method: 'POST' });
        loadPersonas();
    } catch(e) { alert('Ошибка'); }
}

async function deletePersona(id) {
    if (!confirm('Удалить персону?')) return;
    try {
        await fetch(getAuthUrl('/api/personas/' + id), { method: 'DELETE' });
        loadPersonas();
    } catch(e) { alert('Ошибка удаления'); }
}

// ============================================
// ПАМЯТЬ
// ============================================
async function loadMemory() {
    if (!authToken) {
        document.getElementById('memoryGrid').innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Войдите чтобы увидеть память</div>';
        return;
    }
    try {
        var r = await fetch(getAuthUrl('/api/memory'));
        var memories = await r.json();
        var grid = document.getElementById('memoryGrid');
        if (!memories || !memories.length) {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Воспоминаний пока нет</div>';
            return;
        }
        grid.innerHTML = memories.map(function(m) {
            return `
                <div class="card">
                    <div class="avatar">◈</div>
                    <div class="name">${m.content.slice(0, 55)}${m.content.length > 55 ? '...' : ''}</div>
                    <div class="role">Важность: ${m.importance} | ${m.memory_type}</div>
                    <div class="actions">
                        <button onclick="deleteMemory(${m.id})" class="danger">Удалить</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch(e) { console.error(e); }
}

async function loadMemoryCharacters() {
    if (!authToken) return;
    try {
        var r = await fetch(getAuthUrl('/api/characters'));
        var chars = await r.json();
        var sel = document.getElementById('memoryCharacter');
        sel.innerHTML = '<option value="">Выбери персонажа</option>';
        chars.forEach(function(c) {
            sel.innerHTML += '<option value="' + c.id + '">' + c.name + '</option>';
        });
    } catch(e) {}
}

function showCreateMemory() {
    document.getElementById('memoryContent').value = '';
    document.getElementById('memoryImportance').value = '1.0';
    loadMemoryCharacters();
    showPage('memory-create');
}

async function saveMemory() {
    if (!authToken) { alert('Войдите чтобы создать воспоминание'); return; }
    var data = {
        content: document.getElementById('memoryContent').value.trim(),
        importance: parseFloat(document.getElementById('memoryImportance').value) || 1.0,
        memory_type: 'personal',
        character_id: parseInt(document.getElementById('memoryCharacter').value) || null
    };
    if (!data.content) { alert('Введите содержание'); return; }
    try {
        var r = await fetch(getAuthUrl('/api/memory'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var d = await r.json();
        if (d.success) { alert('Воспоминание сохранено!'); showPage('memory'); }
        else alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
    } catch(e) { alert('Ошибка: ' + e.message); }
}

async function deleteMemory(id) {
    if (!confirm('Удалить воспоминание?')) return;
    try {
        await fetch(getAuthUrl('/api/memory/' + id), { method: 'DELETE' });
        loadMemory();
    } catch(e) { alert('Ошибка удаления'); }
}

// ============================================
// ИСТОРИЯ ЧАТОВ
// ============================================

async function loadChats() {
    if (!authToken) {
        document.getElementById('chatHistoryGrid').innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Войдите чтобы увидеть историю чатов</div>';
        return;
    }

    try {
        const r = await fetch(getAuthUrl('/api/chat/sessions'));
        const sessions = await r.json();
        const grid = document.getElementById('chatHistoryGrid');

        if (!sessions || !sessions.length) {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">У вас пока нет чатов<br><span style="font-size:13px;color:#444;">Начните диалог с персонажем</span></div>';
            return;
        }

        grid.innerHTML = sessions.map(function(s) {
            const avatarHtml = s.avatar ? '<img src="'+s.avatar+'">' : '✦';
            const lastMsg = s.last_message.length > 60 ? s.last_message.slice(0, 60) + '...' : s.last_message;

            return `
                <div class="card" onclick="startChat(${s.character_id})" style="cursor:pointer;">
                    <div class="avatar">${avatarHtml}</div>
                    <div class="name">${s.character_name}</div>
                    <div class="role" style="font-size:12px; color:#666; margin-top:4px;">${s.last_message_time || 'Недавно'}</div>
                    <div style="font-size:13px; color:#888; margin-top:6px; font-style:italic; text-align:left; padding:0 4px;">"${lastMsg}"</div>
                    <div class="actions" style="margin-top:10px;">
                        <button onclick="event.stopPropagation(); startChat(${s.character_id})" style="background:rgba(48,76,47,0.3);">💬 Продолжить</button>
                    </div>
                </div>
            `;
        }).join('');

    } catch(e) {
        console.error('Ошибка загрузки чатов:', e);
        document.getElementById('chatHistoryGrid').innerHTML = '<div style="color:#ff4444;text-align:center;padding:40px;">Ошибка загрузки чатов</div>';
    }
}

// ============================================
// КОМНАТЫ
// ============================================
async function loadRooms() {
    if (!authToken) {
        document.getElementById('roomsGrid').innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Войдите чтобы увидеть комнаты</div>';
        return;
    }
    try {
        var r = await fetch(getAuthUrl('/api/rooms'));
        var rooms = await r.json();
        var grid = document.getElementById('roomsGrid');
        if (!rooms || !rooms.length) {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">У вас пока нет комнат</div>';
            return;
        }
        grid.innerHTML = rooms.map(function(r) {
            return `
                <div class="card">
                    <div class="avatar">⌂</div>
                    <div class="name">${r.name}</div>
                    <div class="role">${r.description || 'Без описания'}${r.members ? ' | Участников: '+r.members.length : ''}</div>
                    <div class="actions">
                        <button onclick="deleteRoom(${r.id})" class="danger">Удалить</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch(e) { console.error(e); }
}

function showCreateRoom() {
    document.getElementById('roomName').value = '';
    document.getElementById('roomDesc').value = '';
    showPage('room-create');
}

async function saveRoom() {
    if (!authToken) { alert('Войдите чтобы создать комнату'); return; }
    var data = {
        name: document.getElementById('roomName').value.trim(),
        description: document.getElementById('roomDesc').value.trim() || null
    };
    if (!data.name) { alert('Введите название'); return; }
    try {
        var r = await fetch(getAuthUrl('/api/rooms'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var d = await r.json();
        if (d.success) { alert('Комната создана!'); showPage('rooms'); }
        else alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
    } catch(e) { alert('Ошибка: ' + e.message); }
}

async function deleteRoom(id) {
    if (!confirm('Удалить комнату?')) return;
    try {
        await fetch(getAuthUrl('/api/rooms/' + id), { method: 'DELETE' });
        loadRooms();
    } catch(e) { alert('Ошибка удаления'); }
}

// ============================================
// ЛОРБУК
// ============================================
async function loadLore() {
    if (!authToken) {
        document.getElementById('loreGrid').innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Войдите чтобы увидеть лорбук</div>';
        return;
    }
    var search = document.getElementById('loreSearch')?.value || '';
    try {
        var url = getAuthUrl('/api/lore' + (search ? '&search=' + encodeURIComponent(search) : ''));
        var r = await fetch(url);
        var lore = await r.json();
        var grid = document.getElementById('loreGrid');
        if (!lore || !lore.length) {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:40px;">Записей пока нет</div>';
            return;
        }
        grid.innerHTML = lore.map(function(l) {
            return `
                <div class="card">
                    <div class="avatar">◈</div>
                    <div class="name">${l.title}</div>
                    <div class="role">${l.category || 'Без категории'}${l.character_id ? ' | привязано к персонажу' : ''}${l.world_id ? ' | привязано к миру' : ''}</div>
                    <div class="actions">
                        <button onclick="event.stopPropagation(); editLore(${l.id})" style="background:rgba(48,76,47,0.3);">✏️ Редактировать</button>
                        <button onclick="event.stopPropagation(); deleteLore(${l.id})" class="danger">Удалить</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch(e) { console.error(e); }
}

document.getElementById('loreSearch')?.addEventListener('input', function() {
    clearTimeout(loreSearchTimeout);
    loreSearchTimeout = setTimeout(loadLore, 400);
});

async function loadLoreSelects() {
    if (!authToken) return;
    try {
        var r1 = await fetch(getAuthUrl('/api/characters'));
        var chars = await r1.json();

        var selChar = document.getElementById('loreCharacter');
        if (selChar) {
            selChar.innerHTML = '<option value="">Без персонажа</option>';
            chars.forEach(function(c) {
                selChar.innerHTML += '<option value="' + c.id + '">' + c.name + '</option>';
            });
        }

        var selEditChar = document.getElementById('editLoreCharacter');
        if (selEditChar) {
            selEditChar.innerHTML = '<option value="">Без персонажа</option>';
            chars.forEach(function(c) {
                selEditChar.innerHTML += '<option value="' + c.id + '">' + c.name + '</option>';
            });
        }

        var r2 = await fetch(getAuthUrl('/api/worlds'));
        var worlds = await r2.json();

        var selWorld = document.getElementById('loreWorld');
        if (selWorld) {
            selWorld.innerHTML = '<option value="">Без мира</option>';
            worlds.forEach(function(w) {
                selWorld.innerHTML += '<option value="' + w.id + '">' + w.name + '</option>';
            });
        }

        var selEditWorld = document.getElementById('editLoreWorld');
        if (selEditWorld) {
            selEditWorld.innerHTML = '<option value="">Без мира</option>';
            worlds.forEach(function(w) {
                selEditWorld.innerHTML += '<option value="' + w.id + '">' + w.name + '</option>';
            });
        }

        var r3 = await fetch(getAuthUrl('/api/rooms'));
        var rooms = await r3.json();

        var selRoom = document.getElementById('loreRoom');
        if (selRoom) {
            selRoom.innerHTML = '<option value="">Без комнаты</option>';
            rooms.forEach(function(r) {
                selRoom.innerHTML += '<option value="' + r.id + '">' + r.name + '</option>';
            });
        }

        var selEditRoom = document.getElementById('editLoreRoom');
        if (selEditRoom) {
            selEditRoom.innerHTML = '<option value="">Без комнаты</option>';
            rooms.forEach(function(r) {
                selEditRoom.innerHTML += '<option value="' + r.id + '">' + r.name + '</option>';
            });
        }
    } catch(e) {
        console.error('Ошибка загрузки данных для лорбука:', e);
    }
}

function showCreateLore() {
    ['loreTitle','loreCategory','loreContent','loreTags'].forEach(function(id) {
        document.getElementById(id).value = '';
    });
    loadLoreSelects();
    showPage('lore-create');
}

async function saveLore() {
    if (!authToken) { alert('Войдите чтобы создать запись'); return; }
    var tags = document.getElementById('loreTags').value.split(',').map(function(t) { return t.trim(); }).filter(function(t) { return t; });
    var data = {
        title: document.getElementById('loreTitle').value.trim(),
        category: document.getElementById('loreCategory').value.trim() || null,
        content: document.getElementById('loreContent').value.trim(),
        tags: tags,
        character_id: parseInt(document.getElementById('loreCharacter').value) || null,
        world_id: parseInt(document.getElementById('loreWorld').value) || null,
        room_id: parseInt(document.getElementById('loreRoom').value) || null
    };
    if (!data.title) { alert('Введите заголовок'); return; }
    if (!data.content) { alert('Введите содержание'); return; }
    try {
        var r = await fetch(getAuthUrl('/api/lore'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        var d = await r.json();
        if (d.success) { alert('Запись создана!'); showPage('lore'); }
        else alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
    } catch(e) { alert('Ошибка: ' + e.message); }
}

async function deleteLore(id) {
    if (!confirm('Удалить запись?')) return;
    try {
        await fetch(getAuthUrl('/api/lore/' + id), { method: 'DELETE' });
        loadLore();
    } catch(e) { alert('Ошибка удаления'); }
}

// ============================================
// РЕДАКТИРОВАНИЕ ЛОРБУКА
// ============================================

async function editLore(loreId) {
    editingLoreId = loreId;
    showPage('lore-edit');

    try {
        const r = await fetch(getAuthUrl('/api/lore'));
        const lore = await r.json();
        const entry = lore.find(l => l.id === loreId);

        if (!entry) {
            alert('Запись не найдена');
            showPage('lore');
            return;
        }

        document.getElementById('editLoreId').value = entry.id;
        document.getElementById('editLoreTitle').value = entry.title || '';
        document.getElementById('editLoreCategory').value = entry.category || '';
        document.getElementById('editLoreContent').value = entry.content || '';
        document.getElementById('editLoreTags').value = (entry.tags || []).join(', ');

        await loadLoreSelects();

        if (entry.character_id) {
            document.getElementById('editLoreCharacter').value = entry.character_id;
        }
        if (entry.world_id) {
            document.getElementById('editLoreWorld').value = entry.world_id;
        }
        if (entry.room_id) {
            document.getElementById('editLoreRoom').value = entry.room_id;
        }

    } catch(e) {
        alert('Ошибка загрузки записи: ' + e.message);
        showPage('lore');
    }
}

async function updateLore() {
    if (!authToken) { alert('Войдите чтобы редактировать запись'); return; }

    const loreId = document.getElementById('editLoreId').value;
    if (!loreId) { alert('Запись не выбрана'); return; }

    const tags = document.getElementById('editLoreTags').value.split(',').map(function(t) {
        return t.trim();
    }).filter(function(t) {
        return t;
    });

    const data = {
        title: document.getElementById('editLoreTitle').value.trim(),
        category: document.getElementById('editLoreCategory').value.trim() || null,
        content: document.getElementById('editLoreContent').value.trim(),
        tags: tags,
        character_id: parseInt(document.getElementById('editLoreCharacter').value) || null,
        world_id: parseInt(document.getElementById('editLoreWorld').value) || null,
        room_id: parseInt(document.getElementById('editLoreRoom').value) || null
    };

    if (!data.title) { alert('Введите заголовок'); return; }
    if (!data.content) { alert('Введите содержание'); return; }

    try {
        const r = await fetch(getAuthUrl('/api/lore/' + loreId), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const d = await r.json();
        if (d.success) {
            alert('Запись обновлена!');
            showPage('lore');
            loadLore();
        } else {
            alert('Ошибка: ' + (d.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    }
}

// ============================================
// ПОПУЛЯРНЫЕ (ГЛАВНАЯ)
// ============================================
async function loadPopular() {
    try {
        var r = await fetch('/api/characters/public?limit=4');
        var data = await r.json();
        var chars = data.items || [];
        var grid = document.getElementById('popularGrid');
        if (chars && chars.length) {
            grid.innerHTML = chars.map(function(c) {
                return `
                    <div class="card" onclick="startChat(${c.id})" style="cursor:pointer;">
                        <div class="avatar">${c.avatar ? '<img src="'+c.avatar+'">' : '✦'}</div>
                        <div class="name">${c.name}</div>
                        <div class="role">${c.role || 'Без роли'}</div>
                    </div>
                `;
            }).join('');
        } else {
            grid.innerHTML = '<div style="color:#666;text-align:center;padding:20px;">Публичных персонажей пока нет</div>';
        }
    } catch(e) { console.error(e); }
}

// ============================================
// ОЧИСТКА ЧАТА (НАЧАТЬ ЗАНОВО)
// ============================================

async function clearChat() {
    if (!chatCharacterId) {
        alert('Выберите персонажа');
        return;
    }

    if (!confirm('⚠️ Вы уверены, что хотите начать чат заново?\n\nИстория будет сохранена, но текущий диалог очистится.')) {
        return;
    }

    try {
        const r = await fetch(getAuthUrl('/api/chat/' + chatCharacterId + '/clear'), {
            method: 'POST'
        });
        const data = await r.json();

        if (data.success) {
            const div = document.getElementById('chatMessages');
            div.innerHTML = '';
            chatGreetingSent = false;

            fetch(getAuthUrl('/api/characters'))
                .then(function(r) { return r.json(); })
                .then(function(chars) {
                    var char = chars.find(function(c) { return c.id === chatCharacterId; });
                    if (char && char.greeting) {
                        var msgId = 'msg_' + (++messageIdCounter);
                        addBotMessage('🔄 ' + char.greeting, msgId);
                        chatGreetingSent = true;
                    } else {
                        var msgId = 'msg_' + (++messageIdCounter);
                        addBotMessage('🔄 Новая сессия началась! Чем займемся?', msgId);
                    }
                })
                .catch(function(e) {
                    console.error('Ошибка загрузки персонажа:', e);
                    var msgId = 'msg_' + (++messageIdCounter);
                    addBotMessage('🔄 Новая сессия началась!', msgId);
                });

            const systemMsg = document.createElement('div');
            systemMsg.style.cssText = 'text-align:center; color:#666; font-size:12px; margin:10px 0; padding:6px; border-top:1px solid rgba(255,255,255,0.05); border-bottom:1px solid rgba(255,255,255,0.05);';
            systemMsg.textContent = '✦ Новая сессия началась ✦';
            div.prepend(systemMsg);

            div.scrollTop = div.scrollHeight;

        } else {
            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    }
}

// ============================================
// МОДАЛЬНОЕ ОКНО ВЫБОРА ПЕРСОНЫ
// ============================================

function openPersonaModal(callback) {
    console.log('✅ openPersonaModal вызван');

    if (!authToken) {
        alert('Войдите чтобы выбрать персону');
        return;
    }

    _personaModalCallback = callback;
    console.log('✅ _personaModalCallback сохранён');

    fetch(getAuthUrl('/api/personas'))
        .then(function(r) {
            console.log('✅ Ответ от сервера:', r.status);
            return r.json();
        })
        .then(function(personas) {
            console.log('✅ Получены персоны:', personas);
            var list = document.getElementById('personaModalList');
            if (!list) {
                console.error('❌ Нет элемента personaModalList');
                return;
            }

            if (!personas || !personas.length) {
                list.innerHTML = '<div style="color:#666;text-align:center;padding:20px;">У вас пока нет персон.<br>Создайте персону в разделе "Персоны"</div>';
                return;
            }

            list.innerHTML = personas.map(function(p) {
                var isActive = p.is_active ? '●' : '';
                var avatarHtml = p.avatar ? '<img src="'+p.avatar+'">' : '◌';
                return `
                    <div class="persona-option" onclick="selectPersona(${p.id})">
                        <div class="avatar">${avatarHtml}</div>
                        <div class="name">${p.name} ${isActive}</div>
                        <div class="check">➜</div>
                    </div>
                `;
            }).join('');

            document.getElementById('personaModal').style.display = 'flex';
        })
        .catch(function(e) {
            console.error('❌ Ошибка загрузки персон:', e);
            alert('Ошибка загрузки персон: ' + e.message);
        });
}

function selectPersona(personaId) {
    console.log('✅ selectPersona вызван, ID:', personaId);
    console.log('✅ _personaModalCallback:', _personaModalCallback);

    document.getElementById('personaModal').style.display = 'none';

    if (_personaModalCallback) {
        console.log('✅ Вызываем callback с ID:', personaId);
        var callback = _personaModalCallback;
        _personaModalCallback = null;
        callback(personaId);
    } else {
        console.log('❌ _personaModalCallback = null!');
        alert('Ошибка: callback не найден');
    }
}

function closePersonaModal() {
    console.log('✅ closePersonaModal вызван');
    document.getElementById('personaModal').style.display = 'none';

    if (_personaModalCallback) {
        console.log('✅ Отменяем выбор');
        var callback = _personaModalCallback;
        _personaModalCallback = null;
        callback(null);
    }
}

// ============================================
// СМЕНА ПЕРСОНЫ ИЗ ЧАТА
// ============================================

function openPersonaModalFromChat() {
    if (!chatCharacterId) {
        alert('Выберите персонажа');
        return;
    }

    openPersonaModal(function(personaId) {
        if (personaId) {
            localStorage.setItem('chat_persona_' + chatCharacterId, personaId);

            var sel = document.getElementById('chatPersonaSelect');
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].value == personaId) {
                    sel.value = personaId;
                    break;
                }
            }

            fetch(getAuthUrl('/api/personas'))
                .then(function(r) { return r.json(); })
                .then(function(personas) {
                    var persona = personas.find(function(p) { return p.id === personaId; });
                    if (persona) {
                        var div = document.getElementById('chatMessages');
                        div.innerHTML += '<div style="text-align:center; color:#666; font-size:13px; margin:12px 0;">✦ Теперь вы говорите как ' + persona.name + ' ✦</div>';
                        div.scrollTop = div.scrollHeight;
                    }
                });
        }
    });
}

// ============================================
// ГЕНЕРАЦИЯ ПЕРСОНАЖА
// ============================================

async function generateCharacter() {
    if (!authToken) {
        alert('Войдите чтобы создать персонажа');
        return;
    }

    const prompt = document.getElementById('generatePrompt').value.trim();
    if (!prompt) {
        alert('Введите описание персонажа');
        return;
    }

    const worldId = parseInt(document.getElementById('charWorld').value) || null;

    const btn = document.querySelector('#page-character-create .btn-primary');
    const originalText = btn.textContent;
    btn.textContent = '⏳ Генерация...';
    btn.disabled = true;

    try {
        const r = await fetch(getAuthUrl('/api/generate/character'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                world_id: worldId
            })
        });
        const data = await r.json();

        if (data.success) {
            alert('✨ Персонаж "' + data.name + '" создан!');
            loadCharacters();
            showPage('characters');
        } else {
            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// ============================================
// ГЕНЕРАЦИЯ МИРА
// ============================================

async function generateWorld() {
    if (!authToken) {
        alert('Войдите чтобы создать мир');
        return;
    }

    const prompt = document.getElementById('generateWorldPrompt').value.trim();
    if (!prompt) {
        alert('Введите описание мира');
        return;
    }

    const btn = document.querySelector('#page-world-create .btn-primary');
    const originalText = btn.textContent;
    btn.textContent = '⏳ Генерация...';
    btn.disabled = true;

    try {
        const r = await fetch(getAuthUrl('/api/generate/world'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt
            })
        });
        const data = await r.json();

        if (data.success) {
            alert('✨ Мир "' + data.name + '" создан!');
            loadWorlds();
            showPage('worlds');
        } else {
            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// ============================================
// ПЕРЕГЕНЕРАЦИЯ ПЕРСОНАЖА
// ============================================

async function regenerateCharacter() {
    if (!authToken) {
        alert('Войдите чтобы перегенерировать персонажа');
        return;
    }

    if (!editingCharacterId) {
        alert('Сначала открой персонажа на редактирование');
        return;
    }

    const prompt = document.getElementById('editGeneratePrompt').value.trim();
    if (!prompt) {
        alert('Введите описание для перегенерации');
        return;
    }

    const worldId = parseInt(document.getElementById('editCharWorld').value) || null;

    const btn = document.querySelector('#page-character-edit .btn-primary');
    const originalText = btn.textContent;
    btn.textContent = '⏳ Перегенерация...';
    btn.disabled = true;

    try {
        await fetch(getAuthUrl('/api/characters/' + editingCharacterId), {
            method: 'DELETE'
        });

        const r = await fetch(getAuthUrl('/api/generate/character'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                world_id: worldId
            })
        });
        const data = await r.json();

        if (data.success) {
            alert('🔄 Персонаж "' + data.name + '" перегенерирован!');
            loadCharacters();
            showPage('characters');
        } else {
            alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch(e) {
        alert('Ошибка: ' + e.message);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// ============================================
// ИСТОРИЯ ЧАТОВ (АРХИВ)
// ============================================

function showChatHistory() {
    if (!chatCharacterId) {
        alert('Выберите персонажа');
        return;
    }

    const modal = document.getElementById('chatHistoryModal');
    const list = document.getElementById('chatHistoryList');

    const savedChats = JSON.parse(localStorage.getItem('chat_history_' + chatCharacterId) || '[]');

    if (!savedChats.length) {
        list.innerHTML = '<div style="color:#666;text-align:center;padding:20px;">Нет сохранённых чатов</div>';
    } else {
        list.innerHTML = savedChats.map(function(chat, index) {
            const date = new Date(chat.timestamp).toLocaleString();
            const preview = chat.messages.length > 0 ? chat.messages[0].content.slice(0, 50) + '...' : 'Пустой чат';
            return `
                <div style="padding:12px 16px; background:rgba(255,255,255,0.03); border-radius:10px; border:1px solid rgba(255,255,255,0.05); display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:14px; color:#aaa;">${date}</div>
                        <div style="font-size:13px; color:#666;">"${preview}"</div>
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button onclick="loadSavedChat(${chatCharacterId}, ${index})" style="padding:4px 12px; background:rgba(48,76,47,0.3); border:none; border-radius:8px; color:#fff; cursor:pointer;">Загрузить</button>
                        <button onclick="deleteSavedChat(${chatCharacterId}, ${index})" style="padding:4px 12px; background:rgba(180,40,40,0.2); border:none; border-radius:8px; color:#ff4444; cursor:pointer;">Удалить</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    modal.style.display = 'flex';
}

function closeChatHistory() {
    document.getElementById('chatHistoryModal').style.display = 'none';
}

function saveCurrentChat() {
    if (!chatCharacterId) {
        alert('Выберите персонажа');
        return;
    }

    const messages = [];
    document.querySelectorAll('.msg-wrapper').forEach(function(wrapper) {
        const content = wrapper.querySelector('.msg-content');
        if (content) {
            const isBot = wrapper.dataset.isBot === 'true';
            messages.push({
                role: isBot ? 'assistant' : 'user',
                content: content.textContent
            });
        }
    });

    if (!messages.length) {
        alert('Чат пуст, нечего сохранять');
        return;
    }

    const chatData = {
        timestamp: Date.now(),
        messages: messages
    };

    const saved = JSON.parse(localStorage.getItem('chat_history_' + chatCharacterId) || '[]');
    saved.push(chatData);
    localStorage.setItem('chat_history_' + chatCharacterId, JSON.stringify(saved));

    alert('✅ Чат сохранён в историю!');
}

function loadSavedChat(characterId, index) {
    const saved = JSON.parse(localStorage.getItem('chat_history_' + characterId) || '[]');
    if (!saved[index]) {
        alert('Чат не найден');
        return;
    }

    if (!confirm('Загрузить этот чат? Текущий чат будет заменён.')) {
        return;
    }

    const chat = saved[index];
    const div = document.getElementById('chatMessages');
    div.innerHTML = '';
    chatGreetingSent = true;

    chat.messages.forEach(function(msg) {
        if (msg.role === 'user') {
            addUserMessage(msg.content);
        } else {
            addBotMessage(msg.content);
        }
    });

    closeChatHistory();
    alert('✅ Чат загружен!');
}

function deleteSavedChat(characterId, index) {
    if (!confirm('Удалить этот сохранённый чат?')) {
        return;
    }

    const saved = JSON.parse(localStorage.getItem('chat_history_' + characterId) || '[]');
    saved.splice(index, 1);
    localStorage.setItem('chat_history_' + characterId, JSON.stringify(saved));
    showChatHistory();
}

// ============================================
// ЗАПУСК
// ============================================
loadPopular();
if (authToken) loadProfile();
console.log('H.Y.G. Portal loaded');
console.log('User:', currentUser || 'Not logged in');
</script>
</body>
</html>"""

# ============================================
# ФУНКЦИЯ ДЛЯ АВТО-СУММАРИЗАЦИИ
# ============================================

def summarize_chat_history(messages):
    """Сжимает историю чата в краткий пересказ."""
    if len(messages) < 50:
        return None

    # Берем последние 50 сообщений (исключаем system)
    chat_messages = [m for m in messages if m['role'] != 'system']
    recent = chat_messages[-50:]

    # Формируем текст для сжатия
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

    try:
        # Просим AI сжать
        response = openai.chat.completions.create(
            model="deepseek/deepseek-v4-flash",
            messages=[
                {"role": "system", "content": "Ты — помощник, который сжимает историю диалога в 3-5 предложений, сохраняя суть, ключевые события и эмоциональный фон."},
                {"role": "user", "content": f"Сожми эту историю:\n\n{history_text}"}
            ],
            max_tokens=200,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка суммаризации: {e}")
        return None

# ============================================
# ФУНКЦИИ ДЛЯ ЛИЧНОЙ ПАМЯТИ
# ============================================

def save_user_fact(user_id: int, fact: str, category: str = "general"):
    """Сохраняет факт о пользователе в личную память."""
    with SessionLocal() as db:
        existing = db.query(UserMemory).filter(
            UserMemory.user_id == user_id,
            UserMemory.fact == fact
        ).first()
        if not existing:
            memory = UserMemory(
                user_id=user_id,
                fact=fact,
                category=category
            )
            db.add(memory)
            db.commit()

def load_user_memories(user_id: int, limit: int = 10):
    """Загружает последние факты о пользователе."""
    with SessionLocal() as db:
        memories = db.query(UserMemory).filter(
            UserMemory.user_id == user_id
        ).order_by(UserMemory.created_at.desc()).limit(limit).all()
        return [m.fact for m in memories]
        
        # ============================================
# ФУНКЦИИ ДЛЯ ИЕРАРХИЧЕСКОЙ ПАМЯТИ
# ============================================

def save_hierarchical_memory(
    user_id: int,
    content: str,
    memory_type: str = "short",
    importance: float = 1.0,
    category: str = "general",
    character_id: int = None
) -> int:
    """Сохраняет память с иерархией"""
    with SessionLocal() as db:
        memory = MemoryHierarchy(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            category=category,
            character_id=character_id
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        
        # Если важность высокая и это не долгосрочная память - консолидируем
        if importance > 1.5 and memory_type != "long":
            consolidate_memory(user_id, memory.id)
        
        return memory.id

def get_relevant_memory(
    user_id: int,
    context: str = None,
    character_id: int = None,
    limit: int = 10
):
    """Получает релевантную память с учетом иерархии"""
    with SessionLocal() as db:
        # Сначала берем долгосрочную память (самая важная)
        long_memory = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.user_id == user_id,
            MemoryHierarchy.memory_type == "long",
            MemoryHierarchy.is_forgotten == False
        )
        if character_id:
            long_memory = long_memory.filter(MemoryHierarchy.character_id == character_id)
        long_memory = long_memory.order_by(MemoryHierarchy.importance.desc()).limit(limit // 2).all()
        
        # Затем среднесрочную
        medium_memory = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.user_id == user_id,
            MemoryHierarchy.memory_type == "medium",
            MemoryHierarchy.is_forgotten == False
        )
        if character_id:
            medium_memory = medium_memory.filter(MemoryHierarchy.character_id == character_id)
        medium_memory = medium_memory.order_by(
            MemoryHierarchy.last_accessed.desc(),
            MemoryHierarchy.importance.desc()
        ).limit(limit // 3).all()
        
        # Затем краткосрочную (самая свежая)
        short_memory = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.user_id == user_id,
            MemoryHierarchy.memory_type == "short",
            MemoryHierarchy.is_forgotten == False
        )
        if character_id:
            short_memory = short_memory.filter(MemoryHierarchy.character_id == character_id)
        short_memory = short_memory.order_by(
            MemoryHierarchy.last_accessed.desc()
        ).limit(limit - len(long_memory) - len(medium_memory)).all()
        
        # Объединяем
        all_memory = long_memory + medium_memory + short_memory
        
        # Обновляем время доступа
        for mem in all_memory:
            mem.last_accessed = datetime.utcnow()
            mem.access_count += 1
        db.commit()
        
        return [{
            "id": m.id,
            "content": m.content,
            "type": m.memory_type,
            "importance": m.importance,
            "category": m.category
        } for m in all_memory]

def consolidate_memory(user_id: int, memory_id: int):
    """Консолидирует важную память в долгосрочную"""
    with SessionLocal() as db:
        memory = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.id == memory_id,
            MemoryHierarchy.user_id == user_id
        ).first()
        
        if not memory or memory.memory_type == "long":
            return
        
        # Проверяем, есть ли похожие воспоминания
        similar = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.user_id == user_id,
            MemoryHierarchy.memory_type == "long",
            MemoryHierarchy.content.ilike(f"%{memory.content[:50]}%")
        ).first()
        
        if similar:
            # Обновляем существующее
            similar.content = memory.content + "\n\n[Обновлено] " + similar.content
            similar.importance = max(similar.importance, memory.importance)
            db.commit()
            # Удаляем исходное
            db.delete(memory)
            db.commit()
        else:
            # Превращаем в долгосрочное
            memory.memory_type = "long"
            memory.importance = min(memory.importance * 1.5, 2.0)
            db.commit()

def forget_memory(user_id: int, days_threshold: int = 30):
    """Механизм забывания - удаляет неиспользуемую память"""
    with SessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(days=days_threshold)
        
        # Короткая память забывается быстрее
        short_memory = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.user_id == user_id,
            MemoryHierarchy.memory_type == "short",
            MemoryHierarchy.last_accessed < cutoff,
            MemoryHierarchy.importance < 0.5
        ).delete()
        
        # Средняя память - реже
        medium_cutoff = datetime.utcnow() - timedelta(days=days_threshold * 2)
        medium_memory = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.user_id == user_id,
            MemoryHierarchy.memory_type == "medium",
            MemoryHierarchy.last_accessed < medium_cutoff,
            MemoryHierarchy.importance < 0.3
        ).update({"is_forgotten": True})
        
        db.commit()
        
        return short_memory + medium_memory

def summarize_memory_batch(user_id: int):
    """Пакетная суммаризация старых воспоминаний"""
    with SessionLocal() as db:
        # Берем старые короткие воспоминания (больше 7 дней)
        cutoff = datetime.utcnow() - timedelta(days=7)
        old_memories = db.query(MemoryHierarchy).filter(
            MemoryHierarchy.user_id == user_id,
            MemoryHierarchy.memory_type.in_(["short", "medium"]),
            MemoryHierarchy.created_at < cutoff,
            MemoryHierarchy.is_forgotten == False
        ).order_by(MemoryHierarchy.created_at).limit(20).all()
        
        if len(old_memories) < 5:
            return None
        
        # Группируем по категориям
        categories = {}
        for mem in old_memories:
            if mem.category not in categories:
                categories[mem.category] = []
            categories[mem.category].append(mem)
        
        summaries = []
        for category, memories in categories.items():
            if len(memories) < 3:
                continue
            
            memory_text = "\n".join([f"- {m.content}" for m in memories])
            
            try:
                response = openai.chat.completions.create(
                    model="deepseek/deepseek-v4-flash",
                    messages=[
                        {"role": "system", "content": f"Сожми эти воспоминания категории '{category}' в 2-3 предложения, сохраняя суть:"},
                        {"role": "user", "content": memory_text}
                    ],
                    max_tokens=150,
                    temperature=0.5
                )
                summary = response.choices[0].message.content
                
                # Сохраняем консолидированную память
                consolidated = MemoryConsolidation(
                    user_id=user_id,
                    summary=summary,
                    source_memory_ids=[m.id for m in memories],
                    is_active=True
                )
                db.add(consolidated)
                
                # Помечаем исходные как забытые
                for mem in memories:
                    mem.is_forgotten = True
                
                db.commit()
                summaries.append(summary)
                
            except Exception as e:
                print(f"Ошибка суммаризации: {e}")
        
        return summaries
        
# ============================================
# ЗАПУСК
# ============================================
# ============================================
# API ЭНДПОИНТЫ ДЛЯ ИЕРАРХИЧЕСКОЙ ПАМЯТИ
# ============================================

@app.get("/api/memory/hierarchy")
async def get_hierarchical_memory(
    token: str,
    character_id: Optional[int] = None,
    limit: int = 10
):
    """Получить иерархическую память"""
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    memories = get_relevant_memory(user.id, character_id=character_id, limit=limit)
    return memories

@app.post("/api/memory/hierarchy")
async def save_hierarchical_memory_endpoint(
    token: str,
    content: str,
    memory_type: str = "short",
    importance: float = 1.0,
    category: str = "general",
    character_id: Optional[int] = None
):
    """Сохранить иерархическую память"""
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    memory_id = save_hierarchical_memory(
        user_id=user.id,
        content=content,
        memory_type=memory_type,
        importance=importance,
        category=category,
        character_id=character_id
    )
    
    return {"success": True, "memory_id": memory_id}

@app.post("/api/memory/forget")
async def forget_old_memories(token: str, days: int = 30):
    """Забыть старые воспоминания"""
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    forgotten_count = forget_memory(user.id, days)
    return {"success": True, "forgotten_count": forgotten_count}

@app.post("/api/memory/consolidate")
async def consolidate_memories(token: str):
    """Сконсолидировать воспоминания"""
    user = get_user_by_token(token)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, 401)
    
    summaries = summarize_memory_batch(user.id)
    return {"success": True, "summaries": summaries or []}
    
    # ============================================
# СОЗДАНИЕ НОВЫХ ТАБЛИЦ
# ============================================

try:
    # Создаем новые таблицы для иерархической памяти
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы иерархической памяти созданы")
except Exception as e:
    print(f"❌ Ошибка создания таблиц: {e}")
    
@app.get("/")
@app.get("/{path:path}")
async def serve_frontend():
    return HTMLResponse(HTML)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
