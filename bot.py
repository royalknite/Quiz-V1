
"""
╔══════════════════════════════════════════════════════════════════════════╗
║                      QUIZBOT — Scheduler Bot (PTB)                       ║
║                                                                          ║
║  High-performance quiz scheduler built with python-telegram-bot.         ║
║  Handles concurrent quiz sessions, poll tracking, leaderboards,          ║
║  result comparisons, and scheduled quiz dispatch.                        ║
║                                                                          ║
║  Sponsored by  : Qzio — qzio.in                                          ║
║  Developed by  : devgagan — devgagan.in                                  ║
║  Version       : 2.2.0                                                   ║
║  License       : MIT                                                     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import time
import random
import re
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Indian Standard Time — used for /schedule so users always think in local IST,
# regardless of where the bot is hosted (Render/VPS/Replit may be on UTC).
IST = ZoneInfo("Asia/Kolkata")

def now_ist() -> datetime:
    """Naive datetime representing the current moment in IST.
    
    We store and compare scheduled_time as naive IST datetimes so the value the
    user sees in their group chat (e.g. 14:30) is exactly what's stored in DB
    and exactly what the scheduler ticks against.
    """
    return datetime.now(IST).replace(tzinfo=None)
from typing import Dict, Any, Optional, List, Set
from collections import deque, defaultdict
from contextlib import asynccontextmanager
import logging
from logging.handlers import RotatingFileHandler
import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ConnectionFailure, OperationFailure

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.constants import ParseMode, ChatType
from telegram.ext import Application, CommandHandler, PollAnswerHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError, RetryAfter, TimedOut, NetworkError

try:
    from c import generate_quiz_html, generate_analysis_html
except ImportError:
    generate_quiz_html = None
    generate_analysis_html = None

try:
    from pdf_report import generate_mock_test_pdf
except ImportError:
    generate_mock_test_pdf = None


async def send_quiz_result_pdf(quiz_data, chat_id, context, protect_content: bool = False,
                               leaderboard=None, shuffle: bool = False):
    """Generate and send the post-quiz report PDF.

    Includes leaderboard (if provided) and Q&A with answers/explanations.
    Falls back gracefully if the PDF generator is unavailable.
    """
    if not generate_mock_test_pdf:
        return False

    import re as _re
    from unidecode import unidecode as _unidecode

    quiz_name = quiz_data.get("quiz_name") or "quiz"
    safe_name = _re.sub(r"[^A-Za-z0-9_-]", "", _unidecode(quiz_name).replace(" ", "_"))[:80] or "quiz"
    quiz_id = quiz_data.get("question_set_id") or quiz_data.get("quiz_id") or "QUIZ"

    os.makedirs("quiz_results", exist_ok=True)
    out_path = f"quiz_results/{chat_id}_{quiz_id}_{int(time.time())}_{safe_name}.pdf"

    try:
        await asyncio.to_thread(
            generate_mock_test_pdf, quiz_data, out_path,
            "@AIpha_World", leaderboard or [], shuffle
        )
    except Exception as e:
        logger.error(f"PDF generation failed for chat {chat_id}: {e}", exc_info=True)
        return False

    try:
        total_q = len(quiz_data.get("questions") or [])
        with open(out_path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=f"QuizReport_{safe_name}.pdf",
                caption=(
                    f"📄 *{quiz_name}*\n"
                    f"❓ Questions: {total_q}\n"
                    f"📊 Quiz Report — Powered by Quiz Bot"
                ),
                protect_content=bool(protect_content),
            )
        return True
    except Exception as e:
        logger.error(f"Failed to send PDF to chat {chat_id}: {e}", exc_info=True)
        return False
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN  = os.getenv("BOT_TOKEN", "")   # PTB scheduler bot token (shared with main bot)
MONGO_URI_1 = os.getenv("MONGO_URI", "")
MONGO_URI_2 = os.getenv("MONGO_URI_2", "")

MAX_CONCURRENT_POLLS = 5000  # Max polls per chat simultaneously
POLL_SEND_DELAY = 0.1  # Delay between polls (anti-flood)
DB_BATCH_SIZE = 100  # Batch size for DB operations
CONNECTION_POOL_SIZE = 100  # MongoDB connection pool
MAX_RETRIES = 3  # Retry attempts for failed operations
RETRY_DELAY = 1.0  # Base delay for exponential backoff
RATE_LIMIT_WINDOW = 5  # Rate limit window in seconds
RATE_LIMIT_MAX_REQUESTS = 500  # Max requests per window per user
SESSION_CLEANUP_INTERVAL = 3600  # Clean old sessions every hour
SESSION_TIMEOUT = 3600  # Session expires after 1 hour of inactivity
SCHEDULED_QUIZ_CHECK_INTERVAL = 60  # Check scheduled quizzes every 60 seconds
POLL_QUESTION_MAX_LENGTH = 300
POLL_OPTION_MAX_LENGTH = 95
POLL_EXPLANATION_MAX_LENGTH = 200
TRIM_LENGTH = 80

# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════

def setup_logging():
    """Setup production-grade logging with rotation"""
    os.makedirs("logs", exist_ok=True)
    

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    

    file_handler = RotatingFileHandler(
        'logs/quiz_bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    

    error_handler = RotatingFileHandler(
        'logs/quiz_bot_errors.log',
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION POOL MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class DatabaseManager:
    """
    Enterprise-grade database manager with:
    - Connection pooling
    - Automatic failover
    - Retry logic with exponential backoff
    - Health monitoring
    """
    
    def __init__(self):
        self.clients: List[MongoClient] = []
        self.collections: Dict[str, Any] = {}
        self.health_status: Dict[str, bool] = {}
        self.last_health_check: float = 0
        self.health_check_interval: float = 30.0  # Check every 30 seconds
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize database connections with connection pooling"""
        try:
            logger.info("Initializing database connections...")
            

            client1 = MongoClient(
                MONGO_URI_1,
                maxPoolSize=CONNECTION_POOL_SIZE,
                minPoolSize=10,
                maxIdleTimeMS=30000,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=20000,
                retryWrites=True,
                retryReads=True
            )
            
            db1 = client1["quiz_bot"]
            self.collections['users_1'] = db1["quiz_users"]
            self.collections['questions_1'] = db1["questions"]
            self.collections['auth_1'] = db1["auth_chats"]
            self.collections['scheduled_1'] = db1["scheduled_quizzes"]
            self.clients.append(client1)
            self.health_status['db1'] = True
            
            logger.info("✓ Primary database connected")
            

            try:
                client2 = MongoClient(
                    MONGO_URI_2,
                    maxPoolSize=CONNECTION_POOL_SIZE,
                    minPoolSize=10,
                    maxIdleTimeMS=30000,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=20000
                )
                
                db2 = client2["quiz_bot"]
                self.collections['users_2'] = db2["quiz_users"]
                self.collections['questions_2'] = db2["questions"]
                self.collections['auth_2'] = db2["auth_chats"]
                self.collections['scheduled_2'] = db2["scheduled_quizzes"]
                self.clients.append(client2)
                self.health_status['db2'] = True
                
                logger.info("✓ Secondary database connected")
            except Exception as e:
                logger.warning(f"Secondary database unavailable: {e}")
                self.health_status['db2'] = False
            

            await self.health_check()
            logger.info("✓ Database initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize databases: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check database health"""
        current_time = time.time()
        

        if current_time - self.last_health_check < self.health_check_interval:
            return all(self.health_status.values())
        
        async with self._lock:
            self.last_health_check = current_time
            
            for idx, client in enumerate(self.clients, 1):
                db_key = f'db{idx}'
                try:

                    client.admin.command('ping')
                    self.health_status[db_key] = True
                except Exception as e:
                    logger.error(f"Database {db_key} health check failed: {e}")
                    self.health_status[db_key] = False
        
        return any(self.health_status.values())
    
    async def find_one(self, collection_type: str, query: Dict, retry: int = 0) -> Optional[Dict]:
        """Find one document with automatic failover"""
        try:

            if self.health_status.get('db1', False):
                result = self.collections[f'{collection_type}_1'].find_one(query)
                if result:
                    return result
            

            if self.health_status.get('db2', False):
                result = self.collections[f'{collection_type}_2'].find_one(query)
                if result:
                    return result
            
            return None
            
        except PyMongoError as e:
            logger.error(f"Database error in find_one: {e}")
            
            if retry < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (2 ** retry))
                await self.health_check()
                return await self.find_one(collection_type, query, retry + 1)
            
            raise
    
    async def insert_one(self, collection_type: str, document: Dict, retry: int = 0) -> bool:
        """Insert one document with retry logic"""
        try:
            if self.health_status.get('db1', False):
                self.collections[f'{collection_type}_1'].insert_one(document)
                return True
            
            if self.health_status.get('db2', False):
                self.collections[f'{collection_type}_2'].insert_one(document)
                return True
            
            return False
            
        except PyMongoError as e:
            logger.error(f"Database error in insert_one: {e}")
            
            if retry < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (2 ** retry))
                await self.health_check()
                return await self.insert_one(collection_type, document, retry + 1)
            
            return False
    
    async def update_one(self, collection_type: str, query: Dict, update: Dict, retry: int = 0) -> bool:
        """Update one document with retry logic"""
        try:
            if self.health_status.get('db1', False):
                self.collections[f'{collection_type}_1'].update_one(query, update)
                return True
            
            if self.health_status.get('db2', False):
                self.collections[f'{collection_type}_2'].update_one(query, update)
                return True
            
            return False
            
        except PyMongoError as e:
            logger.error(f"Database error in update_one: {e}")
            
            if retry < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (2 ** retry))
                await self.health_check()
                return await self.update_one(collection_type, query, update, retry + 1)
            
            return False
    
    async def delete_one(self, collection_type: str, query: Dict, retry: int = 0) -> bool:
        """Delete one document with retry logic"""
        try:
            if self.health_status.get('db1', False):
                self.collections[f'{collection_type}_1'].delete_one(query)
                return True
            
            if self.health_status.get('db2', False):
                self.collections[f'{collection_type}_2'].delete_one(query)
                return True
            
            return False
            
        except PyMongoError as e:
            logger.error(f"Database error in delete_one: {e}")
            
            if retry < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (2 ** retry))
                await self.health_check()
                return await self.delete_one(collection_type, query, retry + 1)
            
            return False
    
    async def find(self, collection_type: str, query: Dict, retry: int = 0) -> List[Dict]:
        """Find multiple documents with automatic failover"""
        try:

            if self.health_status.get('db1', False):
                cursor = self.collections[f'{collection_type}_1'].find(query)
                return list(cursor)
            

            if self.health_status.get('db2', False):
                cursor = self.collections[f'{collection_type}_2'].find(query)
                return list(cursor)
            
            return []
            
        except PyMongoError as e:
            logger.error(f"Database error in find: {e}")
            
            if retry < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * (2 ** retry))
                await self.health_check()
                return await self.find(collection_type, query, retry + 1)
            
            raise
    
    async def bulk_insert(self, collection_type: str, documents: List[Dict]) -> int:
        """Bulk insert with batching for performance"""
        inserted_count = 0
        
        try:

            for i in range(0, len(documents), DB_BATCH_SIZE):
                batch = documents[i:i + DB_BATCH_SIZE]
                
                try:
                    if self.health_status.get('db1', False):
                        result = self.collections[f'{collection_type}_1'].insert_many(batch, ordered=False)
                        inserted_count += len(result.inserted_ids)
                except Exception as e:
                    logger.error(f"Batch insert failed: {e}")
            
            return inserted_count
            
        except Exception as e:
            logger.error(f"Bulk insert error: {e}")
            return inserted_count
    
    def close(self):
        """Close all database connections"""
        for client in self.clients:
            try:
                client.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

db_manager = DatabaseManager()

# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """
    Token bucket algorithm for rate limiting
    """
    
    def __init__(self):
        self.buckets: Dict[int, deque] = defaultdict(lambda: deque(maxlen=RATE_LIMIT_MAX_REQUESTS))
        self._lock = asyncio.Lock()
        self.total_requests = 0
        self.total_blocked = 0
    
    async def check_rate_limit(self, user_id: int) -> bool:
        """Check if user exceeded rate limit"""
        async with self._lock:
            current_time = time.time()
            bucket = self.buckets[user_id]
            

            while bucket and bucket[0] < current_time - RATE_LIMIT_WINDOW:
                bucket.popleft()
            

            self.total_requests += 1
            
            if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
                self.total_blocked += 1
                logger.warning(f"Rate limit exceeded for user {user_id} (total blocked: {self.total_blocked})")
                return False
            

            bucket.append(current_time)
            return True
    
    async def cleanup_old_entries(self):
        """Clean up old rate limit entries"""
        async with self._lock:
            current_time = time.time()
            users_to_remove = []
            
            for user_id, bucket in self.buckets.items():

                while bucket and bucket[0] < current_time - RATE_LIMIT_WINDOW:
                    bucket.popleft()
                

                if not bucket:
                    users_to_remove.append(user_id)
            

            for user_id in users_to_remove:
                del self.buckets[user_id]
            
            if users_to_remove:
                logger.debug(f"Cleaned up {len(users_to_remove)} empty rate limit buckets")
    
    def get_stats(self) -> Dict[str, int]:
        """Get rate limiter statistics"""
        return {
            'active_buckets': len(self.buckets),
            'total_requests': self.total_requests,
            'total_blocked': self.total_blocked,
        }

rate_limiter = RateLimiter()

# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════

class SessionManager:
    """
    Simplified session manager with linear quiz flow per chat
    """
    
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self.last_activity: Dict[int, float] = {}
        self.active_quiz_tasks: Dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(self, chat_id: int, data: Dict[str, Any]):
        """Create new session"""
        async with self._lock:
            self.sessions[chat_id] = data
            self.last_activity[chat_id] = time.time()
            logger.info(f"Session created for chat {chat_id}")
    
    async def get_session(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get session and update activity"""
        async with self._lock:
            if chat_id in self.sessions:
                self.last_activity[chat_id] = time.time()
                return self.sessions[chat_id]
            return None
    
    async def update_session(self, chat_id: int, updates: Dict[str, Any]):
        """Update session data"""
        async with self._lock:
            if chat_id in self.sessions:
                self.sessions[chat_id].update(updates)
                self.last_activity[chat_id] = time.time()
    
    async def delete_session(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Delete session and return data"""
        async with self._lock:
            session = self.sessions.pop(chat_id, None)
            self.last_activity.pop(chat_id, None)
            

            if chat_id in self.active_quiz_tasks:
                task = self.active_quiz_tasks.pop(chat_id)
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled quiz task for chat {chat_id}")
            
            if session:
                logger.info(f"Session deleted for chat {chat_id}")
            return session
    
    async def register_quiz_task(self, chat_id: int, task: asyncio.Task):
        """Register a quiz task for a chat"""
        async with self._lock:

            if chat_id in self.active_quiz_tasks:
                old_task = self.active_quiz_tasks[chat_id]
                if not old_task.done():
                    old_task.cancel()
                    logger.info(f"Cancelled previous quiz task for chat {chat_id}")
            
            self.active_quiz_tasks[chat_id] = task
    
    async def cancel_quiz_task(self, chat_id: int):
        """Cancel quiz task for a chat"""
        async with self._lock:
            if chat_id in self.active_quiz_tasks:
                task = self.active_quiz_tasks.pop(chat_id)
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled quiz task for chat {chat_id}")
    
    async def cleanup_old_sessions(self):
        """Remove inactive sessions"""
        async with self._lock:
            current_time = time.time()
            to_remove = []
            
            for chat_id, last_time in self.last_activity.items():
                if current_time - last_time > SESSION_TIMEOUT:
                    to_remove.append(chat_id)
            
            for chat_id in to_remove:
                self.sessions.pop(chat_id, None)
                self.last_activity.pop(chat_id, None)
                

                if chat_id in self.active_quiz_tasks:
                    task = self.active_quiz_tasks.pop(chat_id)
                    if not task.done():
                        task.cancel()
                
                logger.info(f"Cleaned up inactive session: {chat_id}")
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} inactive sessions")
    
    def get_active_count(self) -> int:
        """Get count of active sessions"""
        return len(self.sessions)
    
    def get_stats(self) -> Dict[str, int]:
        """Get session statistics"""
        active_tasks = sum(1 for t in self.active_quiz_tasks.values() if not t.done())
        return {
            'active_sessions': len(self.sessions),
            'active_quiz_tasks': active_tasks,
        }

session_manager = SessionManager()

# ═══════════════════════════════════════════════════════════════════════════
# SCHEDULED QUIZ MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class ScheduledQuizManager:
    """Manages scheduled quizzes"""
    
    def __init__(self, application: Application):
        self.application = application
        self.running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the scheduled quiz manager"""
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._check_scheduled_quizzes())
        logger.info("Scheduled quiz manager started")
    
    async def stop(self):
        """Stop the scheduled quiz manager"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduled quiz manager stopped")
    
    async def _check_scheduled_quizzes(self):
        """Check for scheduled quizzes that need to start"""
        while self.running:
            try:
                await asyncio.sleep(SCHEDULED_QUIZ_CHECK_INTERVAL)
                
                current_time = now_ist()
                logger.debug(f"Checking scheduled quizzes at {current_time}")
                

                scheduled_quizzes = await db_manager.find("scheduled", {
                    "scheduled_time": {"$lte": current_time},
                    "status": "pending"
                })
                
                for quiz in scheduled_quizzes:
                    try:
                        logger.info(f"Starting scheduled quiz: {quiz['quiz_id']} for chat {quiz['chat_id']}")
                        

                        await db_manager.update_one("scheduled", 
                            {"_id": quiz["_id"]},
                            {"$set": {"status": "running"}}
                        )
                        

                        from telegram import Chat, User
                        
                        chat = Chat(id=quiz["chat_id"], type="group", title="Scheduled Quiz")
                        user = User(id=quiz["scheduled_by"], is_bot=False, first_name="Scheduler")
                        

                        class MockUpdate:
                            def __init__(self):
                                self.effective_chat = chat
                                self.effective_user = user
                                self.message = None
                                self.callback_query = None
                        
                        mock_update = MockUpdate()
                        

                        from telegram.ext import ContextTypes
                        context = ContextTypes.DEFAULT_TYPE(self.application)
                        

                        quiz_data = await db_manager.find_one("questions", {"question_set_id": quiz["quiz_id"]})
                        if not quiz_data:
                            logger.error(f"Quiz {quiz['quiz_id']} not found")
                            continue
                        

                        await safe_send_message(
                            context, quiz["chat_id"],
                            f"⏰ *Scheduled Quiz Starting Now!*\n\n"
                            f"📝 Quiz: {escape_markdown(quiz_data.get('quiz_name', 'Unnamed Quiz'))}\n"
                            f"🕐 Scheduled by: <code>{quiz['scheduled_by']}</code>\n"
                            f"⏰ Scheduled time: {quiz['scheduled_time'].strftime('%Y-%m-%d %H:%M:%S')}",
                            parse_mode=ParseMode.HTML
                        )
                        

                        skip_count = quiz.get("skip_count", 0)
                        

                        existing_session = await session_manager.get_session(quiz["chat_id"])
                        if existing_session:
                            await safe_send_message(
                                context, quiz["chat_id"],
                                "⚠️ Another quiz is already running. Skipping scheduled quiz."
                            )
                            continue
                        

                        await start_group_quiz(
                            mock_update, context, 
                            quiz["quiz_id"], skip_count,
                            scheduled=True
                        )
                        

                        await db_manager.delete_one("scheduled", {"_id": quiz["_id"]})
                        
                    except Exception as e:
                        logger.error(f"Error starting scheduled quiz {quiz['quiz_id']}: {e}")

                        await db_manager.update_one("scheduled",
                            {"_id": quiz["_id"]},
                            {"$set": {"status": "failed", "error": str(e)}}
                        )
                
            except Exception as e:
                logger.error(f"Error in scheduled quiz check: {e}")

scheduled_quiz_manager = None

# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def trim_text(text: str, max_length: int) -> str:
    """Trim text to max length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 1] + "…"


# Matches inline Roman numeral statement labels (I. II. III. etc.) that appear
# after sentence-ending punctuation without a preceding newline, e.g.:
#   "...है? I. नरेगा..." → "...है?\nI. नरेगा..."
#   "...था। II. इसे..."  → "...था।\nII. इसे..."
_STMT_NEWLINE_RE = re.compile(
    r'([?।!.][ \t]+)'               # sentence-ending punctuation + whitespace
    r'((?:I{1,3}|IV|VI{0,3}|IX|XI{0,3}|XIV|XV)\.)' # Roman numeral + period
    r'(?=[ \t])'                    # followed by a space (not already on own line)
)


def format_statement_question(text: str) -> str:
    """
    Insert newlines before inline Roman numeral statement labels so that
    multi-statement questions render clearly in Telegram polls, e.g.:

        "...है? I. नरेगा... II. इसे..."
        →
        "...है?\nI. नरेगा...\nII. इसे..."
    """
    if not text:
        return text
    # Only process if the text actually contains statement-style markers
    if not re.search(r'(?:I{1,3}|IV|VI{0,3}|IX)\.\s', text):
        return text
    # Insert newline before each inline statement label
    result = _STMT_NEWLINE_RE.sub(lambda m: m.group(1).rstrip() + '\n' + m.group(2), text)
    return result


def is_statement_question(text: str) -> bool:
    """Return True if the question contains Roman numeral sub-statements (I. II. III. ...)."""
    if not text:
        return False
    return bool(re.search(r'(?:I{1,3}|IV|VI{0,3}|IX)\.\s', text))


def needs_full_card(text: str) -> bool:
    """Return True if this question needs a full text card sent before the Telegram poll.
    Covers:
      - Statement questions   (I. / II. / III. sub-statements)
      - Match-the-Following   (→ arrow items or [ Poll : [N/T] ] marker in text)
      - Assertion-Reason      (Assertion (A): / Reason (R): blocks — English or Hindi)
    """
    if not text:
        return False
    if re.search(r'(?:I{1,3}|IV|VI{0,3}|IX)\.\s', text):
        return True
    if '→' in text:
        return True
    if re.search(r'\[\s*Poll\s*:\s*\[', text):
        return True
    # English Assertion-Reason
    if re.search(r'Assertion\s*\(A\)\s*:', text, re.IGNORECASE):
        return True
    # Hindi Assertion-Reason (कथन / कारण)
    if re.search(r'कथन\s*\(A\)\s*:', text):
        return True
    if re.search(r'कारण\s*\(R\)\s*:', text):
        return True
    return False


def format_matching_question(text: str) -> str:
    """Ensure each Item → Match pair is on its own line."""
    if '→' not in text:
        return text
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append('')
            continue
        # If multiple → pairs are jammed on one line, split them
        if stripped.count('→') > 1:
            parts = re.split(r'(?<=[^\s])\s+(?=\S.*?→)', stripped)
            result.extend(parts)
        else:
            result.append(stripped)
    return '\n'.join(result)


_POLL_INSTR_RE = re.compile(
    r'(नीचे\s+दिए\s+गए\s+कूट|कूट\s+से\s+सही'
    r'|Which\s+of\s+the\s+above'
    r'|उपर्युक्त\s+कथन'
    r'|Choose\s+the\s+correct\s+code)',
    re.IGNORECASE,
)


def _format_question_body(text: str) -> str:
    """Normalize rich question text for the preamble message."""
    formatted_q = format_statement_question(text)
    formatted_q = format_matching_question(formatted_q)
    formatted_q = re.sub(r'\[\s*Poll\s*:\s*\[\d+/\d+\]\s*\]', '', formatted_q).strip()
    formatted_q = re.sub(r'^\[\d+/\d+\]\s*', '', formatted_q).strip()
    return formatted_q


def _extract_poll_instruction(bare_q: str) -> str:
    """Pick the short instruction line used as the Telegram poll title."""
    lines = [ln.strip() for ln in bare_q.split('\n') if ln.strip()]
    instr = [ln for ln in lines if _POLL_INSTR_RE.search(ln)]
    if instr:
        return instr[-1]
    questions = [ln for ln in lines if ln.endswith('?') or ln.endswith('?')]
    if questions:
        return questions[-1]
    return lines[0] if lines else bare_q


async def send_question_preamble(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                                 question: str, options=None,
                                 question_number: int = 0,
                                 total_questions: int = 0,
                                 explanation: str = None,
                                 correct_option_id: int = None) -> bool:
    """Send the full question body above the poll (statement / match / AR types).

    The poll below carries only the short [N/T] instruction line plus options,
  matching the Advance Quiz Bot layout.
    """
    if not needs_full_card(question):
        return False

    formatted_q = _format_question_body(question)
    full_text = f"Q{question_number}/{total_questions}\n\n{formatted_q}"

    try:
        await safe_send_message(context, chat_id, full_text)
        return True
    except Exception as e:
        logger.error(f"Error sending question preamble: {e}")
        return False


# Backward-compatible alias
send_full_question_text = send_question_preamble

def prepare_poll_content(question: str, options: List[str], explanation: str = None) -> tuple:
    """
    Prepare poll content for the actual Telegram poll widget.

    - AR (Assertion-Reason, Hindi or English): the full कथन+कारण+instruction block
      is placed in the poll question field.  Options are filtered to the real 4
      answer choices (handles old broken DB rows where कारण/instruction ended up
      in the options list).
    - Matching / Statement: similar full-question approach; options filtered.
    - Direct questions: passed through unchanged.

    Returns: (trimmed_question, trimmed_options, trimmed_explanation)
    """
    # Compile once (local but cheap — called per question)
    _AR_HEAD_RE = re.compile(
        r'(Assertion\s*\(A\)\s*:|कथन\s*\(A\)\s*:)', re.IGNORECASE)
    _AR_BODY_RE = re.compile(
        r'(Reason\s*\(R\)\s*:|कारण\s*\(R\)\s*:|नीचे\s+दिए|कूट|Choose\s+the\s+correct)',
        re.IGNORECASE)
    _NON_ANSWER_RE = re.compile(
        r'(Assertion\s*\(A\)\s*:|कथन\s*\(A\)\s*:'
        r'|Reason\s*\(R\)\s*:|कारण\s*\(R\)\s*:'
        r'|नीचे\s+दिए|कूट|Choose\s+the\s+correct'
        r'|^\|.*\|$'
        r'|^:[-]+\s*\|'
        r'|→'
        r'|^👇)',
        re.IGNORECASE | re.MULTILINE
    )

    # Normalise statement questions: inline I./II./III. → separate lines
    question = format_statement_question(question)

    # Extract [N/T] prefix so it can be preserved/re-attached
    prefix_match = re.match(r'^(\[\d+/\d+\]\s*)', question)
    prefix = prefix_match.group(1) if prefix_match else ''
    bare_q = question[len(prefix):].strip()

    # ── Normalise embedded [ Poll : [N/T] question text ] markers ────────────
    # AI sometimes writes [ Poll : [2/24] कथन (A): ... ] instead of a clean marker.
    # Extract any text embedded after the number and promote it to the question body.
    def _clean_poll_markers(text: str) -> str:
        lines_out = []
        for ln in text.split('\n'):
            m = re.match(r'\s*\[\s*Poll\s*:[^\[]*\[\d+/\d+\]\s*(.*?)\s*\]?\s*$', ln)
            if m:
                embedded = m.group(1).strip()
                if embedded:
                    lines_out.append(embedded)
                # else: pure [ Poll : [N/T] ] marker — drop the line entirely
            else:
                lines_out.append(ln)
        return '\n'.join(lines_out).strip()

    bare_q = _clean_poll_markers(bare_q)

    # ── Assertion-Reason (Hindi or English) ──────────────────────────────────
    if _AR_HEAD_RE.search(bare_q) or any(_AR_BODY_RE.search(o) for o in options):
        # Broken DB format: कारण/instruction were stored as option items.
        # Pull them out of options and append to the question body.
        ar_body_opts = [o for o in options
                        if _AR_BODY_RE.search(o) or _AR_HEAD_RE.search(o)]
        real_opts    = [o for o in options
                        if not _AR_BODY_RE.search(o) and not _AR_HEAD_RE.search(o)]

        if ar_body_opts:
            # Old broken format — reconstruct
            full_bare_q = bare_q + '\n' + '\n'.join(ar_body_opts)
        else:
            # Already correct format
            full_bare_q = bare_q

        instr = _extract_poll_instruction(full_bare_q)
        trimmed_question = (prefix + instr).strip()

        # Guarantee exactly 4 real options
        if len(real_opts) >= 4:
            options = real_opts[:4]

    # ── Matching / [ Poll : ] question ───────────────────────────────────────
    elif '→' in bare_q or re.search(r'\[\s*Poll\s*:\s*\[', bare_q):
        instr = _extract_poll_instruction(bare_q)
        trimmed_question = (prefix + instr).strip()
        if len(options) > 4:
            clean = [o for o in options
                     if o.strip() and not _NON_ANSWER_RE.search(o.strip())]
            if len(clean) >= 4:
                options = clean[-4:]

    # ── Rich types: poll shows only the short instruction line ───────────────
    elif needs_full_card(question):
        instr = _extract_poll_instruction(bare_q)
        trimmed_question = (prefix + instr).strip()

    else:
        trimmed_question = question

    if len(trimmed_question) > POLL_QUESTION_MAX_LENGTH:
        trimmed_question = trim_text(trimmed_question, TRIM_LENGTH)

    trimmed_options = []
    for option in options:
        if len(option) > POLL_OPTION_MAX_LENGTH:
            trimmed_options.append(trim_text(option, TRIM_LENGTH))
        else:
            trimmed_options.append(option)

    trimmed_explanation = explanation
    if explanation and len(explanation) > POLL_EXPLANATION_MAX_LENGTH:
        trimmed_explanation = trim_text(explanation, TRIM_LENGTH)

    return trimmed_question, trimmed_options, trimmed_explanation

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

async def safe_send_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, 
                           text: str, **kwargs) -> Optional[Any]:
    """
    Send message with retry logic and flood control
    Handles all Telegram errors gracefully
    """
    retry = 0
    while retry < MAX_RETRIES:
        try:
            return await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        
        except RetryAfter as e:
            wait_time = e.retry_after + 1
            logger.warning(f"Rate limited, waiting {wait_time}s")
            await asyncio.sleep(wait_time)
            retry += 1
        
        except TimedOut:
            logger.warning(f"Request timed out, retry {retry + 1}/{MAX_RETRIES}")
            await asyncio.sleep(RETRY_DELAY * (2 ** retry))
            retry += 1
        
        except NetworkError as e:
            logger.error(f"Network error: {e}")
            await asyncio.sleep(RETRY_DELAY * (2 ** retry))
            retry += 1
        
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            if "chat not found" in str(e).lower():
                return None
            await asyncio.sleep(RETRY_DELAY * (2 ** retry))
            retry += 1
        
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}", exc_info=True)
            return None
    
    logger.error(f"Failed to send message after {MAX_RETRIES} retries")
    return None

async def safe_send_poll(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                        question: str, options: List[str], **kwargs) -> Optional[Any]:
    """Send poll with retry logic"""
    retry = 0
    while retry < MAX_RETRIES:
        try:
            return await context.bot.send_poll(
                chat_id=chat_id,
                question=question,
                options=options,
                **kwargs
            )
        
        except RetryAfter as e:
            wait_time = e.retry_after + 1
            logger.warning(f"Rate limited on poll, waiting {wait_time}s")
            await asyncio.sleep(wait_time)
            retry += 1
        
        except TimedOut:
            logger.warning(f"Poll timed out, retry {retry + 1}/{MAX_RETRIES}")
            await asyncio.sleep(RETRY_DELAY * (2 ** retry))
            retry += 1
        
        except TelegramError as e:
            logger.error(f"Error sending poll: {e}")
            if "chat not found" in str(e).lower():
                return None
            await asyncio.sleep(RETRY_DELAY * (2 ** retry))
            retry += 1
        
        except Exception as e:
            logger.error(f"Unexpected error sending poll: {e}", exc_info=True)
            return None
    
    logger.error(f"Failed to send poll after {MAX_RETRIES} retries")
    return None

async def wait_until_resumed(chat_id: int):
    """Wait for session to be resumed"""
    while True:
        session = await session_manager.get_session(chat_id)
        if not session or not session.get('paused'):
            break
        await asyncio.sleep(1.5)

# ═══════════════════════════════════════════════════════════════════════════
# FILE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

async def save_quiz_results(quiz_data: Dict, chat_id: int, leaderboard: List[Dict]) -> str:
    """Save quiz results to JSON file"""
    try:
        quiz_id = quiz_data["question_set_id"]
        results_dir = f"quiz_results/{quiz_id}"
        os.makedirs(results_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{results_dir}/{chat_id}_{timestamp}.json"
        
        questions_data = []
        for idx, q in enumerate(quiz_data["questions"]):
            questions_data.append({
                "question_id": idx,
                "question": q["question"],
                "options": q["options"],
                "correct_option_id": q["correct_option_id"]
            })
        
        participant_data = []
        for user in leaderboard:
            participant_data.append({
                "user_id": user["user_id"],
                "name": user["name"],
                "correct": user["correct"],
                "wrong": user["wrong"],
                "score": user["score"],
                "total_time": user["total_time"],
                "answers": user.get("answers", {})
            })
        
        results = {
            "quiz_id": quiz_id,
            "quiz_name": quiz_data.get("quiz_name", "Unnamed Quiz"),
            "timestamp": timestamp,
            "chat_id": chat_id,
            "questions": questions_data,
            "participants": participant_data,
            "negative_marking": quiz_data.get("negative_marking", 1/3)
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Quiz results saved: {filename}")
        return filename
    
    except Exception as e:
        logger.error(f"Error saving quiz results: {e}", exc_info=True)
        return ""

def get_previous_quiz_results(quiz_id: str, chat_id: int) -> Optional[Dict]:
    """Get previous quiz results"""
    try:
        results_dir = f"quiz_results/{quiz_id}"
        
        if not os.path.exists(results_dir):
            return None
        
        files = [f for f in os.listdir(results_dir) 
                if f.startswith(str(chat_id)) and f.endswith('.json')]
        
        if len(files) < 2:
            return None
        
        files.sort(reverse=True)
        
        with open(f"{results_dir}/{files[1]}", 'r', encoding='utf-8') as f:
            return json.load(f)
    
    except Exception as e:
        logger.error(f"Error getting previous results: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE CHAT QUIZ HANDLERS (UNCHANGED)
# ═══════════════════════════════════════════════════════════════════════════

async def start_private_quiz(chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                             questions: List[Dict], quiz: Dict, 
                             question_set_id: str, skip_count: int = 0):
    """Start quiz in private chat with click-based progression"""
    try:
        session_data = {
            "quiz_id": question_set_id,
            "current_index": skip_count,
            "paused": False,
            "questions": questions,
            "quiz_data": quiz,
            "is_private": True,
            "participants": {
                chat_id: {
                    "name": "You",
                    "answers": {},
                    "start_time": time.time()
                }
            },
            "waiting_for_answer": False,
            "active_poll_id": None,
            "polls": {},
            "section_msgs": [],
            "current_section": None,
            "sections": quiz.get("sections", []),
            "context": context,
            "modified_timer_offset": 0
        }
        
        await session_manager.create_session(chat_id, session_data)
        

        sections = quiz.get("sections", [])
        if sections:
            sections.sort(key=lambda s: s["question_range"][0])
            

            start_section = None
            for section in sections:
                start_idx, end_idx = section["question_range"]
                if skip_count < end_idx:
                    start_section = section
                    break
            
            if start_section:
                await start_private_section(chat_id, start_section, skip_count)
            else:
                await safe_send_message(context, chat_id, "⚠️ Skip count beyond all sections.")
                await session_manager.delete_session(chat_id)
        else:

            await send_private_question(chat_id, context, skip_count)
    
    except Exception as e:
        logger.error(f"Error starting private quiz: {e}", exc_info=True)
        await safe_send_message(context, chat_id, "❌ Error starting quiz. Please try again.")
        await session_manager.delete_session(chat_id)

async def start_private_section(chat_id: int, section: Dict, skip_count: int = 0):
    """Start section in private chat"""
    try:
        session = await session_manager.get_session(chat_id)
        if not session or session.get('paused'):
            return
        
        start_idx, end_idx = section["question_range"]
        section_name = section.get("name", f"Section {start_idx}-{end_idx}")
        section_timer = section.get("timer", session["quiz_data"]["timer"])
        
        context = session["context"]
        
        section_msg = await safe_send_message(
            context, chat_id,
            f"📚 *{section_name}* started\n\n"
            f"⏱️ Timer: {section_timer} seconds per question\n"
            f"📋 Questions: {start_idx} to {end_idx}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        if section_msg:
            session["section_msgs"].append(section_msg.message_id)
            session["current_section"] = section
            session["current_section_timer"] = section_timer
            await session_manager.update_session(chat_id, session)
            

            first_question_idx = max(skip_count, start_idx - 1)
            await send_private_question(chat_id, context, first_question_idx)
    
    except Exception as e:
        logger.error(f"Error starting private section: {e}", exc_info=True)

async def send_private_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE, 
                                question_index: int):
    """Send question to private chat - with length handling"""
    try:
        session = await session_manager.get_session(chat_id)
        if not session:
            return
        
        await wait_until_resumed(chat_id)
        
        questions = session["questions"]
        
        if question_index >= len(questions):
            await end_private_quiz(chat_id, context)
            return
        

        current_section = session.get("current_section")
        if current_section and question_index + 1 > current_section["question_range"][1] - 1:
            session["is_last_question_in_section"] = True
            await session_manager.update_session(chat_id, session)
        
        question = questions[question_index]
        original_question = question['question']
        options = question["options"]
        correct_option_id = question["correct_option_id"]
        file_id = question.get("file_id")
        reply_text = question.get("reply_text")
        explanation = question.get("explanation")
        shuffle_option = session["quiz_data"].get("shuffle_options", False)
        promo = question.get("promo")
        

        if shuffle_option:
            paired_options = list(enumerate(options))
            random.shuffle(paired_options)
            shuffled_indices, shuffled_options = zip(*paired_options)
            index_mapping = {original_idx: shuffled_idx 
                           for shuffled_idx, original_idx in enumerate(shuffled_indices)}
            options = list(shuffled_options)
            correct_option_id = index_mapping[correct_option_id]

        if promo and (question_index + 1) % 15 == 0:
            try:
                await safe_send_message(
                    context,
                    chat_id,
                    f"📢\n\n{promo}",
                    parse_mode=ParseMode.MARKDOWN
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to send promo: {e}")
        

        if file_id:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=file_id)
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to send photo: {e}")
        

        if reply_text:
            try:
                await safe_send_message(
                    context, chat_id,
                    f"<b>📖 Reference</b>\n\n{reply_text}",
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to send reference: {e}")
        

        total_questions = len(questions)
        content_sent = await send_full_question_text(
            context, chat_id,
            original_question, options,
            question_index + 1, total_questions,
            explanation,
            correct_option_id=correct_option_id
        )
        

        if content_sent:
            await asyncio.sleep(1)
        

        timer = session.get("current_section_timer", session["quiz_data"]["timer"])
        timer = timer + session.get("modified_timer_offset", 0)
        if timer < 10:
            timer = 10
        

        formatted_question = f"[{question_index + 1}/{total_questions}] {original_question}"
        trimmed_question, trimmed_options, trimmed_explanation = prepare_poll_content(
            formatted_question, options, explanation
        )
        

        poll_msg = await safe_send_poll(
            context, chat_id,
            question=trimmed_question,
            options=trimmed_options,
            type=Poll.QUIZ,
            correct_option_id=correct_option_id,
            explanation=trimmed_explanation,
            is_anonymous=False,
            open_period=timer,
            protect_content=False
        )
        
        if poll_msg:
            session["active_poll_id"] = poll_msg.poll.id
            session["waiting_for_answer"] = True
            session["poll_start_time"] = time.time()
            session["current_index"] = question_index
            
            session["polls"][poll_msg.poll.id] = {
                "correct_option": correct_option_id,
                "sent_time": time.time(),
                "question_index": question_index,
                "shuffled_correct": correct_option_id if shuffle_option else None
            }
            
            await session_manager.update_session(chat_id, session)
            

            asyncio.create_task(private_question_timeout(chat_id, poll_msg.poll.id, timer))
        else:

            if question_index + 1 < len(questions):
                await asyncio.sleep(3)
                await send_private_question(chat_id, context, question_index + 1)
            else:
                await end_private_quiz(chat_id, context)
    
    except Exception as e:
        logger.error(f"Error sending private question: {e}", exc_info=True)

        session = await session_manager.get_session(chat_id)
        if session and question_index + 1 < len(session.get("questions", [])):
            await asyncio.sleep(3)
            await send_private_question(chat_id, context, question_index + 1)

async def private_question_timeout(chat_id: int, poll_id: str, timer: int):
    """Handle timeout for private quiz question"""
    try:
        await asyncio.sleep(timer + 2)
        
        session = await session_manager.get_session(chat_id)
        if not session or session.get("active_poll_id") != poll_id:
            return
        
        session["waiting_for_answer"] = False
        current_idx = session.get("current_index", 0)
        session["current_index"] = current_idx + 1
        
        await session_manager.update_session(chat_id, session)
        

        if session.get("is_last_question_in_section"):
            session["is_last_question_in_section"] = False
            await session_manager.update_session(chat_id, session)
            await end_private_section(chat_id)
        else:

            context = session.get("context")
            if context and current_idx + 1 < len(session.get("questions", [])):
                await asyncio.sleep(1)
                await send_private_question(chat_id, context, current_idx + 1)
            else:
                await end_private_quiz(chat_id, context)
    
    except Exception as e:
        logger.error(f"Error in private question timeout: {e}", exc_info=True)

async def handle_private_poll_answer(poll_id: str, user_id: int, 
                                     option_id: int, current_time: float):
    """Handle poll answer in private chat"""
    try:

        for chat_id in list(session_manager.sessions.keys()):
            session = await session_manager.get_session(chat_id)
            
            if not session or not session.get("is_private"):
                continue
            
            if poll_id == session.get("active_poll_id"):

                if user_id not in session["participants"]:
                    session["participants"][user_id] = {
                        "name": "You",
                        "answers": {}
                    }
                
                session["participants"][user_id]["answers"][poll_id] = {
                    "option": option_id,
                    "time": current_time
                }
                
                session["waiting_for_answer"] = False
                current_idx = session.get("current_index", 0)
                
                await session_manager.update_session(chat_id, session)
                

                if session.get("is_last_question_in_section"):
                    session["is_last_question_in_section"] = False
                    await session_manager.update_session(chat_id, session)
                    await asyncio.sleep(2)
                    await end_private_section(chat_id)
                else:

                    await asyncio.sleep(2)
                    context = session.get("context")
                    if context and current_idx + 1 < len(session.get("questions", [])):
                        await send_private_question(chat_id, context, current_idx + 1)
                    else:
                        await end_private_quiz(chat_id, context)
                
                break
    
    except Exception as e:
        logger.error(f"Error handling private poll answer: {e}", exc_info=True)

async def end_private_section(chat_id: int):
    """End current section in private chat"""
    try:
        session = await session_manager.get_session(chat_id)
        if not session:
            return
        
        context = session.get("context")
        

        if session.get("section_msgs"):
            try:
                last_msg_id = session["section_msgs"][-1]
                await context.bot.unpin_chat_message(chat_id, last_msg_id)
            except Exception as e:
                logger.warning(f"Could not unpin message: {e}")
        

        sections = session.get("sections", [])
        current_section = session.get("current_section")
        
        if current_section and sections:
            current_end = current_section["question_range"][1]
            next_section = None
            
            for section in sections:
                if section["question_range"][0] > current_end:
                    next_section = section
                    break
            
            if next_section:
                await start_private_section(chat_id, next_section, 0)
            else:
                await end_private_quiz(chat_id, context)
        else:
            await end_private_quiz(chat_id, context)
    
    except Exception as e:
        logger.error(f"Error ending private section: {e}", exc_info=True)

async def end_private_quiz(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """End quiz in private chat and show results"""
    try:
        session = await session_manager.delete_session(chat_id)
        if not session:
            return
        
        quiz_data = session["quiz_data"]
        questions = session["questions"]
        total_questions = len(questions)
        negative_marking = quiz_data.get("negative_marking", 1/3)
        
        await safe_send_message(context, chat_id, "📊 Calculating your results...")
        

        user_data = session["participants"].get(chat_id, {})
        correct = 0
        wrong = 0
        total_time = 0
        
        for poll_id, poll_info in session.get("polls", {}).items():
            if poll_id in user_data.get("answers", {}):
                answer = user_data["answers"][poll_id]
                response_time = answer["time"] - poll_info["sent_time"]
                total_time += response_time
                
                if answer["option"] == poll_info["correct_option"]:
                    correct += 1
                else:
                    wrong += 1
        
        score = correct - (wrong * negative_marking)
        percentage = (correct / total_questions) * 100 if total_questions else 0
        accuracy = (correct / (correct + wrong)) * 100 if (correct + wrong) > 0 else 0
        
        minutes, seconds = divmod(total_time, 60)
        time_str = f"{int(minutes)}m {int(seconds)}s"
        

        leaderboard = [{
            "user_id": chat_id,
            "name": "You",
            "correct": correct,
            "wrong": wrong,
            "score": score,
            "total_time": total_time,
            "answers": user_data.get("answers", {})
        }]
        

        results_file = await save_quiz_results(quiz_data, chat_id, leaderboard)
        
        start_link = f"https://t.me/Xd_Quiz_Bot?start={quiz_data['question_set_id']}"
        compare_callback = f"compare_{quiz_data['question_set_id']}_{chat_id}"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Quiz", url=start_link)],
            [InlineKeyboardButton("📊 Compare Results", callback_data=compare_callback)]
        ])
        
        quiz_name = escape_markdown(quiz_data.get('quiz_name', 'Unnamed Quiz'))
        
        result_text = f"""🏆 *Quiz Completed!*

📝 Quiz: {quiz_name}
📊 Total Questions: {total_questions}

📈 *Your Performance:*
✅ Correct: {correct}
❌ Wrong: {wrong}
🎯 Score: {score:.2f}
⏱️ Total Time: {time_str}
📊 Percentage: {percentage:.2f}%
🎯 Accuracy: {accuracy:.2f}%"""
        
        await safe_send_message(
            context, chat_id,
            text=result_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=buttons
        )
        

        try:
            await send_quiz_result_pdf(
                quiz_data, chat_id, context,
                protect_content=False,
                leaderboard=leaderboard,
                shuffle=False,
            )
        except Exception as e:
            logger.error(f"Error generating quiz PDF: {e}")
    
    except Exception as e:
        logger.error(f"Error ending private quiz: {e}", exc_info=True)
        await safe_send_message(context, chat_id, "❌ Error generating results.")

# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════

async def start_group_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           quiz_id: str, skip_count: int = 0, scheduled: bool = False):
    """Start group quiz with linear sequential flow"""
    try:
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        user_id = update.effective_user.id
        
        logger.info(f"Starting group quiz {quiz_id} in chat {chat_id} (skip: {skip_count})")
        

        quiz = await db_manager.find_one("questions", {"question_set_id": quiz_id})
        if not quiz:
            if not scheduled:
                await safe_send_message(context, chat_id, "❌ Invalid Quiz ID.")
            return False
        
        quiz_name = quiz.get("quiz_name", "Unnamed Quiz")
        questions = quiz["questions"]
        shuffle_enabled = quiz.get("shuffle", False)
        sections = quiz.get("sections", [])
        

        creator_id = quiz["creator_id"]
        is_paid = quiz.get("type") == "paid"
        auth_record = await db_manager.find_one("auth", {"creator_id": creator_id})
        
        protect_type = True
        if chat_id == creator_id and chat_type == "private":
            protect_type = False
        elif is_paid and (not auth_record or chat_id not in auth_record.get("auth_users", [])):
            if not scheduled:
                try:
                    creator_info = await context.bot.get_chat(creator_id)
                    creator_details = (
                        f"🆔 Creator Details:\n"
                        f"👤 Name: {escape_markdown(creator_info.first_name or '')}\n"
                        f"💬 Username: @{escape_markdown(creator_info.username if creator_info.username else 'N/A')}\n"
                        f"📢 User ID: `{creator_info.id}`\n\n"
                        f"*_Protected by [Team SPY](https://t.me/AIpha_World)_*"
                    )
                    await safe_send_message(
                        context, chat_id,
                        f"> ❌ Contact creator of this quiz to get access\n\n{creator_details}",
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    await safe_send_message(
                        context, chat_id,
                        f"❌ Unable to fetch creator details. Contact directly via ID `{creator_id}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
            return False
        

        # Shuffle question order if the quiz has shuffle enabled
        if shuffle_enabled:
            import random as _random
            questions = list(questions)
            _random.shuffle(questions)

        session_data = {
            "quiz_id": quiz_id,
            "current_index": skip_count,
            "paused": False,
            "polls": {},
            "participants": {},
            "is_private": False,
            "section_msgs": [],
            "modified_timer_offset": 0,
            "quiz_data": quiz,
            "questions": questions,
            "protect_type": protect_type,
            "context": context,
            "shuffle_options": quiz.get("shuffle_options", False),
            "sections": sections,
            "sections_sorted": sorted(sections, key=lambda s: s["question_range"][0]) if sections else []
        }
        
        await session_manager.create_session(chat_id, session_data)
        

        quiz_task = asyncio.create_task(run_group_quiz(chat_id, skip_count, scheduled))
        await session_manager.register_quiz_task(chat_id, quiz_task)
        
        logger.info(f"Group quiz {quiz_id} started in chat {chat_id} with task")
        return True
    
    except Exception as e:
        logger.error(f"Error in start_group_quiz: {e}", exc_info=True)
        if not scheduled:
            await safe_send_message(context, chat_id, "❌ Error starting quiz.")
        return False

async def run_group_quiz(chat_id: int, start_index: int = 0, scheduled: bool = False):
    """
    Main group quiz runner - one task per chat with linear flow
    """
    try:
        logger.info(f"Starting quiz runner for chat {chat_id}")
        

        session = await session_manager.get_session(chat_id)
        if not session:
            logger.error(f"No session found for chat {chat_id}")
            return
        
        context = session["context"]
        quiz_data = session["quiz_data"]
        questions = session["questions"]
        protect_type = session["protect_type"]
        shuffle_options = session["shuffle_options"]
        sections = session["sections_sorted"]
        

        if not scheduled:
            await safe_send_message(
                context, chat_id,
                f"🏁 *{quiz_data.get('quiz_name', 'Quiz')}* starting now!\n\n"
                f"📊 Total questions: {len(questions)}\n"
                f"⏱️ Timer: {quiz_data['timer']} seconds per question",
                parse_mode=ParseMode.MARKDOWN
            )
            await asyncio.sleep(2)
        
        current_index = start_index
        

        if sections:
            await run_group_quiz_with_sections(chat_id, current_index)
        else:
            await run_group_quiz_no_sections(chat_id, current_index)
        

        await end_group_quiz(chat_id)
        
    except asyncio.CancelledError:
        logger.info(f"Quiz runner cancelled for chat {chat_id}")
        raise
    except Exception as e:
        logger.error(f"Error in run_group_quiz for chat {chat_id}: {e}", exc_info=True)
        session = await session_manager.get_session(chat_id)
        if session:
            await safe_send_message(
                session["context"], chat_id,
                "❌ An error occurred during the quiz. The quiz has been stopped."
            )
            await session_manager.delete_session(chat_id)

async def run_group_quiz_no_sections(chat_id: int, start_index: int):
    """Run quiz without sections"""
    session = await session_manager.get_session(chat_id)
    if not session:
        return
    
    context = session["context"]
    questions = session["questions"]
    protect_type = session["protect_type"]
    shuffle_options = session["shuffle_options"]
    
    total_questions = len(questions)
    base_timer = session["quiz_data"]["timer"]
    
    for question_idx in range(start_index, total_questions):

        session = await wait_and_check_session(chat_id)
        if not session:
            return
        

        success = await send_group_question(chat_id, question_idx)
        
        if not success:

            logger.warning(f"Failed to send question {question_idx} for chat {chat_id}")
            await asyncio.sleep(3)
            continue
        

        timer = base_timer + session.get("modified_timer_offset", 0)
        if timer < 10:
            timer = 10
        
        try:
            await asyncio.sleep(timer + 3)  # Wait for poll to end + buffer
        except asyncio.CancelledError:
            raise
        

        await asyncio.sleep(1)
    
    logger.info(f"Quiz completed all questions for chat {chat_id}")

async def run_group_quiz_with_sections(chat_id: int, start_index: int):
    """Run quiz with sections"""
    session = await session_manager.get_session(chat_id)
    if not session:
        return
    
    sections = session["sections_sorted"]
    questions = session["questions"]
    

    current_section_idx = 0
    for i, section in enumerate(sections):
        start_range, end_range = section["question_range"]
        if start_index < end_range:
            current_section_idx = i
            break
    

    for section_idx in range(current_section_idx, len(sections)):
        session = await wait_and_check_session(chat_id)
        if not session:
            return
        

        section = sections[section_idx]
        await start_group_section(chat_id, section)
        

        start_range, end_range = section["question_range"]
        section_start_idx = max(start_index, start_range - 1)
        section_timer = section.get("timer", session["quiz_data"]["timer"])
        
        for question_idx in range(section_start_idx, min(end_range - 1, len(questions))):
            session = await wait_and_check_session(chat_id)
            if not session:
                return
            

            success = await send_group_question(chat_id, question_idx, section_timer)
            
            if not success:
                logger.warning(f"Failed to send question {question_idx} for chat {chat_id}")
                await asyncio.sleep(3)
                continue
            

            timer = section_timer + session.get("modified_timer_offset", 0)
            if timer < 10:
                timer = 10
            
            try:
                await asyncio.sleep(timer + 3)
            except asyncio.CancelledError:
                raise
            

            await asyncio.sleep(1)
        

        await end_group_section(chat_id, section)
        

        start_index = 0
    
    logger.info(f"Quiz completed all sections for chat {chat_id}")

async def wait_and_check_session(chat_id: int) -> Optional[Dict]:
    """Wait for session to be resumed and check if it exists"""
    while True:
        session = await session_manager.get_session(chat_id)
        if not session:
            return None
        
        if not session.get('paused'):
            return session
        
        await asyncio.sleep(1.5)

async def start_group_section(chat_id: int, section: Dict):
    """Start a section in group chat"""
    try:
        session = await session_manager.get_session(chat_id)
        if not session:
            return
        
        start_idx, end_idx = section["question_range"]
        section_name = section.get("name", f"Section {start_idx}-{end_idx}")
        section_timer = section.get("timer", session["quiz_data"]["timer"])
        
        context = session["context"]
        
        section_msg = await safe_send_message(
            context, chat_id,
            f"📚 *{section_name}* started\n\n"
            f"⏱️ Timer: {section_timer} seconds per question\n"
            f"📋 Questions: {start_idx} to {end_idx}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        if section_msg:
            try:
                await context.bot.pin_chat_message(chat_id, section_msg.message_id)
            except Exception as e:
                logger.warning(f"Could not pin message: {e}")
            
            session["section_msgs"].append(section_msg.message_id)
            session["current_section"] = section
            await session_manager.update_session(chat_id, session)
    
    except Exception as e:
        logger.error(f"Error starting group section: {e}", exc_info=True)

async def end_group_section(chat_id: int, section: Dict):
    """End a section in group chat"""
    try:
        session = await session_manager.get_session(chat_id)
        if not session or not session.get("section_msgs"):
            return
        

        context = session["context"]
        last_msg_id = session["section_msgs"][-1]
        
        try:
            await context.bot.unpin_chat_message(chat_id, last_msg_id)
        except Exception as e:
            logger.warning(f"Could not unpin message: {e}")
        

        session["current_section"] = None
        await session_manager.update_session(chat_id, session)
    
    except Exception as e:
        logger.error(f"Error ending group section: {e}", exc_info=True)

async def send_group_question(chat_id: int, question_idx: int, custom_timer: int = None) -> bool:
    """Send a single question to group chat"""
    try:
        session = await session_manager.get_session(chat_id)
        if not session:
            return False
        
        context = session["context"]
        questions = session["questions"]
        protect_type = session["protect_type"]
        shuffle_options = session["shuffle_options"]
        
        if question_idx >= len(questions):
            return False
        
        question = questions[question_idx]
        original_question = question['question']
        options = question["options"]
        correct_option_id = question["correct_option_id"]
        file_id = question.get("file_id")
        reply_text = question.get("reply_text")
        explanation = question.get("explanation")
        promo = session.get("quiz_data", {}).get("promo")

        # Guard against legacy DB rows where `correct_option_id` was saved as
        # None (this used to happen for forwarded polls whose answer wasn't
        # revealed). Without this, shuffling crashed with KeyError: None and
        # the question silently failed to send.
        if correct_option_id is None or not isinstance(correct_option_id, int):
            logger.warning(
                f"Skipping question {question_idx + 1} — invalid correct_option_id "
                f"({correct_option_id!r}). Likely an unrevealed poll was imported."
            )
            return False
        if not (0 <= correct_option_id < len(options)):
            logger.warning(
                f"Skipping question {question_idx + 1} — correct_option_id "
                f"{correct_option_id} out of range for {len(options)} options."
            )
            return False

        if shuffle_options:
            paired_options = list(enumerate(options))
            random.shuffle(paired_options)
            shuffled_indices, shuffled_options = zip(*paired_options)
            index_mapping = {original_idx: shuffled_idx 
                           for shuffled_idx, original_idx in enumerate(shuffled_indices)}
            options = list(shuffled_options)
            correct_option_id = index_mapping[correct_option_id]

        if promo and (question_idx + 1) % 15 == 0:
            try:
                await safe_send_message(
                    context,
                    chat_id,
                    escape_markdown(f"📢\n\n{promo}"),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to send promo: {e}")
        

        if file_id:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=file_id)
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to send photo: {e}")
                "Use /features to see what I can do and /help to learn how to use me!"
        

        if reply_text:
            try:
                await safe_send_message(
                    context, chat_id,
                    f"<b>📖 Reference</b>\n\n{reply_text}",
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Failed to send reference: {e}")
        

        total_questions = len(questions)
        content_sent = await send_full_question_text(
            context, chat_id,
            original_question, options,
            question_idx + 1, total_questions,
            explanation,
            correct_option_id=correct_option_id
        )
        

        if content_sent:
            await asyncio.sleep(1)
        

        if custom_timer is None:
            base_timer = session["quiz_data"]["timer"]
        else:
            base_timer = custom_timer
        
        timer = base_timer + session.get("modified_timer_offset", 0)
        if timer < 10:
            timer = 10
        

        formatted_question = f"[{question_idx + 1}/{total_questions}] {original_question}"
        trimmed_question, trimmed_options, trimmed_explanation = prepare_poll_content(
            formatted_question, options, explanation
        )
        

        poll_msg = await safe_send_poll(
            context, chat_id,
            question=trimmed_question,
            options=trimmed_options,
            type=Poll.QUIZ,
            correct_option_id=correct_option_id,
            explanation=trimmed_explanation,
            is_anonymous=False,
            open_period=timer,
            protect_content=protect_type
        )
        
        if poll_msg:
            current_time = time.time()
            session["polls"][poll_msg.poll.id] = {
                "correct_option": correct_option_id,
                "sent_time": current_time
            }
            session["current_index"] = question_idx + 1
            await session_manager.update_session(chat_id, session)
            
            logger.info(f"Sent question {question_idx + 1}/{total_questions} to chat {chat_id}")
            return True
        else:
            logger.error(f"Failed to send poll for question {question_idx} to chat {chat_id}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending group question: {e}", exc_info=True)
        return False

async def end_group_quiz(chat_id: int):
    """End group quiz and show results"""
    try:
        session = await session_manager.get_session(chat_id)
        if not session:
            return
        
        context = session["context"]
        quiz_id = session["quiz_id"]
        protect_type = session["protect_type"]
        

        for msg_id in session.get("section_msgs", []):
            try:
                await context.bot.unpin_chat_message(chat_id, msg_id)
            except Exception as e:
                pass
        
        await safe_send_message(
            context, chat_id,
            "__Generating Result...__",
            parse_mode=ParseMode.MARKDOWN
        )
        

        quiz_data = await db_manager.find_one("questions", {"question_set_id": quiz_id})
        if not quiz_data:
            await safe_send_message(context, chat_id, "❌ Quiz data not found in database.")
            await session_manager.delete_session(chat_id)
            return
        
        total_questions = len(quiz_data["questions"])
        quiz_name = quiz_data.get("quiz_name", "Unnamed Quiz")
        negative_marking = quiz_data.get("negative_marking", 1/3)
        
        leaderboard = []
        

        for user_id, user_data in session["participants"].items():
            correct = 0
            wrong = 0
            total_time = 0
            user_answers = {}
            
            for poll_id, poll_data in session["polls"].items():
                if poll_id not in user_data["answers"]:
                    continue
                
                answer_time = user_data["answers"][poll_id]["time"]
                selected_option = user_data["answers"][poll_id]["option"]
                correct_option = poll_data["correct_option"]
                poll_sent_time = poll_data["sent_time"]
                

                question_idx = None
                for idx, (pid, _) in enumerate(session["polls"].items()):
                    if pid == poll_id:
                        question_idx = idx
                        break
                
                if question_idx is not None:
                    user_answers[f"q{question_idx}"] = selected_option
                
                response_time = answer_time - poll_sent_time
                total_time += response_time
                
                if selected_option == correct_option:
                    correct += 1
                else:
                    wrong += 1
            
            score = correct - (wrong * negative_marking)
            
            leaderboard.append({
                "user_id": user_id,
                "name": user_data["name"],
                "correct": correct,
                "wrong": wrong,
                "score": score,
                "total_time": total_time,
                "answers": user_answers
            })
        
        if not leaderboard:
            await safe_send_message(
                context, chat_id,
                f"🏆 *Quiz '{escape_markdown(quiz_name)}' has ended!*\n\n"
                "ℹ️ Kisi ne bhi answer nahi diya — yahaan question paper PDF bhej raha hoon:",
                parse_mode=ParseMode.MARKDOWN
            )
            try:
                await send_quiz_result_pdf(
                    quiz_data, chat_id, context,
                    protect_content=False,
                    leaderboard=[],
                    shuffle=False,
                )
            except Exception as e:
                logger.error(f"Error generating quiz PDF (no-answers branch): {e}")
            await session_manager.delete_session(chat_id)
            return
        

        leaderboard.sort(key=lambda x: (x["score"], -x["total_time"]), reverse=True)
        

        results_file = await save_quiz_results(quiz_data, chat_id, leaderboard)
        
        start_link = f"https://t.me/Xd_Quiz_Bot?start={quiz_id}"
        compare_callback = f"compare_{quiz_id}_{chat_id}"
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Quiz", url=start_link)],
            [InlineKeyboardButton("📊 Compare Results", callback_data=compare_callback)]
        ])
        

        for i in range(0, len(leaderboard), 15):
            chunk = leaderboard[i:i+15]
            leaderboard_text = ""
            
            for index, user in enumerate(chunk, start=i+1):
                total_attempts = user["correct"] + user["wrong"]
                percentage = (user["correct"] / total_questions) * 100 if total_questions else 0
                accuracy = (user["correct"] / total_attempts) * 100 if total_attempts else 0
                
                minutes, seconds = divmod(user["total_time"], 60)
                time_str = f"{int(minutes)}m {int(seconds)}s"
                
                rank_icon = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"{index}."
                
                leaderboard_text += (
                    f"{rank_icon} {user['name']} | ✅ {user['correct']} | ❌ {user['wrong']} | 🎯 {user['score']:.2f} | "
                    f"⏱️ {time_str} | 📊 {percentage:.2f}% | 🚀 {accuracy:.2f}%\n"
                    f"────────────────\n"
                )
            
            if i == 0:
                await safe_send_message(
                    context, chat_id,
                    f"""🏆 Quiz '{quiz_name}' has ended!\n\n🎯 Top Performers:\n\n{leaderboard_text}""",
                    reply_markup=buttons
                )
            else:
                await asyncio.sleep(4)
                await safe_send_message(
                    context, chat_id,
                    f"""🏆 Quiz '{quiz_name}' has ended!\n\n🎯 Top Performers:\n\n{leaderboard_text}"""
                )
        

        try:
            ok = await send_quiz_result_pdf(
                quiz_data, chat_id, context,
                protect_content=protect_type,
                leaderboard=leaderboard,
                shuffle=False,
            )
            if not ok:
                await safe_send_message(
                    context, chat_id,
                    "⚠️ Could not generate quiz PDF due to an error."
                )
        except Exception as e:
            logger.error(f"Error generating quiz PDF: {e}")
            await safe_send_message(
                context, chat_id,
                "⚠️ Could not generate quiz PDF due to an error."
            )
        

        await session_manager.delete_session(chat_id)
        
        logger.info(f"Group quiz {quiz_id} ended successfully for chat {chat_id}")
    
    except Exception as e:
        logger.error(f"Error ending group quiz: {e}", exc_info=True)
        try:
            await safe_send_message(context, chat_id, "❌ Error generating results.")
        except:
            pass
        finally:
            await session_manager.delete_session(chat_id)

# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS (WITH SCHEDULE FEATURE)
# ═══════════════════════════════════════════════════════════════════════════

async def system_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /stats command
    Show detailed system statistics
    """
    try:
        user_id = update.message.from_user.id
        

        ADMIN_IDS = [7770737860, 77707378601]  # Add your admin user IDs
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("🚫 This command is only available to administrators.")
            return
        

        session_stats = session_manager.get_stats()
        rate_limiter_stats = rate_limiter.get_stats()
        
        all_tasks = asyncio.all_tasks()
        

        memory_info = "N/A"
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=1)
            memory_info = f"{memory_mb:.2f} MB (CPU: {cpu_percent:.1f}%)"
        except:
            pass
        

        db_health = "✓ Healthy" if all(db_manager.health_status.values()) else "✗ Issues Detected"
        
        report = f"""
📊 **SYSTEM STATISTICS**

🔹 **Sessions:**
- Active: {session_stats['active_sessions']}
- Active Quiz Tasks: {session_stats['active_quiz_tasks']}

🔹 **Rate Limiter:**
- Active Buckets: {rate_limiter_stats['active_buckets']}
- Total Requests: {rate_limiter_stats['total_requests']}
- Blocked: {rate_limiter_stats['total_blocked']}

🔹 **System:**
- Asyncio Tasks: {len(all_tasks)}
- Memory: {memory_info}
- Database: {db_health}

⏰ Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error in system_stats: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error retrieving stats: {e}")

async def emergency_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /emergency_cleanup command
    Admin-only command to force cleanup immediately
    """
    try:
        user_id = update.message.from_user.id
        

        ADMIN_IDS = [7770737860, 77707378601]  # Add your admin user IDs
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("🚫 This command is only available to administrators.")
            return
        
        await update.message.reply_text("⚠️ **EMERGENCY CLEANUP INITIATED**\n\nThis may take a few moments...", parse_mode=ParseMode.MARKDOWN)
        

        stats_before = {
            'sessions': session_manager.get_active_count(),
            'asyncio_tasks': len(asyncio.all_tasks()),
            'rate_limiter': len(rate_limiter.buckets),
        }
        

        await session_manager.cleanup_old_sessions()
        await rate_limiter.cleanup_old_entries()
        

        import gc
        collected = gc.collect()
        

        stats_after = {
            'sessions': session_manager.get_active_count(),
            'asyncio_tasks': len(asyncio.all_tasks()),
            'rate_limiter': len(rate_limiter.buckets),
        }
        
        report = f"""
✅ **EMERGENCY CLEANUP COMPLETED**

📊 **Before:**
- Sessions: {stats_before['sessions']}
- Asyncio Tasks: {stats_before['asyncio_tasks']}
- Rate Limiter: {stats_before['rate_limiter']}

🧹 **Actions:**
- Collected {collected} objects

📈 **After:**
- Sessions: {stats_after['sessions']}
- Asyncio Tasks: {stats_after['asyncio_tasks']}
- Rate Limiter: {stats_after['rate_limiter']}
        """
        
        await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)
        
        logger.warning(f"Emergency cleanup executed by admin {user_id}")
        
    except Exception as e:
        logger.error(f"Error in emergency cleanup: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error during emergency cleanup: {e}")

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - SIMPLIFIED VERSION"""
    try:
        chat_id = update.message.chat_id
        chat_type = update.message.chat.type
        user_id = update.message.from_user.id
        

        if not await rate_limiter.check_rate_limit(user_id):
            await safe_send_message(
                context, chat_id,
                "⏱️ Too many requests. Please wait a moment and try again."
            )
            return
        

        await db_manager.insert_one("users", {"chat_id": chat_id})
        

        if len(context.args) <= 0:
            welcome_message = (
                "👋 Welcome to **Quizbot**!\n\n"
                "Create quizzes with MCQs, sections, timers, and even convert TestBook tests to quizzes. "
                "Add media/text, share in groups, or invite users to answer.\n\n"
            )
            join_channel_button = InlineKeyboardMarkup([

                [InlineKeyboardButton("📢 Join Our Channel", url="https://t.me/AIpha_World")]
            ])
            await safe_send_message(
                context, chat_id,
                welcome_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=join_channel_button
            )
            return
        
        question_set_id = context.args[0]
        skip_count = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 0
        
        logger.info(f"Starting quiz {question_set_id} in chat {chat_id} (type: {chat_type})")
        

        existing_session = await session_manager.get_session(chat_id)
        if existing_session:
            await safe_send_message(
                context, chat_id,
                "⚠️ A quiz is already ongoing. Please stop it first or wait until it ends."
            )
            return
        

        quiz = await db_manager.find_one("questions", {"question_set_id": question_set_id})
        if not quiz:
            await safe_send_message(context, chat_id, "❌ Invalid QuestionSetID.")
            return
        
        logger.info(f"Quiz {question_set_id} loaded successfully")
        
        creator_id = quiz["creator_id"]
        is_paid = quiz.get("type") == "paid"
        auth_record = await db_manager.find_one("auth", {"creator_id": creator_id})
        
        protect_type = True
        

        if chat_id == creator_id and chat_type == "private":
            protect_type = False
        elif is_paid and (not auth_record or chat_id not in auth_record.get("auth_users", [])):
            try:
                creator_info = await context.bot.get_chat(creator_id)
                creator_details = (
                    f"🆔 Creator Details:\n"
                    f"👤 Name: {escape_markdown(creator_info.first_name or '')}\n"
                    f"💬 Username: @{escape_markdown(creator_info.username if creator_info.username else 'N/A')}\n"
                    f"📢 User ID: `{creator_info.id}`\n\n"
                    f"*_Protected by [Team SPY](https://t.me/AIpha_World)_*"
                )
                await safe_send_message(
                    context, chat_id,
                    f"> ❌ Contact creator of this quiz to get access\n\n{creator_details}",
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=True
                )
            except Exception as e:
                await safe_send_message(
                    context, chat_id,
                    f"❌ Unable to fetch creator details. Contact directly via ID `{creator_id}`",
                    parse_mode=ParseMode.MARKDOWN
                )
            return
        

        if chat_type == "private":
            logger.info(f"Starting private quiz for chat {chat_id}")
            k = await safe_send_message(context, chat_id, "<b>🪜 Ready ...</b>", parse_mode=ParseMode.HTML)
            await asyncio.sleep(1)
            if k:
                await k.edit_text("<b>⛹️‍♂️ Steady...</b>", parse_mode=ParseMode.HTML)
            await asyncio.sleep(1)
            if k:
                await k.edit_text("<b>🏃‍♀️🏃‍♂️ Go!</b>", parse_mode=ParseMode.HTML)
            await asyncio.sleep(1)
            if k:
                await k.delete()
            
            priv_questions = list(quiz["questions"])
            if quiz.get("shuffle", False):
                import random as _random
                _random.shuffle(priv_questions)
            await start_private_quiz(chat_id, context, priv_questions, quiz, question_set_id, skip_count)
            return
        

        logger.info(f"Starting group quiz for chat {chat_id}")
        k = await safe_send_message(context, chat_id, "<b>🪜 Ready ...</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(2)
        if k:
            await k.edit_text("<b>⛹️‍♂️ Steady...</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(2)
        if k:
            await k.edit_text("<b>🏃‍♀️🏃‍♂️ Go...</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(2)
        if k:
            await k.delete()
        
        logger.info(f"Creating session for chat {chat_id}")
        

        success = await start_group_quiz(update, context, question_set_id, skip_count)
        
        if success:
            logger.info(f"Quiz {question_set_id} started successfully in chat {chat_id}")
        else:
            await safe_send_message(context, chat_id, "❌ Error starting quiz. Please try again.")
    
    except Exception as e:
        logger.error(f"Error in start_quiz: {e}", exc_info=True)
        await safe_send_message(context, chat_id, "❌ Error starting quiz. Please try again.")

async def schedule_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sdl command - Schedule a quiz for later"""
    try:
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        

        if chat_type != ChatType.GROUP and chat_type != ChatType.SUPERGROUP:
            await safe_send_message(
                context, chat_id,
                "⚠️ This command can only be used in groups."
            )
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(
                    context, chat_id,
                    "🚫 You must be an admin to schedule a quiz."
                )
                return
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            await safe_send_message(
                context, chat_id,
                "❌ Error checking admin permissions."
            )
            return
        

        if len(context.args) < 2:
            await safe_send_message(
                context, chat_id,
                "📝 Usage: /schedule <quiz_id> <HH:MM> [skip_count]\n"
                "         (alias: /sdl)\n\n"
                "Example:\n"
                "/schedule abc123 14:30 — Start quiz abc123 at 2:30 PM\n"
                "/schedule abc123 14:30 5 — Start from question 6 at 2:30 PM\n\n"
                "⏰ Time format: 24-hour (HH:MM) in Indian Standard Time"
            )
            return
        
        quiz_id = context.args[0]
        time_str = context.args[1]
        skip_count = int(context.args[2]) if len(context.args) > 2 and context.args[2].isdigit() else 0
        

        try:
            now = now_ist()

            hour, minute = map(int, time_str.split(':'))
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time")

            # Build the requested time on today's date in IST. If it's already
            # in the past, roll over to tomorrow (handles month/year boundary
            # safely via timedelta — `replace(day=...)` would crash on day 31).
            scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if scheduled_time <= now:
                scheduled_time = scheduled_time + timedelta(days=1)

        except ValueError:
            await safe_send_message(
                context, chat_id,
                "❌ Invalid time format. Please use HH:MM (24-hour format).\n"
                "Example: 14:30 for 2:30 PM"
            )
            return
        

        quiz = await db_manager.find_one("questions", {"question_set_id": quiz_id})
        if not quiz:
            await safe_send_message(context, chat_id, "❌ Invalid Quiz ID.")
            return
        

        existing_session = await session_manager.get_session(chat_id)
        if existing_session:
            await safe_send_message(
                context, chat_id,
                "⚠️ A quiz is already running in this group. Please stop it first or wait until it ends."
            )
            return
        

        existing_scheduled = await db_manager.find("scheduled", {
            "chat_id": chat_id,
            "scheduled_time": scheduled_time,
            "status": "pending"
        })
        
        if existing_scheduled:
            await safe_send_message(
                context, chat_id,
                f"⚠️ A quiz is already scheduled for {scheduled_time.strftime('%H:%M')}. "
                "Please choose a different time."
            )
            return
        

        scheduled_quiz = {
            "quiz_id": quiz_id,
            "chat_id": chat_id,
            "scheduled_by": user_id,
            "scheduled_time": scheduled_time,
            "skip_count": skip_count,
            "status": "pending",
            "created_at": now_ist()
        }
        
        success = await db_manager.insert_one("scheduled", scheduled_quiz)
        
        if not success:
            await safe_send_message(context, chat_id, "❌ Failed to schedule quiz. Please try again.")
            return
        
        quiz_name = quiz.get("quiz_name", "Unnamed Quiz")
        
        await safe_send_message(
            context, chat_id,
            f"✅ *Quiz Scheduled Successfully!*\n\n"
            f"📝 Quiz: {escape_markdown(quiz_name)}\n"
            f"🆔 ID: `{quiz_id}`\n"
            f"⏰ Scheduled for: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} (IST)\n"
            f"⏱️ Starting from question: {skip_count + 1}\n"
            f"👤 Scheduled by: <code>{user_id}</code>\n\n"
            f"✅ The quiz will automatically start at the scheduled time.\n"
            f"❌ To cancel, use /cancel_schedule {quiz_id}",
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"Quiz {quiz_id} scheduled for chat {chat_id} at {scheduled_time}")
    
    except Exception as e:
        logger.error(f"Error in schedule_quiz: {e}", exc_info=True)
        await safe_send_message(
            context, chat_id,
            "❌ Error scheduling quiz. Please check the format and try again."
        )

async def cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel_schedule command - Cancel a scheduled quiz"""
    try:
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        

        if chat_type != ChatType.GROUP and chat_type != ChatType.SUPERGROUP:
            await safe_send_message(
                context, chat_id,
                "⚠️ This command can only be used in groups."
            )
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(
                    context, chat_id,
                    "🚫 You must be an admin to cancel a scheduled quiz."
                )
                return
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            await safe_send_message(
                context, chat_id,
                "❌ Error checking admin permissions."
            )
            return
        

        if len(context.args) < 1:

            scheduled_quizzes = await db_manager.find("scheduled", {
                "chat_id": chat_id,
                "status": "pending"
            })
            
            if not scheduled_quizzes:
                await safe_send_message(
                    context, chat_id,
                    "📭 No scheduled quizzes found for this group."
                )
                return
            
            message = "📋 *Scheduled Quizzes:*\n\n"
            for i, quiz in enumerate(scheduled_quizzes, 1):
                quiz_data = await db_manager.find_one("questions", {"question_set_id": quiz["quiz_id"]})
                quiz_name = quiz_data.get("quiz_name", "Unnamed Quiz") if quiz_data else "Unknown Quiz"
                
                message += (
                    f"{i}. *{escape_markdown(quiz_name)}*\n"
                    f"   🆔 ID: `{quiz['quiz_id']}`\n"
                    f"   ⏰ Time: {quiz['scheduled_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"   👤 By: <code>{quiz['scheduled_by']}</code>\n"
                    f"   ❌ Cancel: `/cancel_schedule {quiz['quiz_id']}`\n\n"
                )
            
            message += "To cancel a quiz, use `/cancel_schedule <quiz_id>`"
            
            await safe_send_message(
                context, chat_id,
                message,
                parse_mode=ParseMode.HTML
            )
            return
        
        quiz_id = context.args[0]
        

        deleted = await db_manager.delete_one("scheduled", {
            "chat_id": chat_id,
            "quiz_id": quiz_id,
            "status": "pending"
        })
        
        if deleted:
            await safe_send_message(
                context, chat_id,
                f"✅ Scheduled quiz `{quiz_id}` has been cancelled."
            )
            logger.info(f"Scheduled quiz {quiz_id} cancelled for chat {chat_id}")
        else:
            await safe_send_message(
                context, chat_id,
                f"❌ No scheduled quiz found with ID `{quiz_id}`."
            )
    
    except Exception as e:
        logger.error(f"Error in cancel_schedule: {e}", exc_info=True)
        await safe_send_message(
            context, chat_id,
            "❌ Error cancelling scheduled quiz."
        )

async def stop_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command"""
    try:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        
        session = await session_manager.get_session(chat_id)
        if not session:
            await safe_send_message(context, chat_id, "⚠️ No quiz is currently ongoing.")
            return
        

        if chat_type == ChatType.PRIVATE:
            if session.get("is_private"):
                await end_private_quiz(chat_id, context)
            else:

                await session_manager.cancel_quiz_task(chat_id)
                await session_manager.delete_session(chat_id)
            await safe_send_message(context, chat_id, "🚫 The quiz has been stopped.")
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(context, chat_id, "🚫 You must be an admin to stop the quiz.")
                return
        except Exception as e:
            await safe_send_message(context, chat_id, f"❌ Error checking admin status: {e}")
            return
        

        await session_manager.cancel_quiz_task(chat_id)
        await end_group_quiz(chat_id)
        await safe_send_message(context, chat_id, "🚫 The quiz has been stopped by an admin.")
    
    except Exception as e:
        logger.error(f"Error in stop_quiz: {e}", exc_info=True)
        await safe_send_message(context, chat_id, "❌ Error stopping quiz.")

async def pause_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pause command"""
    try:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        
        session = await session_manager.get_session(chat_id)
        if not session:
            await safe_send_message(context, chat_id, "⚠️ No quiz is currently running.")
            return
        

        if chat_type == ChatType.PRIVATE:
            await session_manager.update_session(chat_id, {"paused": True})
            await safe_send_message(context, chat_id, "⏸ Quiz has been paused. Use /resume to continue.")
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(context, chat_id, "🚫 You must be an admin to pause the quiz.")
                return
        except Exception as e:
            await safe_send_message(context, chat_id, f"❌ Error checking admin status: {e}")
            return
        
        await session_manager.update_session(chat_id, {"paused": True})
        await safe_send_message(context, chat_id, "⏸ Quiz has been paused by an admin. Use /resume to continue.")
    
    except Exception as e:
        logger.error(f"Error in pause_quiz: {e}", exc_info=True)

async def resume_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /resume command"""
    try:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        
        session = await session_manager.get_session(chat_id)
        if not session or not session.get("paused"):
            await safe_send_message(context, chat_id, "⚠️ No quiz is currently paused.")
            return
        

        if chat_type == ChatType.PRIVATE:
            await session_manager.update_session(chat_id, {"paused": False})
            await safe_send_message(context, chat_id, "▶️ Quiz resumed!")
            

            if session.get("is_private") and session.get("waiting_for_answer"):
                current_idx = session.get("current_index", 0)
                if current_idx < len(session.get("questions", [])):
                    await send_private_question(chat_id, context, current_idx)
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(context, chat_id, "🚫 You must be an admin to resume the quiz.")
                return
        except Exception as e:
            await safe_send_message(context, chat_id, f"❌ Error checking admin status: {e}")
            return
        
        await session_manager.update_session(chat_id, {"paused": False})
        await safe_send_message(context, chat_id, "▶️ Quiz resumed by an admin!")
    
    except Exception as e:
        logger.error(f"Error in resume_quiz: {e}", exc_info=True)

async def fast_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fast command - decrease timer"""
    try:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        
        seconds = 5
        if context.args and context.args[0].isdigit():
            seconds = int(context.args[0])
        
        session = await session_manager.get_session(chat_id)
        if not session:
            await safe_send_message(context, chat_id, "⚠️ No quiz is currently running.")
            return
        

        if chat_type == ChatType.PRIVATE:
            offset = session.get("modified_timer_offset", 0) - seconds
            await session_manager.update_session(chat_id, {"modified_timer_offset": offset})
            await safe_send_message(
                context, chat_id,
                f"⏱️ Quiz timer decreased by {seconds} seconds per question (faster pace)."
            )
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(context, chat_id, "🚫 You must be an admin to adjust the quiz timer.")
                return
        except Exception as e:
            await safe_send_message(context, chat_id, f"❌ Error checking admin status: {e}")
            return
        
        offset = session.get("modified_timer_offset", 0) - seconds
        await session_manager.update_session(chat_id, {"modified_timer_offset": offset})
        await safe_send_message(
            context, chat_id,
            f"⏱️ Quiz timer decreased by {seconds} seconds per question (faster pace) by an admin."
        )
    
    except Exception as e:
        logger.error(f"Error in fast_quiz: {e}", exc_info=True)

async def slow_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /slow command - increase timer"""
    try:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        
        seconds = 5
        if context.args and context.args[0].isdigit():
            seconds = int(context.args[0])
        
        session = await session_manager.get_session(chat_id)
        if not session:
            await safe_send_message(context, chat_id, "⚠️ No quiz is currently running.")
            return
        

        if chat_type == ChatType.PRIVATE:
            offset = session.get("modified_timer_offset", 0) + seconds
            await session_manager.update_session(chat_id, {"modified_timer_offset": offset})
            await safe_send_message(
                context, chat_id,
                f"⏱️ Quiz timer increased by {seconds} seconds per question (slower pace)."
            )
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(context, chat_id, "🚫 You must be an admin to adjust the quiz timer.")
                return
        except Exception as e:
            await safe_send_message(context, chat_id, f"❌ Error checking admin status: {e}")
            return
        
        offset = session.get("modified_timer_offset", 0) + seconds
        await session_manager.update_session(chat_id, {"modified_timer_offset": offset})
        await safe_send_message(
            context, chat_id,
            f"⏱️ Quiz timer increased by {seconds} seconds per question (slower pace) by an admin."
        )
    
    except Exception as e:
        logger.error(f"Error in slow_quiz: {e}", exc_info=True)

async def normal_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /normal command - reset timer"""
    try:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id
        chat_type = update.message.chat.type
        
        session = await session_manager.get_session(chat_id)
        if not session:
            await safe_send_message(context, chat_id, "⚠️ No quiz is currently running.")
            return
        

        if chat_type == ChatType.PRIVATE:
            await session_manager.update_session(chat_id, {"modified_timer_offset": 0})
            await safe_send_message(
                context, chat_id,
                "⏱️ Quiz timer reset to default speed for each question."
            )
            return
        

        try:
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            if chat_member.status not in ["administrator", "creator"]:
                await safe_send_message(context, chat_id, "🚫 You must be an admin to adjust the quiz timer.")
                return
        except Exception as e:
            await safe_send_message(context, chat_id, f"❌ Error checking admin status: {e}")
            return
        
        await session_manager.update_session(chat_id, {"modified_timer_offset": 0})
        await safe_send_message(
            context, chat_id,
            "⏱️ Quiz timer reset to default speed for each question by an admin."
        )
    
    except Exception as e:
        logger.error(f"Error in normal_quiz: {e}", exc_info=True)

async def compare_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle compare results callback"""
    try:
        query = update.callback_query
        user_id = query.from_user.id
        _, quiz_id, chat_id = query.data.split("_")
        chat_id = int(chat_id)
        
        results_dir = f"quiz_results/{quiz_id}"
        
        if not os.path.exists(results_dir):
            await query.answer(text="No result ...", show_alert=True)
            return
        
        files = [f for f in os.listdir(results_dir) 
                if f.startswith(str(chat_id)) and f.endswith('.json')]
        
        if not files:
            await query.answer(text="📊 No result found", show_alert=True)
            return
        
        await query.answer(
            text="📊 Generating detailed analysis... it will be sent personally.",
            show_alert=True
        )
        
        files.sort(reverse=True)
        
        with open(f"{results_dir}/{files[0]}", 'r', encoding='utf-8') as f:
            quiz_results = json.load(f)
        
        quiz_data = await db_manager.find_one("questions", {"question_set_id": quiz_id})
        if not quiz_data:
            await query.answer(text="No data", show_alert=True)
            return
        

        if generate_analysis_html:
            html_content = await generate_analysis_html(quiz_results, quiz_data)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = f"reports/{chat_id}_{quiz_id}_analysis_{timestamp}.html"
            os.makedirs("reports", exist_ok=True)
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            with open(html_file, 'rb') as f:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=f,
                    filename=f"quiz_analysis_{timestamp}.html",
                    caption="Analysis report! Compare yourself."
                )
    
    except Exception as e:
        logger.error(f"Error comparing results: {e}", exc_info=True)
        await query.answer(text="❌ Error generating analysis", show_alert=True)

# ═══════════════════════════════════════════════════════════════════════════
# POLL ANSWER HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poll answers"""
    try:
        poll_answer = update.poll_answer
        poll_id = poll_answer.poll_id
        user_id = poll_answer.user.id
        user_name = poll_answer.user.first_name
        
        if not poll_answer.option_ids:
            return
        
        option_id = poll_answer.option_ids[0]
        current_time = time.time()
        

        for chat_id in list(session_manager.sessions.keys()):
            session = await session_manager.get_session(chat_id)
            
            if session and session.get("is_private") and poll_id == session.get("active_poll_id"):
                await handle_private_poll_answer(poll_id, user_id, option_id, current_time)
                return
        

        for chat_id in list(session_manager.sessions.keys()):
            session = await session_manager.get_session(chat_id)
            if not session or session.get("is_private"):
                continue
            
            if poll_id in session.get("polls", {}):
                if user_id not in session["participants"]:
                    session["participants"][user_id] = {
                        "name": user_name,
                        "answers": {}
                    }
                
                session["participants"][user_id]["answers"][poll_id] = {
                    "option": option_id,
                    "time": current_time
                }
                
                await session_manager.update_session(chat_id, session)
                break
    
    except Exception as e:
        logger.error(f"Error handling poll answer: {e}", exc_info=True)

# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════

async def cleanup_task():
    """Background task for cleanup"""
    while True:
        try:
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
            

            await session_manager.cleanup_old_sessions()
            

            await rate_limiter.cleanup_old_entries()
            

            stats = session_manager.get_stats()
            logger.info(f"System stats: {stats}")
            

            import gc
            collected = gc.collect(generation=0)
            if collected > 0:
                logger.debug(f"Garbage collected {collected} objects")
            

            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                logger.info(f"Memory usage: {memory_mb:.2f} MB")
            except ImportError:
                pass
            except Exception as e:
                logger.error(f"Error checking memory: {e}")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}", exc_info=True)

# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════

async def post_init(application: Application):
    """Post-initialization setup"""
    logger.info("Running post-initialization setup...")
    

    await db_manager.initialize()
    

    global scheduled_quiz_manager
    scheduled_quiz_manager = ScheduledQuizManager(application)
    await scheduled_quiz_manager.start()
    

    asyncio.create_task(cleanup_task())
    
    logger.info("✓ Bot initialization complete")
    logger.info("✓ Hourly cleanup task started")
    logger.info("✓ Simplified group quiz flow enabled")
    logger.info("Shutting down bot...")
async def post_shutdown(application: Application):
    """Cleanup on shutdown"""
    

    if scheduled_quiz_manager:
        await scheduled_quiz_manager.stop()
    

    db_manager.close()
    
    logger.info("✓ Bot shutdown complete")

def main():
    """Main entry point"""
    logger.info("="*80)
    logger.info("PRODUCTION QUIZ BOT - STARTING (SIMPLIFIED VERSION)")
    logger.info("="*80)
    

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    

    application.add_handler(CommandHandler("start", start_quiz))
    application.add_handler(CommandHandler("sdl", schedule_quiz))
    application.add_handler(CommandHandler("schedule", schedule_quiz))
    application.add_handler(CommandHandler("cancel_schedule", cancel_schedule))
    application.add_handler(CommandHandler("pause", pause_quiz))
    application.add_handler(CommandHandler("resume", resume_quiz))
    application.add_handler(CommandHandler("stop", stop_quiz))
    application.add_handler(CommandHandler("slow", slow_quiz))
    application.add_handler(CommandHandler("fast", fast_quiz))
    application.add_handler(CommandHandler("normal", normal_quiz))
    application.add_handler(CommandHandler("check", system_stats))
    application.add_handler(CommandHandler("cleanup", emergency_cleanup))
    application.add_handler(PollAnswerHandler(handle_poll_answer))
    application.add_handler(CallbackQueryHandler(compare_results, pattern="^compare_"))
    
    logger.info("✓ Handlers registered")
    logger.info("✓ Starting polling...")
    

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Bot terminated")
