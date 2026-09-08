"""
╔══════════════════════════════════════════════════════════════════════════╗
║                      QUIZBOT — Main Bot (Pyrogram)                       ║
║                                                                          ║
║  A powerful Telegram quiz bot built with Pyrogram.                       ║
║  Supports quiz creation, analytics, file imports, inline queries,        ║
║  broadcast, assignments, HTML reports, and much more.                    ║
║                                                                          ║
║  Sponsored by  : Qzio — qzio.in                                         ║
║  Developed by  : devgagan — devgagan.in                                  ║
║  License       : MIT                                                     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
import asyncio, aiohttp, html, io, json, logging, os, random, re, string, sys, traceback, fractions, uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import aiofiles
from collections import Counter, defaultdict
import gc, requests
import pymongo
from pymongo.errors import PyMongoError
from sympy.parsing.latex import parse_latex
from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorClient

from pyrogram import Client, filters
from pyrogram.enums import PollType, ChatType
from pyrogram.errors import (
    ChatAdminRequired, FloodWait, InviteHashExpired, InviteHashInvalid,
    UserAlreadyParticipant, UserNotParticipant
)
from pyrogram.types import InlineQueryResultArticle, InlineKeyboardMarkup, InlineKeyboardButton, InputTextMessageContent

from pyrogram.raw.functions.messages import GetPollVotes, GetPollResults
from pyrogram.raw.types import InputPeerChat
from pyrogram.types import (
    Message, User, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent
)
from func import clean_html
from ai_quiz import generate_questions_txt_from_file
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import binascii
import base64
import binascii
import time
from bson import ObjectId
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import (
    API_ID, API_HASH, BOT_TOKEN, BOT_TOKEN_2,
    MONGO_URI, MONGO_URI_2, MONGO_URIX, DB_NAME,
    OWNER_ID, LOG_GROUP, FORCE_SUB, BOT_GROUP, CHANNEL_ID,
    MASTER_KEY, IV_KEY, FREEMIUM_LIMIT, PREMIUM_LIMIT,
    PAY_API, YT_COOKIES, INSTA_COOKIES, UMODE, FREE_BOT
)

app = Client("quizbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=50)

# ── Database connections ──────────────────────────────────────────────────────
client_db = pymongo.MongoClient(MONGO_URI)
db = client_db[DB_NAME]
users_collection     = db["quiz_users"]
questions_collection = db["questions"]
auth_chats_collection = db["auth_chats"]

mongo_client = pymongo.MongoClient(MONGO_URI_2)
mdb = mongo_client["assignment_bot"]
assignments_collection = mdb["assignments"]
submissions_collection = mdb["submissions"]

cl2_db = pymongo.MongoClient(MONGO_URI_2)
db2 = cl2_db[DB_NAME]
uc_2 = db2["quiz_users"]
qc_2 = db2["questions"]
ac_2 = db2["auth_chats"]

clientX = AsyncIOMotorClient(MONGO_URIX)
dbx = clientX.quiz_bot_db
quizzes_collection = dbx.quizzes
filter_collection  = dbx.user_filters  # kept for compatibility

BOT_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Constants ─────────────────────────────────────────────────────────────────
chatn     = "AIpha_World"
PAGE_SIZE = 10

# ── State ─────────────────────────────────────────────────────────────────────
ongoing_edits   = {}
user_quiz_data  = {}
broadcast_active = False
TEMP_ACCESS     = {}

import binascii
MASTER_KEY_HEX = binascii.hexlify(MASTER_KEY.encode() if isinstance(MASTER_KEY, str) else MASTER_KEY).decode()
IV_HEX         = binascii.hexlify(IV_KEY.encode() if isinstance(IV_KEY, str) else IV_KEY).decode()
MASTER_KEY_B   = binascii.unhexlify(MASTER_KEY_HEX)
IV_B           = binascii.unhexlify(IV_HEX.ljust(32, "0"))[:16]

user_quiz_data = {}
broadcast_active = False 

TEMP_ACCESS = {}

MASTER_KEY_HEX = "2e4c5fe382452f9f636b059b4f5cfdfa"
IV_HEX = "4048894e29ea"

MASTER_KEY = binascii.unhexlify(MASTER_KEY_HEX)
IV = binascii.unhexlify(IV_HEX.ljust(32, '0'))[:16]

def encrypt_test_id(test_id: str) -> str:
    cipher = AES.new(MASTER_KEY, AES.MODE_CBC, IV)
    padded_data = pad(test_id.encode(), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_test_id(encrypted_id: str) -> str:
    MASTER_KEY = binascii.unhexlify(MASTER_KEY_HEX)
    IV = binascii.unhexlify(IV_HEX.ljust(32, '0'))[:16]

    padding_needed = 4 - (len(encrypted_id) % 4)
    if padding_needed and padding_needed != 4:
        encrypted_id += "=" * padding_needed

    cipher = AES.new(MASTER_KEY, AES.MODE_CBC, IV)
    encrypted_data = base64.urlsafe_b64decode(encrypted_id)
    decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    return decrypted.decode()

FEATURES_TEXT = """> **📢 Features Showcase of Quizbot!** 🚀  

🔹 **Create questions from text** just by providing a ✅ mark to the right options.  
🔹 **Marathon Quiz Mode:** Create unlimited questions for a never-ending challenge.  
🔹 **Convert Polls to Quizzes:** Simply forward polls (e.g., from @Xd_Quiz_Bot), and unnecessary elements like `[1/100]` will be auto-removed!  
🔹 **Smart Filtering:** Remove unwanted words (e.g., usernames, links) from forwarded polls.  
🔹 **Skip, Pause & Resume** ongoing quizzes anytime.  
🔹 **Bulk Question Support** via ChatGPT output.  
🔹 **Negative Marking** for accurate scoring.  
🔹 **Edit Existing Quizzes** with ease like shuffle title editing timer adding removing questions and many more.  
🔹 **Quiz Analytics:** View engagement, tracking how many users completed the quiz.  
🔹 **Inline Query Support:** Share quizzes instantly via quiz ID.  
🔹 **Free & Paid Quizzes:** Restrict access to selected users/groups—perfect for paid quiz series!  
🔹 **Assignment Management:** Track student responses via bot submissions.  
🔹 **View Creator Info** using the quiz ID.  
🔹 **Generate Beautiful HTML Reports** with score counters, plus light/dark theme support.  
🔹 **Manage Paid Quizzes:** Add/remove users & groups individually or in bulk.  
🔹 **Video Tutorials:** Find detailed guides in the Help section.  
🔹 **Auto-Send Group Results:** No need to copy-paste manually—send all results in one click! 
🔹 **Create Sectional Quiz:** You can create different sections with different timing 🥳.
🔹 **Slow/Fast**: Slow or fast ongoing quiz.
🔹 **OCR Update** - Now extract text from PDFs or Photos
🔹 **Comparison** of Result with accuracy, percentile and percentage
🔹 Create Questions from TXT.
🔹 Advance Mechanism with 99.99% uptime.
🔹 Automated link and username removal from Poll's description and questions.
🔹 Auto txt quiz creation from Wikipedia Britannia bbc news and 20+ articles sites.

> **Latest update 🆕**

🔹 Auto clone from official quizbot.
🔹 Create from polls/already finishrd quizzes in channels and all try /extract.
🔹 Create from Drishti IAS web Quiz try /quiztxt.

> **🚀 Upcoming Features:** 

🔸 Advance Engagement saving + later on perspective.
🔸 More optimizations for a smoother experience.
🔸 Suprising Updates...

> **📊 Live Tracker & Analysis:** 

✅ **Topper Comparisons**  
✅ **Detailed Quiz Performance Analytics**  
"""

def generate_random_id():
    return "GGN" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))

async def is_paid_user(user_id):
    """Check if user has premium access via the API."""
    try:
        from func import is_premium_user
        return await is_premium_user(user_id)
    except Exception:
        return False

async def remove_baby(text, keep_links: bool = False):
    """Strip noise from imported text.

    By default removes Q-numbering AND any URLs / @mentions — useful for
    cleaning question / option text imported from polls or PDFs that often
    contain promo links from the original creator.

    Pass `keep_links=True` for fields the user *intends* to be promotional
    (explanations, reference / reply_text). Otherwise their own
    `JOIN ➤ @MyChannel` style notes get silently stripped.
    """
    if not text:
        return text

    text = re.sub(r'[\[\(]\s*Q\.?\s*\d+\s*/\s*\d+\s*[\]\)]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bQ\.?\s*\d+\s*/\s*\d+\)?', '', text, flags=re.IGNORECASE)

    text = re.sub(r'[\[\(]?\s*Q\.?\s*\d+\s*[\]\)]?', '', text, flags=re.IGNORECASE)

    if not keep_links:
        pattern = r"(https?://[^\s]+|t\.me/[^\s]+|@\w+)"
        text = re.sub(pattern, "", text)

    return text.strip()
    

@app.on_message(filters.command("delall") & filters.user(OWNER_ID))  # Owner ID is 1234
async def delete_all_quizzes(client, message: Message):
    result = questions_collection.delete_many({})
    await message.reply(f"✅ Deleted {result.deleted_count} quiz records from the database.")

async def subscribe(app, message):
    if LOG_GROUP:
        try:
          user = await app.get_chat_member(LOG_GROUP, message.from_user.id)
          if str(user.status) == "ChatMemberStatus.BANNED":
              await message.reply_text("You are Banned. Contact -- Alpha World")
              return 1
        except UserNotParticipant:
            caption = f"Join our channel to use the bot"
            await message.reply_photo(photo="https://graph.org/file/d44f024a08ded19452152.jpg",caption=caption, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Now...", url=f"https://t.me/AIpha_World")]]))
            return 1
        except Exception:
            await message.reply_text("Something Went Wrong. Contact us Alpha World...")
            return 1

async def send_document_http(chat_id: int, file_id: str, caption: str):
    payload = {
        "chat_id": chat_id,
        "document": file_id,
        "caption": caption
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BOT_API_URL}/sendDocument",
            json=payload
        ) as resp:
            return await resp.json()
            

# ─── /clone COMMAND (PRIVATE ONLY) ──────────────────────────────────────────
@app.on_message(filters.command("clone") & filters.private)
async def clone_quiz(client, message):
    command_parts = message.text.split(maxsplit=1)
    if len(message.command) != 2:
        await message.reply_text("❌ Usage:\n`/clone QUIZID`\nor\n`/clone https://t.me/<bot>?start=QUIZID`")
        return

    input_text = command_parts[1].strip()
    quiz_id = input_text.split('=')[-1] if '=' in input_text else input_text
    chat_id = message.chat.id
    user_id = message.from_user.id

    status = await message.reply_text("🔍 Searching quiz database...")

    # 1) Try the file-based encrypted quizzes collection (legacy /clone behaviour)
    quiz_file = await quizzes_collection.find_one({"quiz_id": quiz_id})

    if quiz_file:
        caption = (
            f"📘 Quiz Cloned\n"
            f"🆔 {quiz_id}\n"
            f"📊 Questions: {quiz_file.get('question_count', 'N/A')}"
        )

        try:
            await app.send_document(
                chat_id=chat_id,
                document=quiz_file["file_id"],
                caption=caption,
            )
            await status.delete()
            return
        except Exception as e:
            print(f"clone primary send_document failed: {e}")
            await status.edit("⚠️ Primary send failed. Trying fallback...")

        result = await send_document_http(
            chat_id=chat_id,
            file_id=quiz_file["file_id"],
            caption=caption,
        )

        if result.get("ok"):
            await status.delete()
            await message.reply("✅ Sent!!")
        else:
            await status.edit("❌ Failed to send quiz file via fallback.")
        return

    # 2) Fallback: clone a regular question-set quiz from this bot's database
    source = questions_collection.find_one({"question_set_id": quiz_id})
    if not source:
        try:
            source = qc_2.find_one({"question_set_id": quiz_id})
        except Exception:
            source = None

    if not source:
        await status.edit(
            "❌ Quiz not found.\n\n"
            "ℹ️ `/clone` can only clone quizzes that exist in this bot. "
            "Quizzes from other bots cannot be imported."
        )
        return

    new_quiz_id = generate_random_id()
    new_doc = {
        "question_set_id": new_quiz_id,
        "creator_id": user_id,
        "quiz_name": source.get("quiz_name", "Cloned Quiz"),
        "questions": source.get("questions", []),
        "sections": source.get("sections", []),
        "timer": source.get("timer"),
        "type": source.get("type", "free"),
        "negative_marking": source.get("negative_marking", 0),
        "promo": source.get("promo"),
        "cloned_from": quiz_id,
    }

    try:
        questions_collection.insert_one(new_doc)
    except Exception as e:
        await status.edit(f"❌ Failed to clone quiz: {e}")
        return

    question_count = len(new_doc["questions"])
    timer = new_doc["timer"]
    quiz_name = new_doc["quiz_name"]
    nmark = new_doc["negative_marking"]

    start_deep_link = f"https://t.me/{client.me.username}?start={new_quiz_id}"
    group_start_deep_link = f"https://t.me/{client.me.username}?startgroup={new_quiz_id}"

    text = (
        f"> **✅ Quiz Cloned Successfully!**\n\n"
        f"**💳 Quiz Name:** {quiz_name}\n"
        f"**#️⃣ Questions:** {question_count}\n"
        f"**⏰ Timer:** {timer} seconds\n"
        f"**🆔 New Quiz ID:** `{new_quiz_id}`\n"
        f"**📋 Cloned From:** `{quiz_id}`\n"
        f"**🏴‍☠️ -ve Marking:** `{nmark}`\n"
        f"**👤 Owner:** {message.from_user.mention}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Start Quiz Now", url=start_deep_link)],
        [InlineKeyboardButton("🚀 Start Quiz in Group", url=group_start_deep_link)],
        [InlineKeyboardButton("🔗 Share Quiz", switch_inline_query=new_quiz_id)],
    ])

    await status.delete()
    await message.reply(text, reply_markup=keyboard)
        

@app.on_message(filters.command("convertall") & filters.chat(chatn))
async def convert_all_paid_to_free(client, message):
    k = await message.reply_text("Converting paid to free plz wait")
    updated_count = questions_collection.update_many(
        {"type": "paid"},
        {"$set": {"type": "free"}}
    ).modified_count
    
    await k.edit(f"Converted {updated_count} quizzes from Paid to Free.")

@app.on_message(filters.command("del") & filters.private)
async def delete_quiz(client, message: Message):
    args = message.text.split()
    if len(args) != 2:
        await message.reply("❌ Please provide a valid Question Set ID. Example: `/del 12345`")
        return

    question_set_id = args[1]
    user_id = message.from_user.id

    quiz = questions_collection.find_one({"question_set_id": question_set_id})

    if not quiz:
        await message.reply("❌ No quiz found with the given Question Set ID.")
        return

    if quiz["creator_id"] != user_id:
        await message.reply("❌ You are not authorized to delete this quiz.")
        return

    questions_collection.delete_one({"question_set_id": question_set_id})
    await message.reply(f"✅ Quiz with Question Set ID `{question_set_id}` has been deleted.")


def _fix_ar_question(question_text: str, options: list, correct_option_id: int):
    """
    Detect and fix an assertion-reason question that was parsed incorrectly.

    Wrong case: parser stored only the Assertion line as `question`, and put
    Reason + instruction + all 4 AR options into `options` (6+ items total).

    Correct case: full Assertion+Reason+instruction block in `question`, only
    the 4 answer choices in `options`.

    Returns (new_question, new_options, new_correct_option_id) on success,
    or None if no fix is needed / not possible.
    """
    _AR_DETECT = re.compile(
        r'(Reason\s*\(R\)|कारण\s*\(R\)|Assertion\s*\(A\)|कथन\s*\(A\))',
        re.IGNORECASE)
    _AR_INSTR = re.compile(
        r'(कूट|नीचे\s+दिए|Choose\s+the\s+correct|correct\s+answer\s+using)',
        re.IGNORECASE)
    _DASH_PFX = re.compile(r'^[-•]\s*')

    all_text = question_text + "\n" + "\n".join(options)

    # Not an AR question at all
    if not _AR_DETECT.search(all_text):
        return None

    # Already correctly parsed: exactly 4 options, none containing AR keywords
    if len(options) == 4 and not any(_AR_DETECT.search(opt) for opt in options):
        return None

    # Rebuild all non-empty lines
    all_lines = [_DASH_PFX.sub('', ln).strip()
                 for ln in all_text.split('\n') if ln.strip()]

    # Find the instruction divider line
    instr_idx = None
    for i, ln in enumerate(all_lines):
        if _AR_INSTR.search(ln):
            instr_idx = i
            break

    if instr_idx is not None:
        q_lines = all_lines[:instr_idx + 1]
        opt_lines = [ln for ln in all_lines[instr_idx + 1:]
                     if not ln.lower().startswith('ex:')]
    else:
        # No instruction line — treat last 4 as options
        non_ex = [ln for ln in all_lines if not ln.lower().startswith('ex:')]
        if len(non_ex) < 5:
            return None
        q_lines = non_ex[:-4]
        opt_lines = non_ex[-4:]

    new_question = "\n".join(q_lines).strip()
    new_options = [ln for ln in opt_lines if ln][:4]

    if len(new_options) < 4:
        return None

    # Remap correct_option_id: find old correct text in the new options list
    new_correct_id = None
    if 0 <= correct_option_id < len(options):
        old_correct_text = options[correct_option_id].strip()
        for i, opt in enumerate(new_options):
            if opt.strip() == old_correct_text:
                new_correct_id = i
                break

    if new_correct_id is None:
        # Fallback: count how many option slots were "stolen" by AR body lines
        ar_body_count = sum(
            1 for opt in options
            if _AR_DETECT.search(opt) or _AR_INSTR.search(opt)
        )
        adjusted = correct_option_id - ar_body_count
        new_correct_id = adjusted if 0 <= adjusted < 4 else 0

    return new_question, new_options, new_correct_id


@app.on_message(filters.command("fixquiz") & filters.private)
async def fix_quiz_options(client, message: Message):
    """
    /fixquiz <quiz_id>

    Re-parses every question in the quiz and fixes broken assertion-reason
    questions where the Reason line and instruction line were incorrectly
    stored as poll options.  Updates the quiz in-place in MongoDB.
    Owner or creator only.
    """
    args = message.text.split()
    if len(args) != 2:
        await message.reply(
            "❌ Usage: `/fixquiz <quiz_id>`\n\n"
            "This re-parses every question in the quiz and corrects any "
            "assertion-reason questions where options were parsed incorrectly."
        )
        return

    quiz_id = args[1]
    user_id = message.from_user.id

    quiz = questions_collection.find_one({"question_set_id": quiz_id})
    if not quiz:
        await message.reply(f"❌ No quiz found with ID `{quiz_id}`.")
        return

    if quiz.get("creator_id") != user_id and user_id not in OWNER_ID:
        await message.reply("❌ You are not authorized to fix this quiz.")
        return

    questions = quiz.get("questions", [])
    if not questions:
        await message.reply("❌ This quiz has no questions.")
        return

    status_msg = await message.reply(
        f"🔧 Scanning {len(questions)} questions in quiz `{quiz_id}`..."
    )

    fixed_count = 0
    skipped_count = 0
    updated_questions = []

    for q in questions:
        q_text = q.get("question", "")
        opts = q.get("options", [])
        correct_id = q.get("correct_option_id", 0)

        result = _fix_ar_question(q_text, opts, correct_id)
        if result:
            new_q, new_opts, new_correct = result
            updated_q = dict(q)
            updated_q["question"] = new_q
            updated_q["options"] = new_opts
            updated_q["correct_option_id"] = new_correct
            updated_questions.append(updated_q)
            fixed_count += 1
        else:
            updated_questions.append(q)
            skipped_count += 1

    if fixed_count == 0:
        await status_msg.edit_text(
            f"✅ Quiz `{quiz_id}` — no broken questions found.\n"
            f"All {len(questions)} questions look correct."
        )
        return

    questions_collection.update_one(
        {"question_set_id": quiz_id},
        {"$set": {"questions": updated_questions}}
    )

    await status_msg.edit_text(
        f"✅ Quiz `{quiz_id}` fixed!\n\n"
        f"🔧 Fixed: **{fixed_count}** question(s)\n"
        f"✔️ Already correct: **{skipped_count}** question(s)\n\n"
        f"Re-run the quiz to see the corrected polls."
    )


@app.on_message(filters.command("remall") & filters.private)
async def remove_all_authorized_users(client, message: Message):
    user_id = message.from_user.id

    auth_record = auth_chats_collection.find_one({"creator_id": user_id})

    if not auth_record or not auth_record.get("auth_users"):
        await message.reply("⚠️ You don't have any authorized users to remove.")
        return

    auth_chats_collection.update_one(
        {"creator_id": user_id},
        {"$set": {"auth_users": []}}
    )

    await message.reply("✅ All authorized users have been removed from your list.")

@app.on_message(filters.command("transfer") & filters.user(OWNER_ID))
async def transfer_quizzes(client, m):
    """Transfer all quizzes from one creator to another - Owner only"""
    args = m.text.split()
    
    if len(args) != 3:
        await m.reply(
            "❌ Invalid format!\n\n"
            "**Usage:** `/transfer FROM_ID TO_ID`\n"
            "**Example:** `/transfer 123456789 987654321`"
        )
        return
    
    try:
        from_id = int(args[1])
        to_id = int(args[2])
    except ValueError:
        await m.reply("❌ Both IDs must be valid numbers!")
        return
    
    if from_id == to_id:
        await m.reply("❌ FROM_ID and TO_ID cannot be the same!")
        return
    
    pm = await m.reply(f"🔄 Transferring quizzes from `{from_id}` to `{to_id}`...")
    
    try:

        count = questions_collection.count_documents({"creator_id": from_id})
        
        if count == 0:
            await pm.edit_text(f"❌ No quizzes found for creator ID `{from_id}`")
            return
        

        result = questions_collection.update_many(
            {"creator_id": from_id},
            {"$set": {"creator_id": to_id}}
        )
        
        await pm.edit_text(
            f"✅ **Transfer Complete!**\n\n"
            f"**Transferred:** {result.modified_count} quiz(es)\n"
            f"**From:** `{from_id}`\n"
            f"**To:** `{to_id}`"
        )
        
    except Exception as e:
        await pm.edit_text(f"❌ Transfer failed: {str(e)}")
        print(f"Transfer error: {e}")

@app.on_message(filters.command("add") & filters.private)
async def add_authorized_user(client, message: Message):
    check = await subscribe(app, message)
    if check:  # If user is not subscribed, return early
        return
        
    args = message.text.split()
    try:
        if len(args) != 2:
            raise ValueError("Invalid arguments count.")
        
        target_user_id = int(args[1])  # Will raise ValueError if not an integer
    except ValueError:
        await message.reply("❌ Please provide a valid user ID. Example: `/rem 123456789` or `/rem -123456789`")
        return
        
    user_id = message.from_user.id
    auth_chats_collection.update_one(
        {"creator_id": user_id},
        {"$addToSet": {"auth_users": target_user_id}},
        upsert=True
    )
    await message.reply(f"✅ User {target_user_id} has been authorized.")

# Cancel Command Handler
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_quiz_creation(client, message):
    user_id = message.from_user.id
    

    if user_id in user_quiz_data:

        user_quiz_data.pop(user_id, None)
        await message.reply("❌ Question creation canceled. You can start again by sending a new set of questions.")
    else:
        await message.reply("⚠️ No ongoing question creation to cancel.")

# Command: /rem user_id
@app.on_message(filters.command("rem") & filters.private)
async def remove_authorized_user(client, message: Message):
    args = message.text.split()
    try:
        if len(args) != 2:
            raise ValueError("Invalid arguments count.")
        
        target_user_id = int(args[1])  # Will raise ValueError if not an integer
    except ValueError:
        await message.reply("❌ Please provide a valid user ID. Example: `/rem 123456789` or `/rem -123456789`")
        return

    user_id = message.from_user.id
    auth_chats_collection.update_one(
        {"creator_id": user_id},
        {"$pull": {"auth_users": target_user_id}}
    )
    await message.reply(f"✅ User {target_user_id} has been unauthorized.")
    

# Custom JSON encoder that handles MongoDB types
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

CACHE_DIR = "quiz_cache"
CACHE_EXPIRY = 600  # 10 minutes in seconds
PAGE_SIZE = 5  # Number of quizzes per page

# Ensure cache directory exists
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_cache_file(user_id):
    """Get the cache file path for a user"""
    return os.path.join(CACHE_DIR, f"user_{user_id}.json")

def save_quiz_cache(user_id, quizzes, search_terms=None):
    """Save user's quiz data to a file with custom JSON encoder"""
    cache_file = get_cache_file(user_id)
    cache_data = {
        "data": quizzes,
        "timestamp": time.time(),
        "search_terms": search_terms  # Store search terms if any
    }
    with open(cache_file, "w") as f:
        json.dump(cache_data, f, cls=MongoJSONEncoder)

def load_quiz_cache(user_id):
    """Load user's quiz data from file if it exists and isn't expired"""
    cache_file = get_cache_file(user_id)
    
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, "r") as f:
            cache_data = json.load(f)
        

        if time.time() - cache_data["timestamp"] > CACHE_EXPIRY:
            os.remove(cache_file)  # Delete expired cache
            return None
            
        return cache_data
    except (json.JSONDecodeError, KeyError, FileNotFoundError):

        if os.path.exists(cache_file):
            os.remove(cache_file)
        return None

def prepare_quiz_for_cache(quiz):
    """Convert MongoDB document to a serializable dictionary"""
    if not isinstance(quiz, dict):
        quiz = dict(quiz)
    

    for key, value in quiz.items():
        if isinstance(value, ObjectId):
            quiz[key] = str(value)
        elif isinstance(value, datetime):
            quiz[key] = value.isoformat()
    
    return quiz

def filter_quizzes_by_search(quizzes, search_terms):
    """Filter quizzes by search terms in quiz name"""
    if not search_terms:
        return quizzes
    
    filtered_quizzes = []
    search_terms_lower = [term.lower() for term in search_terms]
    
    for quiz in quizzes:
        quiz_name = quiz.get('quiz_name', '').lower()
        

        if all(term in quiz_name for term in search_terms_lower):
            filtered_quizzes.append(quiz)
    
    return filtered_quizzes

async def send_quiz_page(client, message, quizzes, page_number, user_id, search_terms=None):
    """Send a page of quizzes to the user"""
    start = page_number * PAGE_SIZE
    end = start + PAGE_SIZE
    current_page_quizzes = quizzes[start:end]

    if not current_page_quizzes:
        await message.edit_text("❌ No quizzes found on this page.")
        return

    quiz_list = "\n".join(
        [
            f"**{start + i + 1}. {quiz.get('quiz_name', 'Unnamed Quiz')}**\n"
            f"    - 🆔 Quiz ID: `{quiz.get('question_set_id', 'N/A')}`\n"
            f"    - 🗄️ Database: `{quiz.get('source_db', 'Unknown')}`\n"
            f"    - 📄 Type: {'Paid' if quiz.get('type') == 'paid' else 'Free'}\n"
            f"    - 👥 Users: {quiz.get('total_participation', 0)}\n"
            f"    - 🗽 Start: `/start {quiz.get('question_set_id', 'N/A')}`\n"
            f"    - 🥊 Share: `@Xd_Quiz_Bot {quiz.get('question_set_id', 'N/A')}`\n"
            f"    - 🖊️ Edit: `/edit {quiz.get('question_set_id', 'N/A')}`\n\n────────────────\n"
            for i, quiz in enumerate(current_page_quizzes)
        ]
    )

    keyboard = []
    if len(quizzes) > PAGE_SIZE:
        buttons = []
        if page_number > 0:
            buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"prev:{page_number}:{user_id}"))
        if end < len(quizzes):
            buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"next:{page_number}:{user_id}"))
        

        total_pages = (len(quizzes) + PAGE_SIZE - 1) // PAGE_SIZE
        buttons.append(InlineKeyboardButton(f"📄 {page_number + 1}/{total_pages}", callback_data="page_info"))
        
        keyboard.append(buttons)
    

    if search_terms:
        keyboard.append([InlineKeyboardButton("🔍 Clear Search", callback_data=f"clear_search:{user_id}")])
    

    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{user_id}"), 
                     InlineKeyboardButton("❌ Close", callback_data=f"close:{user_id}")])

    total_quizzes = len(quizzes)
    qc2_count = len([q for q in quizzes if q.get('source_db') == 'qc_2'])
    qc_count = len([q for q in quizzes if q.get('source_db') == 'question_collection'])
    

    header_text = f"📝 **Your Quizzes (Page {page_number + 1})**\n"
    if search_terms:
        header_text += f"🔍 **Search:** `{' '.join(search_terms)}`\n"
    header_text += f"📊 Total: {total_quizzes} | DB 2: {qc2_count} | DB 1: {qc_count}\n\n"

    await message.edit_text(
        f"{header_text}{quiz_list}",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

@app.on_message(filters.command("myquizzes") & filters.private)
async def list_user_quizzes(client, message: Message):

    check = await subscribe(app, message)
    if check:  # If user is not subscribed, return early
        return
        
    user_id = message.from_user.id
    

    search_terms = []
    if len(message.command) > 1:

        search_text = ' '.join(message.command[1:])

        search_terms = search_text.split()
    

    if search_terms:
        progress_message = await message.reply(f"🔍 Searching quizzes for: `{' '.join(search_terms)}`...")
    else:
        progress_message = await message.reply("🔍 Fetching all quizzes from both databases...")
    

    quizzes_qc2 = list(qc_2.find({"creator_id": user_id}))
    quizzes_question_collection = list(questions_collection.find({"creator_id": user_id}))
    

    all_quizzes = []
    

    for quiz in quizzes_qc2:
        quiz = prepare_quiz_for_cache(quiz)
        quiz['source_db'] = 'DB 2'
        all_quizzes.append(quiz)
    

    for quiz in quizzes_question_collection:
        quiz = prepare_quiz_for_cache(quiz)
        quiz['source_db'] = 'DB 1'
        all_quizzes.append(quiz)
    

    if search_terms:
        all_quizzes = filter_quizzes_by_search(all_quizzes, search_terms)
    
    if not all_quizzes:
        if search_terms:
            await progress_message.edit_text(f"❌ No quizzes found containing: `{' '.join(search_terms)}`")
        else:
            await progress_message.edit_text("❌ You haven't created any quizzes in either database.")
        return
    

    save_quiz_cache(user_id, all_quizzes, search_terms)
    

    await send_quiz_page(client, progress_message, all_quizzes, 0, user_id, search_terms)

@app.on_callback_query(filters.regex("^(prev|next|refresh|clear_search|close):"))
async def handle_quiz_pagination(client, callback_query: CallbackQuery):
    data_parts = callback_query.data.split(":")
    action = data_parts[0]
    user_id = int(data_parts[-1])  # user_id is always the last part
    
    if action == "close":
        await callback_query.message.delete()
        await callback_query.answer("Closed!")
        return
        
    elif action == "refresh":

        cache_file = get_cache_file(user_id)
        if os.path.exists(cache_file):
            os.remove(cache_file)
        

        fake_message = callback_query.message
        fake_message.from_user.id = user_id
        fake_message.command = ["myquizzes"]
        
        await list_user_quizzes(client, fake_message)
        await callback_query.message.delete()
        await callback_query.answer("✅ Quizzes refreshed!")
        return
        
    elif action == "clear_search":

        cache_file = get_cache_file(user_id)
        if os.path.exists(cache_file):
            os.remove(cache_file)
        

        fake_message = callback_query.message
        fake_message.from_user.id = user_id
        fake_message.command = ["myquizzes"]
        
        await list_user_quizzes(client, fake_message)
        await callback_query.message.delete()
        await callback_query.answer("✅ Search cleared!")
        return
    

    page_number = int(data_parts[1])
    

    cache_data = load_quiz_cache(user_id)
    if not cache_data:
        await callback_query.answer("❌ Quiz data expired. Please run /myquizzes again.", show_alert=True)
        return
    
    quizzes = cache_data["data"]
    search_terms = cache_data.get("search_terms")
    
    if not quizzes:
        await callback_query.answer("No quizzes available.", show_alert=True)
        return

    new_page_number = page_number - 1 if action == "prev" else page_number + 1
    await send_quiz_page(client, callback_query.message, quizzes, new_page_number, user_id, search_terms)
    await callback_query.answer()
    
# Inline query handler for quizzes and assignments
@app.on_inline_query()
async def handle_inline_query(client, inline_query):
    query = inline_query.query.strip()

    if not query:
        return

    if not query.startswith("ass_"):

        quiz_data = questions_collection.find_one({"question_set_id": query})
        if not quiz_data:
            quiz_data = qc_2.find_one({"question_set_id": query})
        
        if not quiz_data:

            await inline_query.answer(
                results=[],
                switch_pm_text="No quiz found for this ID",
                switch_pm_parameter="start"
            )
            return

        quiz_name = quiz_data["quiz_name"]
        type = quiz_data["type"]
        question_count = len(quiz_data["questions"])
        timer = quiz_data["timer"]
        nmark = quiz_data.get("negative_marking", 0)
        start_deep_link = f"https://t.me/{client.me.username}?start={query}"
        sections = quiz_data.get("sections", [])  
        
        message_text = (
            f"**💳 Quiz Name:** {quiz_name}\n"
            f"**#️⃣ Questions:** {question_count}\n"
            f"**⏰ Timer:** {timer} seconds\n"
            f"**🆔 Quiz ID:** `{query}`\n"
            f"**🏴‍☠️ -ve Marking:** `{nmark}`\n"
            f"**💰 Type:** `{type}`"
        )
        if sections:
            message_text += "\n\n> **📂 Sections:**"
            for i, section in enumerate(sections, start=1):
                section_name = section["name"]
                start_idx, end_idx = section["question_range"]
                section_timer = section.get("timer", "Not specified")
                message_text += (
                    f"\n\n**Section {i}:** {section_name}\n"
                    f"  - **Questions:** {start_idx} to {end_idx}\n"
                    f"  - **Timer:** {section_timer} seconds"
                )
                

        result = InlineQueryResultArticle(
            id=query,
            title=f"Quiz: {quiz_name}",
            description=f"{question_count} questions | Timer: {timer} seconds",
            input_message_content=InputTextMessageContent(
                message_text=message_text,
                disable_web_page_preview=True
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 Start Quiz Now", url=f"https://t.me/{client.me.username}?start={query}")],
                [InlineKeyboardButton("🚀 Start in Group", url=f"https://t.me/{client.me.username}?startgroup={query}")],
                [InlineKeyboardButton("🔗 Share Quiz", switch_inline_query=query)],
            ])
        )

        await inline_query.answer([result], cache_time=0)

    else:

        assignment_id = query.split('_')[1]  # Extract assignment ID from query
        assignment = assignments_collection.find_one({"assignment_id": assignment_id})

        if assignment:

            assignment_text = f"""
> 📚 **Assignment Details** 📚

🆔 **Assignment ID:** `{assignment_id}`
👨‍🏫 **Creator:** {assignment['creator_name']}
📅 **Date Created:** {assignment['created_date']}
"""

            results = [
                InlineQueryResultArticle(
                    title=f"Assignment {assignment_id}",
                    input_message_content=InputTextMessageContent(assignment_text),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("DO Assignment", callback_data=f"do_{assignment_id}")],
                        [InlineKeyboardButton("Share Assignment", switch_inline_query=query)]
                    ])
                )
            ]

            await inline_query.answer(results=results)
        else:

            await inline_query.answer(
                results=[],
                switch_pm_text="Assignment not found",
                switch_pm_parameter="error"
            )

user_create_limits = {}

@app.on_message(filters.command("create") & filters.private)
async def create_quiz(client, message: Message):
    check = await subscribe(app, message)
    if check:  # If user is not subscribed, return early
        return

    user_id = message.from_user.id
    now = datetime.now()
    if user_id in ongoing_edits:
        del ongoing_edits[user_id]

    if user_id not in user_create_limits:
        user_create_limits[user_id] = {"count": 0, "last_used": None, "warned": False}

    data = user_create_limits[user_id]

    if data["last_used"] is None or data["last_used"].date() != now.date():
        data["count"] = 0
        data["last_used"] = None
        data["warned"] = False

    if data["count"] >= 50:
        if not data["warned"]:  # Warn once per day
            await message.reply("⚠️ You can only use /create **50 times per day**. Try again tomorrow.")
            data["warned"] = True
        return  # Ignore silently

    if data["last_used"] and now - data["last_used"] < timedelta(seconds=30):
        if not data["warned"]:  # Warn once until cooldown ends
            await message.reply("⚠️ Please wait **30 seconds** before using /create again.")
            data["warned"] = True
        return  # Ignore silently

    data["count"] += 1
    data["last_used"] = now
    data["warned"] = False  # Reset warning so next time they get warned again if they break rules

    if user_id in user_quiz_data:
        await message.reply("❌ You're already creating a quiz. Finish it first by typing /done, or /cancel to cancel.")
        return

    await message.reply("✅ **Send the quiz name first.**")
    user_quiz_data[user_id] = {"questions": [], "timer": None, "quiz_name": None, "awaiting_name": True}


@app.on_message(filters.command("aicreate") & filters.private)
async def ai_create_quiz(client, message: Message):
    """Start an AI-powered quiz creation session.

    Usage:  /aicreate            (default: 25 questions per upload)
            /aicreate 40         (generate 40 questions per upload)

    Use /aiconfig to set language, question type, page range, etc.
    Once started, just send a .pdf or .txt and the AI will turn it
    into MCQs that get added to the quiz queue.
    """
    check = await subscribe(app, message)
    if check:
        return

    user_id = message.from_user.id
    if user_id in ongoing_edits:
        del ongoing_edits[user_id]

    if user_id in user_quiz_data:
        await message.reply(
            "❌ You're already creating a quiz. Finish it first by typing /done, "
            "or /cancel to cancel."
        )
        return

    # Optional question count argument
    n_questions = 25
    parts = (message.text or "").split()
    if len(parts) >= 2:
        try:
            n_questions = max(5, min(int(parts[1]), 100))
        except ValueError:
            pass

    user_quiz_data[user_id] = {
        "questions": [],
        "timer": None,
        "quiz_name": None,
        "awaiting_name": True,
        "ai_mode": True,
        "ai_num_questions": n_questions,
        "ai_language": "English",
        "ai_bilingual": False,
        "ai_question_type": "mixed",
        "ai_page_range": None,
    }

    await message.reply(
        "🤖 **AI Quiz Mode enabled**\n\n"
        f"I'll generate **{n_questions} questions** from each upload.\n\n"
        "**Default settings:** Mixed question types · English · All pages\n"
        "Use `/aiconfig` to change language, question type, page range, etc.\n\n"
        "**Supported uploads:**\n"
        "• `.pdf` / `.txt` files\n"
        "• 📷 **Images** — send as a photo or as an image file (.jpg/.png/.webp)\n\n"
        "**Question types available:**\n"
        "• `direct` — standard MCQ\n"
        "• `statement` — I./II./III. statement-based questions\n"
        "• `assertion` — Assertion-Reason questions\n"
        "• `match` — Match the Following questions\n"
        "• `mixed` — auto-mix of all types (default)\n\n"
        "**Provider chain (auto-fallback):**\n"
        "1. **Your own Gemini key** — set with `/gemini <key>` (best quality)\n"
        "2. **Pollinations AI** (free, no key) — text + vision\n"
        "3. **Sandeep AI** (free, no key) — text only\n\n"
        "✅ **Send the quiz name first.**"
    )


@app.on_message(filters.command("aiconfig") & filters.private)
async def ai_config(client, message: Message):
    """Configure AI quiz generation settings for the current session.

    Usage:
        /aiconfig                      — show current settings
        /aiconfig type direct          — question type: direct/statement/assertion/match/mixed
        /aiconfig lang Hindi           — output language (e.g. Hindi, English, Tamil)
        /aiconfig bilingual on         — bilingual mode (language + English on every line)
        /aiconfig bilingual off        — disable bilingual mode
        /aiconfig pages 1-5            — extract only pages 1-5 from PDF
        /aiconfig pages all            — use all pages (default)
        /aiconfig difficulty hard      — difficulty: easy/medium/hard
        /aiconfig count 30             — change question count
        /aiconfig reset                — reset all settings to defaults
    """
    check = await subscribe(app, message)
    if check:
        return

    user_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=2)

    # Must be in an active AI quiz session
    if user_id not in user_quiz_data or not user_quiz_data[user_id].get("ai_mode"):
        await message.reply(
            "❌ No active AI quiz session. Start one first with `/aicreate`."
        )
        return

    ud = user_quiz_data[user_id]

    if len(parts) < 2:
        # Show current settings
        lang = ud.get("ai_language", "English")
        bilingual = ud.get("ai_bilingual", False)
        qtype = ud.get("ai_question_type", "mixed")
        page_range = ud.get("ai_page_range") or "all"
        difficulty = ud.get("ai_difficulty", "medium")
        n_q = ud.get("ai_num_questions", 25)

        lang_display = f"{lang}/English (bilingual)" if bilingual else lang
        await message.reply(
            "⚙️ **Current AI Quiz Settings**\n\n"
            f"• **Questions:** {n_q}\n"
            f"• **Difficulty:** {difficulty}\n"
            f"• **Language:** {lang_display}\n"
            f"• **Question Type:** {qtype}\n"
            f"• **PDF Pages:** {page_range}\n\n"
            "**Commands:**\n"
            "`/aiconfig type <direct|statement|assertion|match|mixed>`\n"
            "`/aiconfig lang <language>`\n"
            "`/aiconfig bilingual <on|off>`\n"
            "`/aiconfig pages <range|all>` — e.g. `1-5`, `3`, `all`\n"
            "`/aiconfig difficulty <easy|medium|hard>`\n"
            "`/aiconfig count <number>`\n"
            "`/aiconfig reset`"
        )
        return

    sub = parts[1].lower().strip()
    val = parts[2].strip() if len(parts) > 2 else ""

    if sub == "reset":
        ud.update({
            "ai_language": "English",
            "ai_bilingual": False,
            "ai_question_type": "mixed",
            "ai_page_range": None,
            "ai_difficulty": "medium",
        })
        await message.reply("✅ AI settings reset to defaults.")
        return

    if sub in ("type", "qtype", "kind"):
        valid = {"direct", "statement", "assertion", "match", "mixed"}
        v = val.lower()
        if v not in valid:
            await message.reply(
                f"❌ Unknown type `{val}`.\n"
                "Valid options: `direct` · `statement` · `assertion` · `match` · `mixed`"
            )
            return
        ud["ai_question_type"] = v
        type_desc = {
            "direct": "Standard MCQ",
            "statement": "Statement-based (I./II./III. + 👇)",
            "assertion": "Assertion-Reason",
            "match": "Match the Following",
            "mixed": "Mixed (all types)",
        }[v]
        await message.reply(f"✅ Question type set to **{type_desc}**.")
        return

    if sub in ("lang", "language"):
        if not val:
            await message.reply("❌ Please specify a language. E.g. `/aiconfig lang Hindi`")
            return
        ud["ai_language"] = val.title()
        bilingual = ud.get("ai_bilingual", False)
        note = " · bilingual mode is ON" if bilingual else ""
        await message.reply(f"✅ Language set to **{val.title()}**{note}.")
        return

    if sub == "bilingual":
        v = val.lower()
        if v in ("on", "yes", "true", "1"):
            ud["ai_bilingual"] = True
            lang = ud.get("ai_language", "English")
            await message.reply(
                f"✅ Bilingual mode ON — every line will appear in both **{lang}** and **English**."
            )
        elif v in ("off", "no", "false", "0"):
            ud["ai_bilingual"] = False
            await message.reply("✅ Bilingual mode OFF.")
        else:
            await message.reply("❌ Use `/aiconfig bilingual on` or `/aiconfig bilingual off`.")
        return

    if sub in ("pages", "page", "range"):
        if not val or val.lower() == "all":
            ud["ai_page_range"] = None
            await message.reply("✅ PDF page range reset — all pages will be used.")
        else:
            ud["ai_page_range"] = val
            await message.reply(f"✅ PDF page range set to **{val}**.")
        return

    if sub in ("difficulty", "diff", "level"):
        v = val.lower()
        if v not in ("easy", "medium", "hard"):
            await message.reply("❌ Valid options: `easy` · `medium` · `hard`")
            return
        ud["ai_difficulty"] = v
        await message.reply(f"✅ Difficulty set to **{v}**.")
        return

    if sub in ("count", "num", "questions", "n"):
        try:
            n = max(5, min(int(val), 100))
            ud["ai_num_questions"] = n
            await message.reply(f"✅ Question count set to **{n}**.")
        except ValueError:
            await message.reply("❌ Please provide a number. E.g. `/aiconfig count 30`")
        return

    await message.reply(
        f"❓ Unknown setting `{sub}`.\n"
        "Run `/aiconfig` with no arguments to see all available options."
    )


@app.on_message(filters.command("gemini") & filters.private)
async def set_gemini_key(client, message: Message):
    """Save / view / remove the user's personal Gemini API key.

    Usage:
        /gemini <api_key>   — save your Gemini key (used for /aicreate)
        /gemini             — show current status
        /gemini remove      — delete your saved key
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    parts = (message.text or "").split(maxsplit=1)

    user_doc = users_collection.find_one({"chat_id": chat_id}) or {}
    has_key = bool(user_doc.get("gemini_api_key"))

    if len(parts) < 2:
        status = "✅ saved" if has_key else "❌ not set"
        await message.reply(
            "🔑 **Gemini API Key**\n\n"
            f"Status: {status}\n\n"
            "**Usage:**\n"
            "`/gemini <your_api_key>` — save your key\n"
            "`/gemini remove` — delete your saved key\n\n"
            "Get a free key at: https://aistudio.google.com/apikey\n\n"
            "Without a key, `/aicreate` falls back to the free Sandeep AI."
        )
        return

    arg = parts[1].strip()
    if arg.lower() in ("remove", "delete", "clear", "off"):
        users_collection.update_one(
            {"chat_id": chat_id},
            {"$unset": {"gemini_api_key": ""}},
            upsert=True,
        )
        await message.reply(
            "🗑️ Your Gemini key has been removed. "
            "`/aicreate` will now use the free Sandeep AI."
        )
        return

    # Basic sanity check (Google keys are usually 35–45 chars, alphanumeric).
    if len(arg) < 20 or " " in arg:
        await message.reply(
            "❌ That doesn't look like a valid Gemini API key. "
            "Get one from https://aistudio.google.com/apikey and resend."
        )
        return

    users_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"gemini_api_key": arg}},
        upsert=True,
    )

    # Try to delete the user's message so the key isn't left in chat.
    try:
        await message.delete()
    except Exception:
        pass

    await message.reply(
        "✅ Your Gemini API key has been saved (and your message deleted).\n\n"
        "`/aicreate` will now use **your own Gemini key** for generation."
    )


@app.on_message(filters.command("done") & filters.private)
async def finish_quiz_creation(client, message: Message):
    user_id = message.from_user.id
    k = 6693636856

    if user_id not in user_quiz_data:
        await message.reply("❌ You haven't started creating a quiz. Use /create first.")
        return

    total_questions = len(user_quiz_data[user_id]["questions"])
    
    if total_questions < 10:
        await message.reply(f"❌ You need at least **10 questions** to finish the quiz.\nCurrently, you have **{total_questions}** questions.")
        return

    if total_questions > 250 and user_id != k:
        await message.reply(f"❌ You cant create more than 250 questions per quiz, (__itna koi quiz krega bhi nhi, hanthi jesa.__)\nCurrently, you have **{total_questions}** questions.")
        return

    user_quiz_data[user_id]["awaiting_section_choice"] = True
    await message.reply(
        "📂 **Do you want sections in your quiz?**",
        reply_markup=_section_keyboard()
    )

@app.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = (
        "Hey, welcome to help!\n\n"
        "> 📌 **Quiz Commands:**\n"
        "/create - Start creating a quiz\n"
        "/myquizzes - List your quizzes\n"
        "/stop - Stop a running quiz in a group\n"
        "/cancel - Cancel the quiz creation\n"
        "/done - Finish quiz creation\n"
        "/edit - Edit questions\n"
        "/del <quizid> - Remove a quiz from the database\n\n"
        "> 📌 **Paid Quiz Management:**\n"
        "/add <chatid> - Authorize a chat or user for your paid quizzes\n"
        "/rem <chatid> - Remove a user from your paid users database\n"
        "/remall - Clear the list of all paid users\n\n"
        "**__Get Video Tutorial 👇__** \n\n> https://youtu.be/lDFvaPf3LoM?si=bUJRI-OHxHobUH8x"
    )
    await message.reply(help_text, disable_web_page_preview=True)


# ─── /aihelp — proxy chat to Copilot API ────────────────────────────────────
AIHELP_API = "https://copilotbysandeep.replit.app/chat"

@app.on_message(filters.command("aihelp"))
async def aihelp_command(client, message: Message):
    parts = message.text.split(maxsplit=1)
    user_text = parts[1].strip() if len(parts) > 1 else ""

    if not user_text and message.reply_to_message and message.reply_to_message.text:
        user_text = message.reply_to_message.text.strip()

    if not user_text:
        await message.reply_text(
            "🤖 **AI Help**\n\nUsage: `/aihelp your question here`\n"
            "Or reply to any text message with `/aihelp`."
        )
        return

    status = await message.reply_text("🤖 Thinking...")

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(AIHELP_API, params={"text": user_text}) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    data = await resp.json()
                    answer = (
                        data.get("response")
                        or data.get("reply")
                        or data.get("answer")
                        or data.get("message")
                        or data.get("text")
                        or json.dumps(data, ensure_ascii=False)
                    )
                else:
                    answer = (await resp.text()).strip()

                if not answer:
                    answer = "🤖 (empty response)"

        # Telegram message limit is 4096 chars
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n…(truncated)"

        await status.edit_text(f"🤖 **AI:**\n\n{answer}", disable_web_page_preview=True)
    except asyncio.TimeoutError:
        await status.edit_text("⏳ AI request timed out. Please try again.")
    except Exception as e:
        await status.edit_text(f"❌ AI request failed: `{e}`")


# ─── /testseries — export quiz as Mock-Test PDF ─────────────────────────────
from pdf_report import generate_mock_test_pdf

CHANNEL_HANDLE = "@AIpha_World"
CHANNEL_LINK = "https://t.me/AIpha_World"

def _resolve_quiz_for_export(quiz_id: str):
    """Look up a quiz by id in either questions collection."""
    src = questions_collection.find_one({"question_set_id": quiz_id})
    if src:
        return src
    try:
        return qc_2.find_one({"question_set_id": quiz_id})
    except Exception:
        return None


@app.on_message(filters.command("testseries"))
async def testseries_command(client, message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply_text(
            "📚 **Test Series — Mock Test PDF**\n\n"
            "Usage: `/testseries <QUIZ_ID>`\n"
            "Example: `/testseries GGNKE5QNH`\n\n"
            "Use `/myquizzes` to see your quiz IDs.",
        )
        return

    raw = parts[1].strip()
    quiz_id = raw.split("=")[-1] if "=" in raw else raw
    quiz_id = quiz_id.split("/")[-1]

    status = await message.reply_text("⏳ Building Mock Test PDF...")

    quiz = _resolve_quiz_for_export(quiz_id)
    if not quiz:
        await status.edit_text(
            f"❌ Quiz `{quiz_id}` not found.\n"
            "Make sure you've copied the correct ID from `/myquizzes`."
        )
        return

    questions = quiz.get("questions") or []
    if not questions:
        await status.edit_text("❌ This quiz has no questions to export.")
        return

    out_dir = "quiz_pdfs"
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"MockTest_{quiz_id}_{stamp}.pdf"
    out_path = os.path.join(out_dir, filename)

    try:
        await asyncio.to_thread(
            generate_mock_test_pdf, quiz, out_path, CHANNEL_HANDLE
        )
    except Exception as e:
        traceback.print_exc()
        await status.edit_text(f"❌ PDF generation failed: `{e}`")
        return

    quiz_name = quiz.get("quiz_name") or "Mock Test"
    total_q = len(questions)
    neg = quiz.get("negative_marking") or 0
    try:
        neg_str = f"-{float(neg):g}"
    except (TypeError, ValueError):
        neg_str = "-0"

    caption = (
        f"📚 **Mock Test**\n\n"
        f"📋 Tests: 1 | ❓ Questions: {total_q}\n"
        f"🎯 Mode: Answer Key at End (exam mode)\n"
        f"📝 {quiz_name}\n"
        f"📚 JOIN ~ {CHANNEL_HANDLE}\n\n"
        f"_Prepared by QuizBot_"
    )

    try:
        await client.send_document(
            chat_id=message.chat.id,
            document=out_path,
            caption=caption,
            file_name=filename,
        )
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Failed to send PDF: `{e}`")
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass


# ─── /poll2txt — convert a forwarded quiz poll into plain text ──────────────
@app.on_message(filters.command("poll2txt"))
async def poll2txt_command(client, message: Message):
    target = message.reply_to_message
    if not target or not target.poll:
        await message.reply_text(
            "🗳 **Poll → Text**\n\n"
            "Reply to a quiz poll with `/poll2txt` and I'll print it as plain text "
            "you can copy into `/create`."
        )
        return

    poll = target.poll
    lines = [poll.question.strip(), "", "Options"]
    for opt in poll.options:
        lines.append(opt.text.strip())

    if hasattr(poll, "correct_option_id") and poll.correct_option_id is not None:
        idx = poll.correct_option_id
        if 0 <= idx < len(poll.options):
            correct = poll.options[idx].text.strip()
            lines.append("")
            lines.append(f"Answer: {correct}")

    explanation = getattr(poll, "explanation", None)
    if explanation:
        lines.append(f"Ex: {explanation.strip()}")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n\n…(truncated)"

    await message.reply_text(f"```\n{text}\n```")


@app.on_message(filters.command("gcast") & filters.user(OWNER_ID))  # Restrict broadcast to bot owners
async def broadcast(client, message: Message):
    global broadcast_active
    if not message.reply_to_message:
        await message.reply("Please reply to the message you want to broadcast.")
        return

    if broadcast_active:
        await message.reply("⚠️ A broadcast is already in progress! Wait until it finishes or use /stopcast.")
        return

    broadcast_active = True  # Set flag to active
    broadcast_message = message.reply_to_message
    user_list = list(users_collection.find())

    total_users = len(user_list)
    sent_count = 0
    failed_count = 0

    progress_message = await message.reply(f"📤 Broadcast started: 0/{total_users} users sent")

    for index, user in enumerate(user_list):
        if not broadcast_active:
            await progress_message.edit_text(f"❌ Broadcast stopped at {sent_count}/{total_users} users.")
            return  # Stop the broadcast if canceled

        try:

            if broadcast_message.text:
                await client.send_message(
                    chat_id=user["chat_id"],
                    text=broadcast_message.text,
                    reply_markup=broadcast_message.reply_markup if broadcast_message.reply_markup else None
                )

            elif broadcast_message.photo:
                await client.send_photo(
                    chat_id=user["chat_id"],
                    photo=broadcast_message.photo.file_id,
                    caption=broadcast_message.caption if broadcast_message.caption else "",
                    reply_markup=broadcast_message.reply_markup if broadcast_message.reply_markup else None
                )

            elif broadcast_message.video:
                await client.send_video(
                    chat_id=user["chat_id"],
                    video=broadcast_message.video.file_id,
                    caption=broadcast_message.caption if broadcast_message.caption else "",
                    reply_markup=broadcast_message.reply_markup if broadcast_message.reply_markup else None
                )

            elif broadcast_message.document:
                await client.send_document(
                    chat_id=user["chat_id"],
                    document=broadcast_message.document.file_id,
                    caption=broadcast_message.caption if broadcast_message.caption else "",
                    reply_markup=broadcast_message.reply_markup if broadcast_message.reply_markup else None
                )

            elif broadcast_message.audio:
                await client.send_audio(
                    chat_id=user["chat_id"],
                    audio=broadcast_message.audio.file_id,
                    caption=broadcast_message.caption if broadcast_message.caption else "",
                    reply_markup=broadcast_message.reply_markup if broadcast_message.reply_markup else None
                )

            elif broadcast_message.voice:
                await client.send_voice(
                    chat_id=user["chat_id"],
                    voice=broadcast_message.voice.file_id,
                    caption=broadcast_message.caption if broadcast_message.caption else "",
                    reply_markup=broadcast_message.reply_markup if broadcast_message.reply_markup else None
                )

            else:
                await client.send_message(
                    chat_id=user["chat_id"],
                    text="📢 Broadcast Message (Unsupported format)",
                )

            sent_count += 1

        except Exception:
            failed_count += 1

        if (index + 1) % 100 == 0 or (index + 1) == total_users:
            await progress_message.edit_text(
                f"📤 Broadcast Progress: {sent_count}/{total_users} users sent"
            )
            await asyncio.sleep(10)  # Sleep for 10 seconds after 100 messages

    
    broadcast_active = False  # Reset flag after completion
    await progress_message.edit_text(
        f"✅ Broadcast completed: {sent_count}/{total_users} users successfully sent\n❌ Failed: {failed_count} users"
    )
@app.on_message(filters.command("stopcast") & filters.user(OWNER_ID))  # Restrict stop command to the owner
async def stop_broadcast(client, message: Message):
    global broadcast_active
    if not broadcast_active:
        await message.reply("⚠️ No active broadcast to stop.")
        return

    broadcast_active = False  # Set flag to stop the ongoing broadcast
    await message.reply("✅ Broadcast has been stopped.")
    

@app.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def stats_quiz(client, message):

    k = await message.reply("Fetching bot statistics...")
    total_users = users_collection.count_documents({})

    total_quizzes = questions_collection.count_documents({})

    quizzes = questions_collection.find()
    removed_count = 0
    paid_quizzes = 0
    free_quizzes = 0
    for quiz in quizzes:
        question_set_id = quiz["question_set_id"]
        total_questions = len(quiz.get("questions", []))
        
        if quiz.get("type") == "paid":
            paid_quizzes += 1
        elif quiz.get("type") == "free":
            free_quizzes += 1
            

        if total_questions < 10:

            questions_collection.delete_one({"question_set_id": question_set_id})
            removed_count += 1

    await k.edit(
        f"> 📊 **Bot Statistics:**\n\n"
        f"👥 **Total Registered Users:** `{total_users}`\n"
        f"📚 **Total Quizzes Created:** `{total_quizzes}`\n"
        f"💰 **Paid Quizzes:** `{paid_quizzes}`\n"
        f"🎉 **Free Quizzes:** `{free_quizzes}`\n\n"
        f"**__Powered by Alpha World__**"
    )
    

@app.on_message(filters.command("remove") & filters.private)
async def handle_remove_command(client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if len(message.command) < 2:
        await message.reply("❌ Please provide words or a sentence to add to the remove list.\n\nUsage: `/remove WORD or SENTENCE`")
        return

    text_to_remove = " ".join(message.command[1:]).strip().lower()  

    words_to_remove = text_to_remove.split()  # Splits sentence into individual words

    users_collection.update_one(
        {"chat_id": chat_id},
        {"$addToSet": {"remove_words": {"$each": words_to_remove}}},  # Add each word separately
        upsert=True
    )

    await message.reply(f"✅ Words `{', '.join(words_to_remove)}` have been added to your remove list.")
    

def filter_words(text, remove_words):
    if not text:
        return text

    text = re.sub(r'\[\s*\d+\s*/\s*\d+\s*\]', '', text).strip()

    if remove_words:
        for word in remove_words:
            pattern = r'\b' + re.escape(word) + r'\b'  # Match whole words
            text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()  # Case-insensitive replacement

    return re.sub(r'\s+', ' ', text).strip()  # Remove extra spaces
    

async def read_questions_from_file(file_path: str, user_id: str, remove_words: Optional[List[str]] = None, 
                                   app: Optional[Client] = None, log_group_id: Optional[str] = None,
                                   statement_based: bool = False) -> Tuple[Optional[int], Optional[str]]:
    lower = file_path.lower()
    if not (lower.endswith('.txt') or lower.endswith('.json') or lower.endswith('.pdf')):
        return None, "Invalid file format. Only .txt, .json and .pdf files are supported."

    try:
        if lower.endswith('.json'):
            return await _process_json_file(file_path, user_id, remove_words, app, log_group_id)
        elif lower.endswith('.pdf'):
            return await _process_pdf_file(file_path, user_id, remove_words, statement_based=statement_based)
        else:
            return await _process_txt_file(file_path, user_id, remove_words, statement_based=statement_based)
            
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        return None, f"Error processing file: {str(e)}"


async def _process_pdf_file(file_path: str, user_id: str, remove_words: Optional[List[str]] = None, statement_based: bool = False) -> Tuple[Optional[int], Optional[str]]:
    """Extract text from a PDF and feed it through the existing TXT parser.

    Expected PDF content layout (same as .txt format):

        Question text here?
        Option A
        Option B ✅
        Option C
        Option D
        Ex: Optional explanation

        Next question...

    Blank lines (or large gaps in the PDF) separate questions. We extract text
    page-by-page, normalise whitespace, and write a temporary .txt file that
    `_process_txt_file` already knows how to handle — that way TXT and PDF
    inputs share the exact same parsing/validation rules.
    """
    try:
        from pypdf import PdfReader
    except Exception as e:
        return None, f"PDF support requires pypdf — install it and retry. ({e})"

    try:
        reader = PdfReader(file_path)
        pages_text = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception as pe:
                print(f"Skipping a PDF page due to extract error: {pe}")
                txt = ""
            if txt.strip():
                pages_text.append(txt)

        if not pages_text:
            return None, "Couldn't read any text from this PDF — is it scanned/image-based? Try a text PDF or convert it to .txt first."

        raw = "\n".join(pages_text)

        # Normalise: strip per-line whitespace, collapse 3+ blank lines to a
        # single blank line so question blocks are reliably separated by "\n\n".
        lines = [ln.rstrip() for ln in raw.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

        # Hand off to the TXT pipeline by writing a sibling .txt file.
        txt_path = file_path + ".extracted.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

        try:
            return await _process_txt_file(txt_path, user_id, remove_words, statement_based=statement_based)
        finally:
            try:
                if os.path.exists(txt_path):
                    os.remove(txt_path)
            except Exception:
                pass

    except Exception as e:
        print(f"Error processing PDF file: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Error processing PDF file: {str(e)}"

async def _download_and_upload_telegram_file(app: Client, telegram_file_id: str, log_group_id: str) -> Optional[str]:
    """
    Download file from Telegram using file_id with Pyrogram, upload to log group, and return new file_id.
    """
    try:
        print(f"Downloading file with ID: {telegram_file_id[:50]}...")
        

        download_path = await app.download_media(
            telegram_file_id,
            file_name=f"temp_{telegram_file_id[:10]}.jpg"
        )
        
        if not download_path:
            print("Failed to download file")
            return None
        
        print(f"File downloaded to: {download_path}")
        

        try:
            message = await app.send_photo(
                chat_id=log_group_id,
                photo=download_path,
                caption=f"Uploaded from file_id: {telegram_file_id[:20]}..."
            )
            

            if message.photo:

                new_file_id = message.photo.file_id
                print(f"File uploaded successfully. New file_id: {new_file_id[:50]}...")
            else:
                print("No photo in uploaded message")
                new_file_id = None
            
        except Exception as upload_error:
            print(f"Error uploading to log group: {upload_error}")
            new_file_id = None
        

        try:
            os.remove(download_path)
            print("Temporary file cleaned up")
        except:
            pass
        
        return new_file_id
        
    except Exception as e:
        print(f"Error in _download_and_upload_telegram_file: {str(e)}")

        try:
            if 'download_path' in locals() and os.path.exists(download_path):
                os.remove(download_path)
        except:
            pass
        return None

async def _process_text_lengths(question_text: str, options: List[str], reply_text: str = None) -> Tuple[str, List[str], str]:
    """
    Process text lengths according to requirements:
    - If question > 200 chars: truncate question to 100 chars + "...", add full question to reply_text
    - If any option > 100 chars: truncate all options to 50 chars + "...", add full question and all options to reply_text
    """
    original_question = question_text
    original_options = options.copy()
    

    if reply_text is None:
        reply_text = ""
    elif reply_text.strip():
        reply_text = reply_text.strip()
    

    any_long_option = any(len(opt) > 100 for opt in options)
    

    needs_separator = bool(reply_text)
    

    if len(question_text) > 200:

        truncated_question = question_text[:100].rstrip() + "..."
        

        if needs_separator:
            reply_text += "\n\n"
        reply_text += f"Full Question:\n{question_text}"
        needs_separator = True
        
        question_text = truncated_question
    

    if any_long_option:

        truncated_options = []
        for opt in options:
            if len(opt) > 100:
                truncated_opt = opt[:50].rstrip() + "..."
            else:
                truncated_opt = opt[:50].rstrip() + "..." if len(opt) > 50 else opt
            truncated_options.append(truncated_opt)
        
        options = truncated_options
        

        if not reply_text or "Full Question:" not in reply_text:
            if needs_separator:
                reply_text += "\n\n"
            reply_text += f"Full Question:\n{original_question}"
            needs_separator = True
        
        reply_text += "\n\nFull Options:"
        for i, opt in enumerate(original_options):
            reply_text += f"\n{chr(97 + i)}) {opt}"
    
    return question_text, options, reply_text

def decrypt_quiz_file(file_path, auth_key="codedbytedance2"):
    """
    Decrypts an encrypted quiz file and saves it back to the same path
    
    Args:
        file_path: Path to the encrypted JSON file
        auth_key: Authorization key (default: codedbytedance2)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:

        with open(file_path, 'r', encoding='utf-8') as f:
            encrypted_b64 = f.read().strip()
        

        encrypted = base64.b64decode(encrypted_b64)
        key_bytes = auth_key.encode('utf-8')
        

        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        

        json_str = decrypted.decode('utf-8')
        

        quiz_data = json.loads(json_str)
        

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(quiz_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully decrypted: {file_path}")
        return True
        
    except Exception as e:
        print(f"❌ Decryption failed: {e}")
        return False

async def _process_json_file(file_path: str, user_id: str, remove_words: Optional[List[str]] = None,
                           app: Optional[Client] = None, log_group_id: Optional[str] = None) -> Tuple[Optional[int], Optional[str]]:
    """Process JSON file format with Pyrogram file handling."""

    try:
        
        try:
            decrypt_quiz_file(file_path)
        except Exception as e:
            print(e)
            pass

        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        

        if not isinstance(data, dict) or "questions" not in data:
            return None, "Invalid JSON format. Expected object with 'questions' array."
        
        questions = data["questions"]
        if not isinstance(questions, list):
            return None, "Invalid JSON format. 'questions' should be an array."
        

        if user_id not in user_quiz_data:
            user_quiz_data[user_id] = {"questions": []}
        elif "questions" not in user_quiz_data[user_id]:
            user_quiz_data[user_id]["questions"] = []
        
        processed_count = 0
        
        for q_idx, question_data in enumerate(questions):
            try:

                required_fields = ["question_text", "options", "correct_option_id"]
                for field in required_fields:
                    if field not in question_data:
                        print(f"Question {q_idx + 1} missing required field: {field}")
                        continue
                

                question_text = question_data["question_text"]
                if remove_words:
                    question_text = filter_words(question_text, remove_words)
                question_text = await remove_baby(question_text)
                

                options_data = question_data["options"]
                if not isinstance(options_data, list) or len(options_data) < 2:
                    print(f"Question {q_idx + 1} has invalid options")
                    continue
                
                options = []
                option_id_map = {}
                valid_option_ids = []
                
                for opt_idx, option in enumerate(options_data):
                    if not isinstance(option, dict) or "id" not in option or "text" not in option:
                        print(f"Question {q_idx + 1} option {opt_idx} is invalid")
                        continue
                    
                    option_id = option["id"]
                    option_text = option["text"]
                    
                    if remove_words:
                        option_text = filter_words(option_text, remove_words)
                    option_text = await remove_baby(option_text)
                    
                    if not option_text:
                        print(f"Question {q_idx + 1} option {option_id} has empty text")
                        continue
                    
                    options.append(option_text)
                    option_id_map[option_id] = opt_idx
                    valid_option_ids.append(option_id)
                
                if len(options) < 2:
                    print(f"Question {q_idx + 1} has insufficient valid options")
                    continue
                

                correct_option_id = question_data["correct_option_id"]
                if correct_option_id not in option_id_map:
                    print(f"Question {q_idx + 1} has invalid correct_option_id: {correct_option_id}")
                    continue
                

                correct_option_index = option_id_map[correct_option_id]
                

                explanation = None
                if "explanation" in question_data and question_data["explanation"]:
                    explanation = question_data["explanation"]
                    if remove_words:
                        explanation = filter_words(explanation, remove_words)
                    explanation = await remove_baby(explanation, keep_links=True)
                

                reply_text = None
                if "reference_text" in question_data and question_data["reference_text"]:
                    reply_text = question_data["reference_text"]
                    if remove_words:
                        reply_text = filter_words(reply_text, remove_words)
                    reply_text = await remove_baby(reply_text, keep_links=True)
                

                telegram_file_id = None
                new_file_id = None
                
                if "image_url" in question_data and question_data["image_url"]:

                    telegram_file_id = question_data["image_url"]
                    

                    if app and log_group_id:
                        new_file_id = await _download_and_upload_telegram_file(app, telegram_file_id, log_group_id)
                        if not new_file_id:
                            print(f"Warning: Failed to upload image for question {q_idx + 1}")
                

                processed_question, processed_options, processed_reply_text = await _process_text_lengths(
                    question_text, options, reply_text
                )
                

                user_quiz_data[user_id]["questions"].append({
                    "question": processed_question,
                    "options": processed_options,
                    "correct_option_id": correct_option_index,  # Convert to 0-based index
                    "explanation": explanation,
                    "reply_text": processed_reply_text,
                    "file_id": new_file_id,  # Use the new file_id from log group
                })
                
                processed_count += 1
                print(f"Added question {processed_count}: {question_data.get('id', 'No ID')}")
                print(f"  Question: {processed_question[:50]}...")
                print(f"  Options: {[opt[:30] + '...' if len(opt) > 30 else opt for opt in processed_options]}")
                if new_file_id:
                    print(f"  File uploaded, new file_id: {new_file_id[:20]}...")
                
            except Exception as e:
                print(f"Error processing question {q_idx + 1}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"Successfully processed {processed_count} questions from JSON")
        os.remove(file_path)
        return processed_count, None
        
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON format: {str(e)}"
    except Exception as e:
        print(f"Error processing JSON file: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Error processing JSON file: {str(e)}"

async def _process_txt_file(file_path: str, user_id: str, remove_words: Optional[List[str]] = None, statement_based: bool = False) -> Tuple[Optional[int], Optional[str]]:
    """Process TXT file format - KEEPING ORIGINAL LOGIC INTACT."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()

        ggn_tag_pattern = r'<ggn>(.*?)</ggn>'
        ggn_blocks = []
        
        def replace_ggn(match):
            ggn_content = match.group(1)
            placeholder = f"GGN_PLACEHOLDER_{len(ggn_blocks)}"
            ggn_blocks.append(ggn_content)
            return f"RT: <ggn>{placeholder}</ggn>"
        

        protected_content = re.sub(ggn_tag_pattern, replace_ggn, file_content, flags=re.DOTALL)
        

        if user_id not in user_quiz_data:
            user_quiz_data[user_id] = {"questions": []}
        elif "questions" not in user_quiz_data[user_id]:
            user_quiz_data[user_id]["questions"] = []

        questions_blocks = protected_content.strip().split("\n\n")
        processed_count = 0
        

        print(f"Found {len(questions_blocks)} question blocks in file")

        _ROMAN_LINE_RE = re.compile(r'^(I{1,3}V?|V?I{1,3}|IX|XI{0,3})\.\s', re.IGNORECASE)
        _OPT_LETTER_RE = re.compile(r'^[A-Ea-e][)\.]\s*')

        for block_idx, block in enumerate(questions_blocks):
            try:
                print(f"Processing block {block_idx+1}/{len(questions_blocks)}")
                
                lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
                if not lines:
                    print(f"Block {block_idx+1} is empty, skipping")
                    continue
                lines = _sanitize_input_lines(lines)

                question = lines[0].strip()
                options = []
                correct_option_id = None
                explanation = None
                reply_text = None
                file_id = None  # This is already the Telegram file ID in TXT format

                # ── 👇-separator format ──────────────────────────────────────
                # Detect the "Telegram screenshot" style where the 👇 emoji
                # marks the boundary between the (multi-line) question block
                # and the options.  Everything before the 👇 line is joined as
                # the question; everything after is parsed as options / Ex:.
                #
                # Example:
                #   Question line 1
                #   I. Statement one.
                #   II. Statement two.
                #   Final sub-question?
                #   👇 ────────────────────
                #   A) Option A
                #   B) Option B
                #   C) Option C ✅
                #   D) Option D
                #   Ex: Explanation text
                # ─────────────────────────────────────────────────────────────
                emoji_sep_idx = next(
                    (idx for idx, ln in enumerate(lines) if '👇' in ln),
                    None
                )

                if emoji_sep_idx is not None:
                    # Everything before the 👇 line = question (multi-line)
                    question_parts_raw = [l.strip() for l in lines[:emoji_sep_idx] if l.strip()]
                    question = "\n".join(question_parts_raw)
                    if remove_words:
                        question = filter_words(question, remove_words)
                    question = await remove_baby(question)
                    print(f"Question (👇-format): {question[:60]}")

                    for opt_line in lines[emoji_sep_idx + 1:]:
                        opt_line = opt_line.strip()
                        if not opt_line:
                            continue
                        if opt_line.startswith("Ex:"):
                            explanation = opt_line[3:].strip()
                            if remove_words:
                                explanation = filter_words(explanation, remove_words)
                            explanation = await remove_baby(explanation, keep_links=True)
                            continue
                        if opt_line.startswith("RT:"):
                            rt_content = opt_line[3:].strip()
                            ggn_m = re.search(r'<ggn>GGN_PLACEHOLDER_(\d+)</ggn>', rt_content)
                            if ggn_m:
                                pidx = int(ggn_m.group(1))
                                if pidx < len(ggn_blocks):
                                    reply_text = ggn_blocks[pidx]
                            else:
                                reply_text = rt_content
                            if remove_words:
                                reply_text = filter_words(reply_text, remove_words)
                            reply_text = await remove_baby(reply_text, keep_links=True)
                            continue
                        if opt_line.startswith("ID:"):
                            file_id = opt_line[3:].strip()
                            file_id = await remove_baby(file_id)
                            continue
                        # Strip leading A) / B) / a. / b. etc.
                        clean_option = _OPT_LETTER_RE.sub('', opt_line).strip()
                        if "✅" in clean_option:
                            correct_option_id = len(options)
                            clean_option = clean_option.replace("✅", "").strip()
                        if remove_words:
                            clean_option = filter_words(clean_option, remove_words)
                        clean_option = await remove_baby(clean_option)
                        if clean_option:
                            options.append(clean_option)

                    processed_question, processed_options, processed_reply_text = await _process_text_lengths(
                        question, options, reply_text
                    )
                    if not processed_question or len(processed_options) < 2 or correct_option_id is None:
                        print(f"Skipping invalid 👇-format question: {processed_question}")
                        continue
                    user_quiz_data[user_id]["questions"].append({
                        "question": processed_question,
                        "options": processed_options,
                        "correct_option_id": correct_option_id,
                        "explanation": explanation,
                        "reply_text": processed_reply_text,
                        "file_id": file_id,
                    })
                    processed_count += 1
                    print(f"Added question {processed_count} (👇-format)")
                    continue
                # ─────────────────────────────────────────────────────────────

                if remove_words:
                    question = filter_words(question, remove_words)
                question = await remove_baby(question)
                
                print(f"Question: {question}")

                if statement_based:
                    question_parts = [question]
                    in_question_mode = True
                    i = 1
                    while i < len(lines):
                        line = lines[i].strip()
                        i += 1
                        if not line:
                            continue
                        print(f"Processing line (stmt): {line}")
                        if line.startswith("Ex:"):
                            explanation = line[3:].strip()
                            if remove_words:
                                explanation = filter_words(explanation, remove_words)
                            explanation = await remove_baby(explanation, keep_links=True)
                            continue
                        if line.startswith("RT:"):
                            rt_content = line[3:].strip()
                            ggn_m = re.search(r'<ggn>GGN_PLACEHOLDER_(\d+)</ggn>', rt_content)
                            if ggn_m:
                                pidx = int(ggn_m.group(1))
                                if pidx < len(ggn_blocks):
                                    reply_text = ggn_blocks[pidx]
                            else:
                                reply_text = rt_content
                            if remove_words:
                                reply_text = filter_words(reply_text, remove_words)
                            reply_text = await remove_baby(reply_text, keep_links=True)
                            continue
                        if line.startswith("ID:"):
                            file_id = line[3:].strip()
                            file_id = await remove_baby(file_id)
                            continue
                        if in_question_mode:
                            if _ROMAN_LINE_RE.match(line) or line.endswith("?") or line.endswith("?"):
                                part = line
                                if remove_words:
                                    part = filter_words(part, remove_words)
                                part = await remove_baby(part)
                                question_parts.append(part)
                                continue
                            else:
                                in_question_mode = False
                        clean_option = _OPT_LETTER_RE.sub('', line).strip()
                        if "✅" in clean_option:
                            correct_option_id = len(options)
                            clean_option = clean_option.replace("✅", "").strip()
                        if remove_words:
                            clean_option = filter_words(clean_option, remove_words)
                        clean_option = await remove_baby(clean_option)
                        if clean_option:
                            options.append(clean_option)
                    question = "\n".join(question_parts)
                else:
                    # Find the index of the first explicit A)/B)/C)/D) option line.
                    # Everything before it is part of the question body; only the
                    # lettered lines become poll options.
                    _ABCD_LINE_RE = re.compile(r'^[A-Da-d][)\.]\s*')
                    option_start_idx = None
                    for scan_i in range(1, len(lines)):
                        sl = lines[scan_i].strip()
                        if sl.startswith("Ex:") or sl.startswith("RT:") or sl.startswith("ID:"):
                            continue
                        if _ABCD_LINE_RE.match(sl):
                            option_start_idx = scan_i
                            break

                    if option_start_idx is not None:
                        # Collect body lines between the question heading and first A) as
                        # additional question text (matching pairs, instructions, etc.)
                        for qln in lines[1:option_start_idx]:
                            qln = qln.strip()
                            if not qln:
                                continue
                            if qln.startswith("Ex:"):
                                explanation = qln[3:].strip()
                                if remove_words:
                                    explanation = filter_words(explanation, remove_words)
                                explanation = await remove_baby(explanation, keep_links=True)
                                continue
                            if qln.startswith("RT:"):
                                rt_content = qln[3:].strip()
                                ggn_m = re.search(r'<ggn>GGN_PLACEHOLDER_(\d+)</ggn>', rt_content)
                                if ggn_m:
                                    pidx = int(ggn_m.group(1))
                                    if pidx < len(ggn_blocks):
                                        reply_text = ggn_blocks[pidx]
                                else:
                                    reply_text = rt_content
                                if remove_words:
                                    reply_text = filter_words(reply_text, remove_words)
                                reply_text = await remove_baby(reply_text, keep_links=True)
                                continue
                            if qln.startswith("ID:"):
                                file_id = qln[3:].strip()
                                file_id = await remove_baby(file_id)
                                continue
                            if remove_words:
                                qln = filter_words(qln, remove_words)
                            qln = await remove_baby(qln)
                            if qln:
                                question = question + "\n" + qln

                        # Only A)/B)/C)/D) lines become poll options
                        for opt_ln in lines[option_start_idx:]:
                            opt_ln = opt_ln.strip()
                            if not opt_ln:
                                continue
                            if opt_ln.startswith("Ex:"):
                                explanation = opt_ln[3:].strip()
                                if remove_words:
                                    explanation = filter_words(explanation, remove_words)
                                explanation = await remove_baby(explanation, keep_links=True)
                                continue
                            if opt_ln.startswith("RT:"):
                                rt_content = opt_ln[3:].strip()
                                ggn_m = re.search(r'<ggn>GGN_PLACEHOLDER_(\d+)</ggn>', rt_content)
                                if ggn_m:
                                    pidx = int(ggn_m.group(1))
                                    if pidx < len(ggn_blocks):
                                        reply_text = ggn_blocks[pidx]
                                else:
                                    reply_text = rt_content
                                if remove_words:
                                    reply_text = filter_words(reply_text, remove_words)
                                reply_text = await remove_baby(reply_text, keep_links=True)
                                continue
                            if opt_ln.startswith("ID:"):
                                file_id = opt_ln[3:].strip()
                                file_id = await remove_baby(file_id)
                                continue
                            if not _ABCD_LINE_RE.match(opt_ln):
                                continue
                            clean_option = _ABCD_LINE_RE.sub('', opt_ln).strip()
                            if "✅" in clean_option:
                                correct_option_id = len(options)
                                clean_option = clean_option.replace("✅", "").strip()
                            if remove_words:
                                clean_option = filter_words(clean_option, remove_words)
                            clean_option = await remove_baby(clean_option)
                            if clean_option:
                                options.append(clean_option)
                    elif any(re.search(
                            r'(Reason\s*\(R\)|कारण\s*\(R\)|Assertion\s*\(A\)|कथन\s*\(A\))',
                            ln, re.IGNORECASE) for ln in lines):
                        # ── Assertion-Reason format ──────────────────────────────
                        # Options use "(A) और (R)..." / "(A) सही..." style — NOT A)/B).
                        # Split at the instruction line (नीचे दिए / कूट / Choose the correct).
                        # Everything up to and including the instruction line → question.
                        # Everything after → options (strip leading "- " or number prefix).
                        _AR_INSTR_RE = re.compile(
                            r'(कूट|नीचे\s+दिए|Choose\s+the\s+correct|correct\s+answer\s+using)',
                            re.IGNORECASE)
                        _DASH_PREFIX_RE = re.compile(r'^[-•]\s*')
                        _NUM_PREFIX_RE = re.compile(r'^[\(\[]?[1-4][\)\]\.]\s*')

                        instr_idx = None
                        for scan_i in range(1, len(lines)):
                            if _AR_INSTR_RE.search(lines[scan_i]):
                                instr_idx = scan_i
                                break

                        if instr_idx is not None:
                            q_body_end = instr_idx + 1
                            opts_start = instr_idx + 1
                        else:
                            # No explicit instruction line — treat last 4 non-special lines as options
                            non_sp = [j for j in range(1, len(lines))
                                      if lines[j].strip()
                                      and not lines[j].strip().startswith(("Ex:", "RT:", "ID:"))]
                            if len(non_sp) >= 4:
                                q_body_end = non_sp[-4]
                                opts_start = non_sp[-4]
                            else:
                                q_body_end = len(lines)
                                opts_start = len(lines)

                        for qln in lines[1:q_body_end]:
                            qln = _DASH_PREFIX_RE.sub('', qln.strip()).strip()
                            if not qln:
                                continue
                            if qln.startswith("Ex:"):
                                explanation = qln[3:].strip()
                                continue
                            if qln.startswith("RT:"):
                                rt_content = qln[3:].strip()
                                ggn_m = re.search(r'<ggn>GGN_PLACEHOLDER_(\d+)</ggn>', rt_content)
                                if ggn_m:
                                    pidx = int(ggn_m.group(1))
                                    if pidx < len(ggn_blocks):
                                        reply_text = ggn_blocks[pidx]
                                else:
                                    reply_text = rt_content
                                if remove_words:
                                    reply_text = filter_words(reply_text, remove_words)
                                reply_text = await remove_baby(reply_text, keep_links=True)
                                continue
                            if qln.startswith("ID:"):
                                file_id = qln[3:].strip()
                                file_id = await remove_baby(file_id)
                                continue
                            if remove_words:
                                qln = filter_words(qln, remove_words)
                            qln = await remove_baby(qln)
                            if qln:
                                question = question + "\n" + qln

                        for opt_ln in lines[opts_start:]:
                            opt_ln = _DASH_PREFIX_RE.sub('', opt_ln.strip()).strip()
                            if not opt_ln:
                                continue
                            if opt_ln.startswith("Ex:"):
                                explanation = opt_ln[3:].strip()
                                if remove_words:
                                    explanation = filter_words(explanation, remove_words)
                                explanation = await remove_baby(explanation, keep_links=True)
                                continue
                            if opt_ln.startswith("RT:") or opt_ln.startswith("ID:"):
                                continue
                            # Strip numeric prefix 1) 2) (1) etc. if present
                            opt_ln = _NUM_PREFIX_RE.sub('', opt_ln).strip()
                            if not opt_ln:
                                continue
                            clean_option = opt_ln
                            if "✅" in clean_option:
                                correct_option_id = len(options)
                                clean_option = clean_option.replace("✅", "").strip()
                            if remove_words:
                                clean_option = filter_words(clean_option, remove_words)
                            clean_option = await remove_baby(clean_option)
                            if clean_option:
                                options.append(clean_option)
                    else:
                        # Legacy fallback: no explicit A)/B)/C)/D) labels found —
                        # treat every non-special line after the first as an option.
                        i = 1
                        while i < len(lines):
                            line = lines[i].strip()
                            print(f"Processing line: {line}")

                            if line.startswith("Ex:"):
                                explanation = line[3:].strip()
                                if remove_words:
                                    explanation = filter_words(explanation, remove_words)
                                explanation = await remove_baby(explanation, keep_links=True)
                                i += 1
                                continue

                            if line.startswith("RT:"):
                                rt_content = line[3:].strip()
                                ggn_placeholder_match = re.search(r'<ggn>GGN_PLACEHOLDER_(\d+)</ggn>', rt_content)
                                if ggn_placeholder_match:
                                    placeholder_index = int(ggn_placeholder_match.group(1))
                                    if placeholder_index < len(ggn_blocks):
                                        reply_text = ggn_blocks[placeholder_index]
                                else:
                                    reply_text = rt_content
                                if remove_words:
                                    reply_text = filter_words(reply_text, remove_words)
                                reply_text = await remove_baby(reply_text, keep_links=True)
                                i += 1
                                continue

                            if line.startswith("ID:"):
                                file_id = line[3:].strip()
                                file_id = await remove_baby(file_id)
                                i += 1
                                continue

                            if i < len(lines):
                                clean_option = line.strip()
                                if "✅" in clean_option:
                                    correct_option_id = len(options)
                                    clean_option = clean_option.replace("✅", "").strip()
                                if remove_words:
                                    clean_option = filter_words(clean_option, remove_words)
                                clean_option = await remove_baby(clean_option)
                                if clean_option:
                                    options.append(clean_option)

                            i += 1

                processed_question, processed_options, processed_reply_text = await _process_text_lengths(
                    question, options, reply_text
                )

                if not processed_question or len(processed_options) < 2 or correct_option_id is None:
                    print(f"Skipping invalid question: {processed_question}")
                    print(f"Options: {processed_options}, Correct ID: {correct_option_id}")
                    continue

                user_quiz_data[user_id]["questions"].append({
                    "question": processed_question,
                    "options": processed_options,
                    "correct_option_id": correct_option_id,
                    "explanation": explanation,
                    "reply_text": processed_reply_text,
                    "file_id": file_id,  # Original Telegram file ID from TXT
                })
                processed_count += 1
                print(f"Added question {processed_count}")
                print(f"  Processed question: {processed_question[:50]}...")
                print(f"  Options: {[opt[:30] + '...' if len(opt) > 30 else opt for opt in processed_options]}")
                if file_id:
                    print(f"  File ID: {file_id[:20]}...")
                
            except Exception as e:
                print(f"Error processing block {block_idx+1}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue

        print(f"Successfully processed {processed_count} questions")
        os.remove(file_path)
        return processed_count, None

    except Exception as e:
        print(f"Error processing TXT file: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, f"Error processing TXT file: {str(e)}"

@app.on_message(filters.command("clearlist") & filters.private)
async def handle_clearlist_command(client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    users_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"remove_words": []}}  # Set the remove_words list to an empty array
    )

    await message.reply("✅ Your remove list has been cleared.")
    
    
@app.on_message(filters.document & filters.private)
async def handle_document_messages(client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:

        if user_id not in user_quiz_data:

            return

        if user_quiz_data[user_id].get("awaiting_name"):
            await message.reply("✏️ Please send the quiz **name** first (as text).")
            return

        if user_quiz_data[user_id].get("awaiting_statement_based"):
            await message.reply("📋 Please answer the statement-based question first: reply `yes` or `no`.")
            return

        allowed_types = ["text/plain", "application/json", "application/pdf"]
        image_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
        file_name = (message.document.file_name or "").lower()
        mime = (message.document.mime_type or "")
        is_image_doc = mime.startswith("image/") or file_name.endswith(image_exts)
        ai_mode_on = bool(user_quiz_data.get(user_id, {}).get("ai_mode"))

        if is_image_doc and not ai_mode_on:
            await message.reply(
                "📷 Image uploads are only supported in AI mode. "
                "Start with /aicreate first."
            )
            return

        if (
            mime not in allowed_types
            and not file_name.endswith((".txt", ".json", ".pdf"))
            and not (is_image_doc and ai_mode_on)
        ):
            await message.reply(
                "Only `.txt`, `.json`, `.pdf` files are supported "
                "(plus image files in AI mode via /aicreate)."
            )
            return
        

        status_msg = await message.reply("Downloading and processing file...")
        

        print(f"Downloading file: {message.document.file_name}")
        file_path = await message.download()
        print(f"File downloaded to: {file_path}")
        

        user_data = users_collection.find_one({"chat_id": chat_id})
        remove_words = user_data.get("remove_words", []) if user_data else []

        # ── AI mode: let an LLM turn the raw PDF/TXT/Image into MCQs first ──
        if user_quiz_data.get(user_id, {}).get("ai_mode"):
            n_q = user_quiz_data[user_id].get("ai_num_questions", 25)
            ai_lang = user_quiz_data[user_id].get("ai_language", "English")
            ai_bilingual = user_quiz_data[user_id].get("ai_bilingual", False)
            ai_qtype = user_quiz_data[user_id].get("ai_question_type", "mixed")
            ai_page_range = user_quiz_data[user_id].get("ai_page_range", None)
            ai_difficulty = user_quiz_data[user_id].get("ai_difficulty", "medium")
            user_key = (user_data or {}).get("gemini_api_key") or None
            kind = "image" if is_image_doc else "file"
            qtype_label = ai_qtype.capitalize()
            lang_label = f"{ai_lang}/English (bilingual)" if ai_bilingual else ai_lang
            await status_msg.edit_text(
                f"🤖 Reading the {kind} and generating **{n_q} questions** with AI…\n"
                f"Type: {qtype_label} | Language: {lang_label} | Difficulty: {ai_difficulty}\n"
                f"Provider: {'your Gemini key' if user_key else 'free AI (Pollinations / Sandeep)'}\n"
                f"This usually takes 15–60 seconds."
            )
            try:
                ai_txt, ai_count, provider = await generate_questions_txt_from_file(
                    file_path,
                    num_questions=n_q,
                    difficulty=ai_difficulty,
                    user_gemini_api_key=user_key,
                    language=ai_lang,
                    bilingual=ai_bilingual,
                    question_type=ai_qtype,
                    page_range=ai_page_range,
                )
            except Exception as e:
                print(f"AI generation failed: {e}")
                import traceback
                traceback.print_exc()
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
                err_short = str(e)[:200]
                hint = (
                    "Tip: save your own Gemini key with `/gemini <key>` for "
                    "higher reliability."
                    if not user_key else
                    "Both your Gemini key and the free fallback are temporarily "
                    "overloaded. Please try again in a minute."
                )
                await status_msg.edit_text(
                    f"❌ AI couldn't generate questions right now.\n"
                    f"Reason: `{err_short}`\n\n{hint}"
                )
                return

            # Replace the user's upload with the AI-generated TXT and feed it
            # through the standard parser so all downstream behaviour matches.
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            file_path = file_path + ".ai.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(ai_txt)
            await status_msg.edit_text(
                f"✅ AI generated **{ai_count} questions** via {provider} — "
                f"adding to the quiz…"
            )

        print("Starting file processing...")
        _stmt = user_quiz_data.get(user_id, {}).get("statement_based", False)
        processed_count, error = await read_questions_from_file(file_path, user_id, remove_words, statement_based=_stmt)
        print("File processing complete.")
        

        import os
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted temporary file: {file_path}")
        

        if error:
            await status_msg.edit_text(f"❌ Error: {error}")
        else:
            total = len(user_quiz_data[user_id]["questions"])
            await status_msg.edit_text(
                f"✅ {processed_count} questions processed from file! Total questions: {total}\n\n"
                f"Send the next question set or poll or type /done when finished or /cancel to cancel."
            )
    
    except Exception as e:
        print(f"Exception in document handler: {str(e)}")
        await message.reply(f"❌ An error occurred while processing the file: {str(e)}")


@app.on_message(filters.photo & filters.private)
async def handle_photo_for_ai(client, message: Message):
    """In AI quiz mode, accept regular Telegram photos (not just images sent
    as documents) and turn them into MCQs via the same AI pipeline."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in user_quiz_data:
        return
    if not user_quiz_data.get(user_id, {}).get("ai_mode"):
        return
    if user_quiz_data[user_id].get("awaiting_name"):
        await message.reply("✏️ Please send the quiz **name** first (as text).")
        return

    if user_quiz_data[user_id].get("awaiting_statement_based"):
        await message.reply("📋 Please answer the statement-based question first: reply `yes` or `no`.")
        return

    status_msg = await message.reply("📷 Downloading image and running AI…")
    file_path = None
    try:
        file_path = await message.download()
        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Couldn't download the image. Try again.")
            return

        # Telegram photo downloads don't always carry an extension.
        if not any(file_path.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")):
            new_path = file_path + ".jpg"
            try:
                os.rename(file_path, new_path)
                file_path = new_path
            except Exception:
                pass

        n_q = user_quiz_data[user_id].get("ai_num_questions", 25)
        ai_lang = user_quiz_data[user_id].get("ai_language", "English")
        ai_bilingual = user_quiz_data[user_id].get("ai_bilingual", False)
        ai_qtype = user_quiz_data[user_id].get("ai_question_type", "mixed")
        ai_page_range = user_quiz_data[user_id].get("ai_page_range", None)
        ai_difficulty = user_quiz_data[user_id].get("ai_difficulty", "medium")
        user_doc = users_collection.find_one({"chat_id": chat_id}) or {}
        user_key = user_doc.get("gemini_api_key") or None
        lang_label = f"{ai_lang}/English (bilingual)" if ai_bilingual else ai_lang

        await status_msg.edit_text(
            f"🤖 Reading the image and generating **{n_q} questions** with AI…\n"
            f"Type: {ai_qtype.capitalize()} | Language: {lang_label} | Difficulty: {ai_difficulty}\n"
            f"Provider: {'your Gemini key' if user_key else 'free AI (Pollinations / Sandeep)'}\n"
            f"This usually takes 15–60 seconds."
        )

        try:
            ai_txt, ai_count, provider = await generate_questions_txt_from_file(
                file_path,
                num_questions=n_q,
                difficulty=ai_difficulty,
                user_gemini_api_key=user_key,
                language=ai_lang,
                bilingual=ai_bilingual,
                question_type=ai_qtype,
                page_range=ai_page_range,
            )
        except Exception as e:
            print(f"AI image generation failed: {e}")
            import traceback
            traceback.print_exc()
            err_short = str(e)[:200]
            hint = (
                "Tip: save your own Gemini key with `/gemini <key>` for "
                "higher reliability — it has the strongest vision model."
                if not user_key else
                "Both your Gemini key and the free vision fallback are "
                "temporarily unavailable. Please try again in a minute."
            )
            await status_msg.edit_text(
                f"❌ AI couldn't generate questions from this image.\n"
                f"Reason: `{err_short}`\n\n{hint}"
            )
            return
        finally:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

        # Write to a fresh .txt and reuse the standard parser pipeline.
        txt_path = f"./ai_image_{user_id}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(ai_txt)

        await status_msg.edit_text(
            f"✅ AI generated **{ai_count} questions** via {provider} — "
            f"adding to the quiz…"
        )

        user_data = users_collection.find_one({"chat_id": chat_id}) or {}
        remove_words = user_data.get("remove_words", [])
        _stmt = user_quiz_data.get(user_id, {}).get("statement_based", False)
        processed_count, error = await read_questions_from_file(
            txt_path, user_id, remove_words, statement_based=_stmt
        )
        try:
            if os.path.exists(txt_path):
                os.remove(txt_path)
        except Exception:
            pass

        if error:
            await status_msg.edit_text(f"❌ Error: {error}")
            return

        total = len(user_quiz_data[user_id]["questions"])
        await status_msg.edit_text(
            f"✅ {processed_count} questions added from image! "
            f"Total questions: {total}\n\n"
            f"Send another image / file or type /done when finished, "
            f"or /cancel to cancel."
        )
    except Exception as e:
        print(f"Exception in photo handler: {e}")
        import traceback
        traceback.print_exc()
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        await message.reply(f"❌ An error occurred while processing the image: {e}")


@app.on_message(filters.command("ban") & filters.private & filters.user(OWNER_ID))
async def ban_quiz(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Please provide a valid **Quiz ID**.\nExample: `/ban 12345`")
        return

    quiz_id = args[1]
    quiz = questions_collection.find_one({"question_set_id": quiz_id})

    if not quiz:
        await message.reply("❌ No quiz found with this ID.")
        return

    creator_id = quiz.get("creator_id")

    if not creator_id or not CHANNEL_ID:
        await message.reply("❌ Could not find the creator or channel info for this quiz.")
        return

    try:
        await client.ban_chat_member(CHANNEL_ID, creator_id)
        await message.reply(f"✅ Banned user `{creator_id}` from bot.")
    except Exception as e:
        await message.reply(f"❌ Failed to remove user from the channel: {e}")

    deleted_quizzes = questions_collection.delete_many({"creator_id": creator_id})
    
    await message.reply(f"🗑️ Deleted `{deleted_quizzes.deleted_count}` quizzes created by `{creator_id}`.")

@app.on_message(filters.command("features"))
async def features_command(client, message):
    await message.reply_text(FEATURES_TEXT, disable_web_page_preview=True)

@app.on_message(filters.command("listquiz") & filters.chat("advance_quiz_group"))  # Restrict to owner
async def list_quizzes(client, message):
    quizzes = list(questions_collection.find())

    if not quizzes:
        await message.reply("❌ No quizzes found.")
        return

    for index, quiz in enumerate(quizzes):
        quiz_name = quiz.get("quiz_name", "Unnamed Quiz")
        question_set_id = quiz.get("question_set_id")
        num_questions = len(quiz.get("questions", []))
        timer = quiz.get("timer", "Not specified")
        quiz_type = quiz.get("type", "Unknown")
        negative_marking = quiz.get("negative_marking", 0)
        creator_id = quiz.get("creator_id", "Unknown")
        quiz_name = re.sub(r"(https?://\S+|@\S+|/[\w\d_-]+)", "", quiz_name)

        start_deep_link = f"https://t.me/{client.me.username}?start={question_set_id}"
        group_start_deep_link = f"https://t.me/{client.me.username}?startgroup={question_set_id}"

        quiz_text = (
            f"📌 **Quiz {index + 1}\n\n"
            f"**💳 Name:** `{quiz_name}`\n"
            f"**#️⃣ Questions:** `{num_questions}`\n"
            f"**⏰ Timer:** `{timer} seconds`\n"
            f"**🆔 Quiz ID:** `{question_set_id}`\n"
            f"**💰 Type:** `{quiz_type}`\n"
            f"**🏴‍☠️ -ve Marking:** `{negative_marking:.2f}`\n"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Start Now", url=start_deep_link)],
            [InlineKeyboardButton("🚀 Start in Group", url=group_start_deep_link)]
        ])

        await message.reply(quiz_text, reply_markup=keyboard)
        await asyncio.sleep(3)

        
@app.on_message(filters.command("info") & filters.private)
async def info_quiz(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Please provide a valid **Quiz ID**.\nExample: `/info 12345`")
        return

    quiz_id = args[1]
    quiz = questions_collection.find_one({"question_set_id": quiz_id})

    if not quiz:
        await message.reply("❌ No quiz found with this ID.")
        return

    creator_id = quiz["creator_id"]
    creator = await client.get_users(creator_id)
    creator_name = creator.first_name

    await message.reply(f"👨‍🏫 **Creator Name:** {creator_name} his id `{creator_id}`")

@app.on_message(filters.command("assignment") & filters.private)
async def create_assignment(client, message):
    creator_id = message.from_user.id
    creator_name = message.from_user.first_name  # Get creator's name
    

    if message.reply_to_message and message.reply_to_message.document:
        doc_message = message.reply_to_message
    elif message.document:
        doc_message = message
    else:
        await message.reply_text("Please reply to a document or send a document with the /assignment command.")
        return
    

    if BOT_GROUP:
        forwarded = await doc_message.forward(BOT_GROUP)
        file_id = forwarded.document.file_id
    else:
        file_id = doc_message.document.file_id

    assignment_id = generate_random_id()

    created_date = datetime.now().strftime("%d %B %Y")  # Example: 18 February 2025

    assignment_data = {
        "assignment_id": assignment_id,
        "creator_id": creator_id,
        "file_id": file_id,
        "text": message.caption or "",
        "created_date": created_date,
        "creator_name": creator_name
    }
    assignments_collection.insert_one(assignment_data)

    assignment_text = f"""
> 📚 **New Assignment Posted** 📚

🆔 **Assignment ID:** `{assignment_id}`
👨‍🏫 **Creator:** {creator_name}
📅 **Date Created:** {created_date}
"""

    await message.reply_text(
        f"Assignment Created Successfully! Assignment ID: `{assignment_id}`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📁 Share Assignment", switch_inline_query=f"ass_{assignment_id}")]
        ])
    )

def generate_random_id(length=7):

    characters = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    

    random_id = ''.join(random.choices(characters, k=length))
    
    return random_id

# Callback handler for "DO Assignment" button
@app.on_callback_query(filters.regex(r"do_([\w]+)"))
async def do_assignment(client, callback_query):
    assignment_id = callback_query.data.split("_")[1]
    assignment = assignments_collection.find_one({"assignment_id": assignment_id})

    if assignment:

        student_id = callback_query.from_user.id  # Get student ID
        await client.send_document(
            chat_id=student_id,  # Send the assignment directly to the student
            document=assignment["file_id"],
            caption=f"Assignment ID: `{assignment_id}`\n\n{assignment['text']}",
        )

        await callback_query.answer("Assignment sent to you!", show_alert=True)
    else:
        await callback_query.answer("Assignment not found.", show_alert=True)

@app.on_message(filters.command("submit") & filters.private)
async def submit_assignment(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: Reply to a document with `/submit ASSIGNMENT_ID`")
        return

    assignment_id = message.command[1]
    assignment = assignments_collection.find_one({"assignment_id": assignment_id})

    if not assignment:
        await message.reply_text("Invalid Assignment ID.")
        return

    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("Please reply to a document with `/submit ASSIGNMENT_ID`.")
        return

    document = message.reply_to_message.document
    student_id = message.from_user.id  # Get student ID
    student_name = message.from_user.first_name  # Get student's first name
    creator_id = assignment["creator_id"]  # Get creator's ID

    existing_submission = submissions_collection.find_one({
        "assignment_id": assignment_id,
        "submitted_by": student_id
    })

    if existing_submission:
        await message.reply_text("You have already submitted this assignment.")
        return

    await client.send_document(
        chat_id=creator_id,
        document=document.file_id,
        caption=f"🔖 **Assignment ID:** {assignment_id}\n🆔 Student ID: {student_id}\n👨‍🎓 Student Name: {student_name}"
    )

    submission_data = {
        "assignment_id": assignment_id,
        "submitted_by": student_id,
        "file_id": document.file_id,
    }
    submissions_collection.insert_one(submission_data)

    await message.reply_text("Assignment submitted successfully!")

# 🛑 /stopedit Command - Cancel Editing Session
@app.on_message(filters.command("stopedit") & filters.private)
async def stop_edit(client, message):
    user_id = message.from_user.id
    if user_id in ongoing_edits:
        del ongoing_edits[user_id]
        await message.reply("✅ Editing session **stopped** successfully.")
    else:
        await message.reply("❌ You are not in an active editing session.")

# 📝 /edit Command - Get Quiz & Show Edit Buttons
@app.on_message(filters.command("edit") & filters.private)
async def edit_quiz(client, message):
    args = message.text.split()

    if len(args) < 2:
        await message.reply("❌ Please provide a valid **Question Set ID**.\nExample: `/edit 12345`")
        return
    user_id = message.from_user.id
    owner_id = 7770737860  # Replace with your actual owner ID
    
    if args[1] == "-promo":
        if len(args) < 3:
            await message.reply("❌ Please provide the promo message or link.\nExample: `/edit -promo \"Check this out! https://t.me/abc\"`")
            return

        promo_text = message.text.split("-promo", 1)[1].strip()

        result = questions_collection.update_many(
            {"creator_id": user_id},
            {"$set": {"promo": promo_text}}
        )

        await message.reply(f"✅ Promo updated for {result.modified_count} quiz(es)!")
        return

    question_set_id = args[1]
    quiz = questions_collection.find_one({"question_set_id": question_set_id})

    if not quiz:
        quiz = qc_2.find_one({"question_set_id": question_set_id})
    if not quiz:
        await message.reply("❌ No quiz found with this ID.")
        return

    user_id = message.from_user.id
    owner_id = 7770737860  # Replace with your actual owner ID
    
    if quiz["creator_id"] != user_id and user_id != owner_id:
        await message.reply("❌ **This is not your quiz!** You can only edit quizzes you created.")
        return
    

    ongoing_edits[user_id] = {"question_set_id": question_set_id}

    keyboard_buttons = [
    [
        InlineKeyboardButton("📌 Edit Quiz Name", callback_data=f"edit_title_{question_set_id}"),
        InlineKeyboardButton("⏳ Edit Timer", callback_data=f"edit_timer_{question_set_id}")
    ],
    [
        InlineKeyboardButton("⚡ Edit Type", callback_data=f"edit_type_{question_set_id}"),
        InlineKeyboardButton("🏴‍☠️ -ve Marking", callback_data=f"edit_negative_{question_set_id}")
    ],
    [
        InlineKeyboardButton("📖 Edit Questions", callback_data=f"edit_questions_{question_set_id}"),
        InlineKeyboardButton("🔀 Shuffle", callback_data=f"shuffle_{question_set_id}")
    ]
        
    ]

    keyboard_buttons.append([
        InlineKeyboardButton("🔗 Add/Edit Promo", callback_data=f"edit_promo_{question_set_id}")
    ])

    
    
    if not quiz.get("sections", []):  # If sections is empty, show these buttons
        keyboard_buttons.append([
            InlineKeyboardButton("➕ Add Question", callback_data=f"add_question_{question_set_id}"),
            InlineKeyboardButton("➖ Delete Question", callback_data=f"delete_question_{question_set_id}")
        ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    await message.reply(f"📝 **Editing Quiz: {quiz['quiz_name']}**\n\nSelect what you want to edit, I am smart enough to deal with these stuffs 😎:", reply_markup=keyboard)

# 🎯 Handling Button Clicks
@app.on_callback_query(filters.regex(r"^pick_correct:"))
async def handle_pick_correct(client, callback_query: CallbackQuery):
    """Save the correct option for a forwarded open-poll question."""
    user_id = callback_query.from_user.id
    data = callback_query.data.split(":", 1)[1]

    if user_id not in user_quiz_data or "pending_poll" not in user_quiz_data[user_id]:
        await callback_query.answer("⚠️ This question is no longer pending.", show_alert=True)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    pending = user_quiz_data[user_id].pop("pending_poll")

    if data == "skip":
        await callback_query.answer("Skipped.")
        try:
            await callback_query.message.edit_text("⏭️ Question skipped. Send the next one.")
        except Exception:
            pass
        return

    try:
        correct_idx = int(data)
    except ValueError:
        await callback_query.answer("Invalid selection.", show_alert=True)
        return

    if not (0 <= correct_idx < len(pending["options"])):
        await callback_query.answer("Invalid option.", show_alert=True)
        return

    user_quiz_data[user_id]["questions"].append({
        "question": pending["question"],
        "options": pending["options"],
        "correct_option_id": correct_idx,
        "explanation": pending["explanation"],
        "file_id": pending["file_id"],
        "reply_text": pending["reply_text"],
    })

    total = len(user_quiz_data[user_id]["questions"])
    correct_text = pending["options"][correct_idx]
    await callback_query.answer("✅ Saved!")
    try:
        await callback_query.message.edit_text(
            f"✅ Question {total} saved with correct answer: **{correct_text}**\n\n"
            "Send the next poll / .txt / .pdf / link, or /done to finish."
        )
    except Exception:
        pass


# ── Inline keyboard helpers for /create flow ───────────────────
def _stmt_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Statement-Based", callback_data="cr|stmt|yes"),
         InlineKeyboardButton("❌ No, Normal", callback_data="cr|stmt|no")]
    ])

def _section_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Yes, Add Sections", callback_data="cr|sect|yes"),
         InlineKeyboardButton("🚀 No, Continue", callback_data="cr|sect|no")]
    ])

def _timer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("10s", callback_data="cr|timer|10"),
         InlineKeyboardButton("15s", callback_data="cr|timer|15"),
         InlineKeyboardButton("20s", callback_data="cr|timer|20")],
        [InlineKeyboardButton("30s", callback_data="cr|timer|30"),
         InlineKeyboardButton("45s", callback_data="cr|timer|45"),
         InlineKeyboardButton("60s", callback_data="cr|timer|60")],
        [InlineKeyboardButton("90s", callback_data="cr|timer|90"),
         InlineKeyboardButton("120s", callback_data="cr|timer|120")],
        [InlineKeyboardButton("✏️ Custom", callback_data="cr|timer|custom")]
    ])

def _neg_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("0  (None)", callback_data="cr|neg|0"),
         InlineKeyboardButton("¼  (0.25)", callback_data="cr|neg|025")],
        [InlineKeyboardButton("⅓  (0.33)", callback_data="cr|neg|033"),
         InlineKeyboardButton("½  (0.50)", callback_data="cr|neg|05")],
        [InlineKeyboardButton("✏️ Custom", callback_data="cr|neg|custom")]
    ])

def _shuffq_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Shuffle", callback_data="cr|shuffq|yes"),
         InlineKeyboardButton("❌ No, Keep Order", callback_data="cr|shuffq|no")]
    ])

def _shuffo_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Shuffle", callback_data="cr|shuffo|yes"),
         InlineKeyboardButton("❌ No, Keep Order", callback_data="cr|shuffo|no")]
    ])

def _promo_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Skip", callback_data="cr|promo|skip"),
         InlineKeyboardButton("✏️ Add Promo", callback_data="cr|promo|custom")]
    ])

def _type_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 Free", callback_data="cr|type|free"),
         InlineKeyboardButton("💰 Paid", callback_data="cr|type|paid")]
    ])


async def _finalize_and_save_quiz(client, cq_or_msg, user_id: int, quiz_type: str):
    """Save quiz to DB and send the success message with inline buttons."""
    import gc as _gc
    ud = user_quiz_data[user_id]
    quiz_name = ud["quiz_name"]
    timer = ud.get("timer")
    sections = ud.get("sections", [])
    negative_marking = ud.get("negative_marking", 0.0)
    promo = ud.get("promo")
    shuffle_q = ud.get("shuffle", False)
    shuffle_o = ud.get("shuffle_options", False)
    ud["type"] = quiz_type
    question_set_id = generate_random_id()

    questions_collection.insert_one({
        "question_set_id": question_set_id,
        "creator_id": user_id,
        "quiz_name": quiz_name,
        "questions": ud["questions"],
        "sections": sections,
        "timer": timer,
        "type": quiz_type,
        "negative_marking": negative_marking,
        "promo": promo,
        "shuffle": shuffle_q,
        "shuffle_options": shuffle_o,
    })

    del user_quiz_data[user_id]
    _gc.collect()

    start_deep_link = f"https://t.me/{client.me.username}?start={question_set_id}"
    group_start_deep_link = f"https://t.me/{client.me.username}?startgroup={question_set_id}"
    saved = questions_collection.find_one({"question_set_id": question_set_id})
    num_q = len(saved["questions"]) if saved else 0

    quiz_text = (
        f"> **Quiz Created Successfully!**\n\n"
        f"**💳 Quiz Name:** {quiz_name}\n"
        f"**#️⃣ Questions:** {num_q}\n"
        f"**⏰ Timer:** {timer} seconds\n"
        f"**🆔 Quiz ID:** `{question_set_id}`\n"
        f"**💰 Type:** `{quiz_type}`\n"
        f"**🏴‍☠️ -ve Marking:** `{negative_marking:.2f}`\n"
        f"**🔀 Shuffle Q / Opt:** `{'✅' if shuffle_q else '❌'}` / `{'✅' if shuffle_o else '❌'}`\n"
    )

    if sections:
        quiz_text += "\n\n> **📂 Sections:**"
        for i, section in enumerate(sections, start=1):
            s_name = section["name"]
            s_start, s_end = section["question_range"]
            s_timer = section.get("timer", "Not specified")
            quiz_text += (
                f"\n\n**Section {i}:** {s_name}\n"
                f"  - **Questions:** {s_start} to {s_end}\n"
                f"  - **Timer:** {s_timer} seconds"
            )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Start Quiz Now", url=start_deep_link)],
        [InlineKeyboardButton("🚀 Start Quiz in Group", url=group_start_deep_link)],
        [InlineKeyboardButton("🔗 Share Quiz", switch_inline_query=question_set_id)]
    ])

    if isinstance(cq_or_msg, CallbackQuery):
        await cq_or_msg.message.edit_text(quiz_text, reply_markup=keyboard)
        chat_id = cq_or_msg.message.chat.id
    else:
        await cq_or_msg.reply(quiz_text, reply_markup=keyboard)
        chat_id = cq_or_msg.chat.id

    if BOT_GROUP:
        fresh_text = await remove_baby(quiz_text)
        try:
            await app.send_message(BOT_GROUP, fresh_text, reply_markup=keyboard)
        except Exception as e:
            print(f"BOT_GROUP send_message failed: {e}")


@app.on_callback_query(filters.regex(r"^cr\|"))
async def handle_create_callback(client, callback_query: CallbackQuery):
    """Handle all inline buttons in the /create quiz flow."""
    user_id = callback_query.from_user.id

    if user_id not in user_quiz_data:
        await callback_query.answer("❌ No active quiz session. Use /create first.", show_alert=True)
        return

    await callback_query.answer()
    parts = callback_query.data.split("|")
    step = parts[1] if len(parts) > 1 else ""
    value = parts[2] if len(parts) > 2 else ""
    ud = user_quiz_data[user_id]

    # ── Statement-based choice ─────────────────────────────────
    if step == "stmt":
        ud["statement_based"] = (value == "yes")
        ud.pop("awaiting_statement_based", None)
        flag = "✅ Statement-based mode ON" if value == "yes" else "✅ Normal mode"
        await callback_query.message.edit_text(
            f"{flag}\n\n"
            "Now send questions in the stated format, upload a `.txt`, `.json` or `.pdf` file, "
            "or forward quiz polls.\n\n"
            "Type /done when finished or /cancel to stop."
        )
        return

    # ── Section choice ─────────────────────────────────────────
    if step == "sect":
        ud.pop("awaiting_section_choice", None)
        if value == "yes":
            ud["section_wise"] = True
            ud["awaiting_section_count"] = True
            await callback_query.message.edit_text(
                "📌 How many sections do you want? (Must be greater than 1)"
            )
        else:
            ud["section_wise"] = False
            await callback_query.message.edit_text(
                "⏰ **Select Quiz Timer:**\n_Time limit per question_",
                reply_markup=_timer_keyboard()
            )
        return

    # ── Timer selection ────────────────────────────────────────
    if step == "timer":
        if value == "custom":
            ud["awaiting_timer"] = True
            await callback_query.message.edit_text(
                "⏳ Enter the quiz timer in seconds (greater than 10 sec):"
            )
        else:
            timer_val = int(value)
            ud["timer"] = timer_val
            await callback_query.message.edit_text(
                f"⏰ Timer set to **{timer_val}s**\n\n"
                "📝 **Select Negative Marking:**",
                reply_markup=_neg_keyboard()
            )
        return

    # ── Negative marking selection ─────────────────────────────
    if step == "neg":
        if value == "custom":
            ud["awaiting_negative_marking"] = True
            await callback_query.message.edit_text(
                "📝 Enter negative marking value (0 to <1)\n"
                "e.g. `0.25`, `1/3`, `0` for none:"
            )
        else:
            neg_map = {"0": 0.0, "025": 0.25, "033": round(1/3, 4), "05": 0.5}
            neg_val = neg_map.get(value, 0.0)
            ud["negative_marking"] = neg_val
            await callback_query.message.edit_text(
                f"📝 Negative marking: **{neg_val:.2f}**\n\n"
                "🔀 **Shuffle Questions?**\n"
                "_Randomise question order each time the quiz starts_",
                reply_markup=_shuffq_keyboard()
            )
        return

    # ── Shuffle questions ──────────────────────────────────────
    if step == "shuffq":
        ud["shuffle"] = (value == "yes")
        await callback_query.message.edit_text(
            f"🔀 Shuffle questions: **{'ON ✅' if value == 'yes' else 'OFF ❌'}**\n\n"
            "🔀 **Shuffle Options?**\n"
            "_Randomise A/B/C/D order for each question_",
            reply_markup=_shuffo_keyboard()
        )
        return

    # ── Shuffle options ────────────────────────────────────────
    if step == "shuffo":
        ud["shuffle_options"] = (value == "yes")
        await callback_query.message.edit_text(
            f"🔀 Shuffle options: **{'ON ✅' if value == 'yes' else 'OFF ❌'}**\n\n"
            "🔗 **Add a Promo Link / Message?**\n"
            "_Sent every 15 questions during the quiz_",
            reply_markup=_promo_keyboard()
        )
        return

    # ── Promo ──────────────────────────────────────────────────
    if step == "promo":
        if value == "custom":
            ud["awaiting_promo"] = True
            await callback_query.message.edit_text(
                "🔗 Send your promo message or link:\n"
                "_(e.g. https://t.me/yourchannel or any text)_"
            )
        else:
            ud["promo"] = None
            await callback_query.message.edit_text(
                "🔗 No promo added.\n\n"
                "💰 **Select Quiz Type:**",
                reply_markup=_type_keyboard()
            )
        return

    # ── Quiz type — triggers finalization ──────────────────────
    if step == "type":
        if value not in ("free", "paid"):
            await callback_query.answer("❌ Invalid type.", show_alert=True)
            return
        await _finalize_and_save_quiz(client, callback_query, user_id, value)
        return


@app.on_callback_query()
async def handle_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if user_id not in ongoing_edits:
        return

    question_set_id = ongoing_edits[user_id]["question_set_id"]

    if data.startswith("edit_title_"):
        await callback_query.message.edit("✍️ Send the new **Quiz Name**:")
        ongoing_edits[user_id]["field"] = "quiz_name"

    elif data.startswith("edit_timer_"):
        await callback_query.message.edit("⏳ Send the new **Timer** (in seconds):")
        ongoing_edits[user_id]["field"] = "timer"

    elif data.startswith("edit_type_"):
        await callback_query.message.edit("⚡ Send the new **Quiz Type** (free/paid):")
        ongoing_edits[user_id]["field"] = "type"

    elif data.startswith("edit_negative_"):
        await callback_query.message.edit("➖ Send the new **Negative Marking** (e.g., 0.25):")
        ongoing_edits[user_id]["field"] = "negative_marking"

    elif data.startswith("edit_questions_"):
        quiz = questions_collection.find_one({"question_set_id": question_set_id})
        total_questions = len(quiz["questions"])
        await callback_query.message.edit(f"📖 There are `{total_questions}` questions.\n\nSend the **Question Number** you want to edit:")
        ongoing_edits[user_id]["field"] = "question_number"

    elif data.startswith("add_question_"):
        await callback_query.message.edit("📝 Send the new question in the following format:\n\n"
                                          "Question Text\n"
                                          "Option 1\n"
                                          "Option 2 ✅\n"
                                          "Option 3\n"
                                          "Ex: Explanation (optional)")
        ongoing_edits[user_id]["field"] = "add_question"

    elif data.startswith("delete_question_"):
        quiz = questions_collection.find_one({"question_set_id": question_set_id})
        total_questions = len(quiz["questions"])
        await callback_query.message.edit(f"➖ There are `{total_questions}` questions.\n\n"
                                           "Send the **Question Number** you want to delete:")
        ongoing_edits[user_id]["field"] = "delete_question"

    elif data.startswith("edit_promo_"):
        question_set_id = data.split("_")[-1]

        ongoing_edits[user_id] = {
            "question_set_id": question_set_id,
            "field": "promo"
        }

        await callback_query.message.reply(
            "🔗 Send the **promo URL** or message for this quiz.\n"
            "Example: https://t.me/yourchannel or message\n"
            "Or send `remove` to delete the promo link/message."
        )
        await callback_query.answer()

    elif data.startswith("shuffle_"):
        quiz = questions_collection.find_one({"question_set_id": question_set_id})
        shuffle_questions_enabled = quiz.get("shuffle", False)
        shuffle_options_enabled = quiz.get("shuffle_options", False)
        shuffle_questions_text = "Shuffle Questions ✅" if shuffle_questions_enabled else "Shuffle Questions"
        shuffle_options_text = "Shuffle Options ✅" if shuffle_options_enabled else "Shuffle Options"
        keyboard_buttons = [
            [InlineKeyboardButton(shuffle_options_text, callback_data=f"other_shuffle_{question_set_id}")]
        ]

        if not quiz.get("sections", []):  # If sections list is empty, show "Shuffle Questions"
            shuffle_questions_text = "Shuffle Questions ✅" if shuffle_questions_enabled else "Shuffle Questions"
            keyboard_buttons.insert(0, [InlineKeyboardButton(shuffle_questions_text, callback_data=f"edit_shuffle_{question_set_id}")])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await callback_query.message.edit("🔀 Select a shuffle option:", reply_markup=keyboard)

    elif data.startswith("edit_shuffle_"):

        quiz = questions_collection.find_one({"question_set_id": question_set_id})
        new_shuffle_value = not quiz.get("shuffle", False)
        questions_collection.update_one(
            {"question_set_id": question_set_id},
            {"$set": {"shuffle": new_shuffle_value}}
        )
        quiz = questions_collection.find_one({"question_set_id": question_set_id})
        shuffle_questions_enabled = quiz.get("shuffle", False)
        shuffle_options_enabled = quiz.get("shuffle_options", False)
        shuffle_questions_text = f"Shuffle Questions {'✅' if shuffle_questions_enabled else ''}"
        shuffle_options_text = f"Shuffle Options {'✅' if shuffle_options_enabled else ''}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(shuffle_questions_text, callback_data=f"edit_shuffle_{question_set_id}")],
            [InlineKeyboardButton(shuffle_options_text, callback_data=f"other_shuffle_{question_set_id}")]
        ])
        await callback_query.message.edit_text("🔀 Select a shuffle option:", reply_markup=keyboard)
    
    elif data.startswith("other_shuffle_"):

        quiz = questions_collection.find_one({"question_set_id": question_set_id})
        new_shuffle_value = not quiz.get("shuffle_options", False)
        questions_collection.update_one(
            {"question_set_id": question_set_id},
            {"$set": {"shuffle_options": new_shuffle_value}}
        )
        quiz = questions_collection.find_one({"question_set_id": question_set_id})
        shuffle_questions_enabled = quiz.get("shuffle", False)
        shuffle_options_enabled = quiz.get("shuffle_options", False)
        shuffle_questions_text = f"Shuffle Questions {'✅' if shuffle_questions_enabled else ''}"
        shuffle_options_text = f"Shuffle Options {'✅' if shuffle_options_enabled else ''}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(shuffle_questions_text, callback_data=f"edit_shuffle_{question_set_id}")],
            [InlineKeyboardButton(shuffle_options_text, callback_data=f"other_shuffle_{question_set_id}")]
        ])
        await callback_query.message.edit_text("🔀 Select a shuffle option:", reply_markup=keyboard)

async def extract_quiz_questions(app: Client, url_message: str, user_id: int, log_group_id: int, user_quiz_data: dict):
    """
    Extract quiz questions from URL using PHP API and process them for Pyrogram quiz.
    
    Args:
        app: Pyrogram Client instance
        url_message: Message containing URL and range (e.g., "https://rojgarwithankit.co.in/test-series/589/test-ssc/30109/terms 12-20")
        user_id: User ID for storing quiz data
        log_group_id: Log group chat ID for uploading images
        user_quiz_data: Global dictionary to append questions to
    
    Returns:
        int: Number of questions extracted
    """
    

    parts = url_message.strip().split()
    url = parts[0]
    question_range = parts[1] if len(parts) > 1 else None
    subject_id = None
    
    url_pattern = r'/test-series/(\d+)/[^/]+/(\d+)'
    match = re.search(url_pattern, url)
    subject_match = re.search(r'[?&]subjectId=(\d+)', url)
    subject_id = subject_match.group(1) if subject_match else None
    if not match:
        raise ValueError(
            "Invalid URL format. Expected format: "
            "/test-series/{series_id}/<any>/{test_id}/terms"
            )
    
    test_series_id = match.group(1)
    test_id = match.group(2)
    

    start_idx = 0
    end_idx = None
    
    if question_range:
        range_match = re.match(r'(\d+)-(\d+)', question_range)
        if range_match:
            start_idx = int(range_match.group(1)) - 1  # Convert to 0-based index
            end_idx = int(range_match.group(2))
    

    api_url = "purchase the api"
    
    try:
        params = {
        'test_series_id': test_series_id,
        'test_id': test_id,
        'user_id': user_id
        }

        if subject_id:
            params['subject_id'] = subject_id
        
        api_response = requests.get(
            api_url,
            params=params,
            timeout=30
        )
        api_response.raise_for_status()
        api_data = api_response.json()
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch from PHP API: {str(e)}")
    

    if api_data.get('status') != 'success':
        error_msg = api_data.get('message', 'Unknown error from API')
        raise Exception(f"API Error: {error_msg}")
    

    questions_url = api_data.get('questions_url')
    if not questions_url:
        raise ValueError("Questions URL not found in API response")
    

    try:
        questions_response = requests.get(questions_url, timeout=30)
        questions_response.raise_for_status()
        questions_data = questions_response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch questions: {str(e)}")
    

    if end_idx:
        questions_to_process = questions_data[start_idx:end_idx]
    else:
        questions_to_process = questions_data[start_idx:]
    

    if user_id not in user_quiz_data:
        user_quiz_data[user_id] = {"questions": []}
    

    processed_count = 0
    

    for q_data in questions_to_process:
        try:

            has_option_image = any([
                q_data.get(f'option_image_{i}', '').strip() 
                for i in range(1, 11)
            ])
            
            if has_option_image:
                print(f"Skipping question {q_data.get('id')} - contains option images")
                continue
            

            question_html = q_data.get('question', '')
            question_text = clean_html(question_html)
            

            options = []
            for i in range(1, 11):
                option_html = q_data.get(f'option_{i}', '').strip()
                if option_html:
                    option_text = clean_html(option_html)
                    options.append(option_text)
            

            if len(options) < 2 or len(options) > 10:
                print(f"Skipping question {q_data.get('id')} - invalid number of options: {len(options)}")
                continue
            

            correct_answer = q_data.get('answer', '1')
            correct_option_index = int(correct_answer) - 1
            

            solution_html = q_data.get('solution_text', '')
            explanation = clean_html(solution_html)
            

            file_id = None
            image_links = [
                q_data.get('image_link_1', '').strip(),
                q_data.get('image_link_2', '').strip(),
                q_data.get('image_link_3', '').strip()
            ]
            

            for img_url in image_links:
                if img_url:
                    try:
                        file_id = await upload_image_to_log_group(app, img_url, log_group_id)
                        if file_id:
                            break
                    except Exception as e:
                        print(f"Failed to upload image {img_url}: {e}")
            

            user_quiz_data[user_id]["questions"].append({
                "question": question_text,
                "options": options,
                "correct_option_id": correct_option_index,
                "explanation": explanation,
                "reply_text": "",  # No reply text needed
                "file_id": file_id,
            })
            
            processed_count += 1
            
        except Exception as e:
            print(f"Error processing question {q_data.get('id')}: {e}")
            continue
    
    return processed_count

async def upload_image_to_log_group(app: Client, image_url: str, log_group_id: int) -> str:
    """
    Upload image to log group and return file_id.
    
    Args:
        app: Pyrogram Client instance
        image_url: URL of the image to upload
        log_group_id: Chat ID of the log group
    
    Returns:
        str: file_id of the uploaded image
    """

    response = requests.get(image_url, timeout=10)
    response.raise_for_status()
    

    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
        tmp_file.write(response.content)
        tmp_path = tmp_file.name
    
    try:

        message = await app.send_photo(
            chat_id=log_group_id,
            photo=tmp_path,
            caption=f"Quiz image from: {image_url}"
        )
        

        file_id = message.photo.file_id
        
        return file_id
    
    finally:

        if os.path.exists(tmp_path):
            os.remove(tmp_path)

async def handle_rojgar_link(client: Client, message: Message, log_group_id: int, user_quiz_data: dict):
    """
    Handler for rojgarwithankit.co.in links.
    Extracts quiz questions and appends them to user_quiz_data.
    
    Args:
        client: Pyrogram Client instance
        message: Message object
        log_group_id: Log group chat ID for uploading images
        user_quiz_data: Dictionary to append questions to
    
    Returns:
        int: Number of questions extracted
    """
    user_id = message.from_user.id
    

    url_message = message.text
    

    processing_msg = await message.reply_text("⏳ Processing quiz questions...")
    
    try:
        processed_count = await extract_quiz_questions(
            app=client,
            url_message=url_message,
            user_id=user_id,
            log_group_id=log_group_id,
            user_quiz_data=user_quiz_data
        )
        
        if processed_count == 0:
            await processing_msg.edit_text("❌ No valid questions found in the specified range.")
            return 0
        
        await processing_msg.edit_text(
            f"✅ Extracted {processed_count} questions successfully!\n"
            f"Total questions in queue: {len(user_quiz_data[user_id]['questions'])}"
        )
        
        return processed_count
        
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
        print(f"Error in handle_rojgar_link: {e}")
        return 0

_INLINE_OPT_RE = re.compile(r'^[A-Ea-e][)\.]\s*')
_PROMO_LINE_RE = re.compile(r'𝐉𝐎𝐈𝐍|JOIN\s*➢|@Quickstudy\d+', re.IGNORECASE)
_TABLE_SEP_RE = re.compile(r'^\|?\s*:?-{2,}:?\s*(\|?\s*:?-{2,}:?\s*)+\|?\s*$')
_TABLE_ROW_RE = re.compile(r'^\|(.+)\|$')


def _strip_promo_suffix(text: str) -> str:
    """Remove channel-join promo tails from a line or explanation."""
    if not text:
        return text
    text = re.sub(r'\s*𝐉𝐎𝐈𝐍\s*➢\s*@\S+.*$', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\s*JOIN\s*➢\s*@\S+.*$', '', text, flags=re.IGNORECASE).strip()
    return text


def _normalize_table_row(line: str) -> str:
    """Convert a markdown table row into a plain 'left → right' line."""
    inner = line.strip().strip('|')
    cells = [c.strip() for c in inner.split('|') if c.strip()]
    if len(cells) >= 2:
        return f"{cells[0]} → {cells[1]}"
    return cells[0] if cells else line


def _sanitize_input_lines(lines: list) -> list:
    """Drop promo-only lines, table separators, and normalize table rows."""
    cleaned = []
    for ln in lines:
        if _PROMO_LINE_RE.search(ln) and not ln.startswith(("Ex:", "RT:", "ID:")):
            if ln.startswith("Ex:"):
                ln = "Ex: " + _strip_promo_suffix(ln[3:].strip())
                if ln == "Ex:":
                    continue
            else:
                continue
        if _TABLE_SEP_RE.match(ln.strip()):
            continue
        if ln.strip().startswith('|') and ln.strip().endswith('|'):
            ln = _normalize_table_row(ln.strip())
        cleaned.append(ln)
    return cleaned


def _parse_inline_question(lines: list) -> tuple:
    """Parse an inline question block (list of text lines) and return
    (question_text, options, correct_option_id, explanation).

    Supports two formats:

    1. Classic (single-line question):
       Question text
       Option A
       Option B ✅
       Option C
       Ex: Explanation

    2. 👇-separator (multi-line question):
       Question line 1
       I. Statement one.
       II. Statement two.
       Final sub-question?
       👇 ─────────────────
       A) Option A
       B) Option B ✅
       C) Option C
       D) Option D
       Ex: Explanation
    """
    options = []
    correct_option_id = None
    explanation = None

    emoji_sep_idx = next(
        (idx for idx, ln in enumerate(lines) if '👇' in ln),
        None
    )

    if emoji_sep_idx is not None:
        question_parts = [l.strip() for l in lines[:emoji_sep_idx] if l.strip()]
        question_text = "\n".join(question_parts)
        for ln in lines[emoji_sep_idx + 1:]:
            ln = ln.strip()
            if not ln:
                continue
            if ln.startswith("Ex:"):
                explanation = ln[3:].strip()
                continue
            clean = _INLINE_OPT_RE.sub('', ln).strip()
            if "✅" in clean:
                correct_option_id = len(options)
                clean = clean.replace("✅", "").strip()
            if clean:
                options.append(clean)
    else:
        question_text = lines[0].strip() if lines else ""
        # Find the first explicit A)/B)/C)/D) option line.
        # Everything before it is part of the question body.
        option_start_idx = None
        for scan_i in range(1, len(lines)):
            sl = lines[scan_i].strip()
            if sl.startswith("Ex:"):
                continue
            if _INLINE_OPT_RE.match(sl):
                option_start_idx = scan_i
                break

        if option_start_idx is not None:
            # Lines between heading and first A) → append to question text
            extra_q = []
            for qln in lines[1:option_start_idx]:
                qln = qln.strip()
                if not qln:
                    continue
                if qln.startswith("Ex:"):
                    explanation = qln[3:].strip()
                    continue
                extra_q.append(qln)
            if extra_q:
                question_text = question_text + "\n" + "\n".join(extra_q)

            # Only A)/B)/C)/D) lines become poll options
            for ln in lines[option_start_idx:]:
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith("Ex:"):
                    explanation = ln[3:].strip()
                    continue
                if not _INLINE_OPT_RE.match(ln):
                    continue
                clean = _INLINE_OPT_RE.sub('', ln).strip()
                if "✅" in clean:
                    correct_option_id = len(options)
                    clean = clean.replace("✅", "").strip()
                if clean:
                    options.append(clean)
        elif any(re.search(
                r'(Reason\s*\(R\)|कारण\s*\(R\)|Assertion\s*\(A\)|कथन\s*\(A\))',
                ln, re.IGNORECASE) for ln in lines):
            # ── Assertion-Reason format (inline) ────────────────────────
            _AR_INSTR_RE2 = re.compile(
                r'(कूट|नीचे\s+दिए|Choose\s+the\s+correct|correct\s+answer\s+using)',
                re.IGNORECASE)
            _DASH_PFX = re.compile(r'^[-•]\s*')
            _NUM_PFX = re.compile(r'^[\(\[]?[1-4][\)\]\.]\s*')

            instr_idx = None
            for scan_i in range(1, len(lines)):
                if _AR_INSTR_RE2.search(lines[scan_i]):
                    instr_idx = scan_i
                    break

            if instr_idx is not None:
                q_body_end = instr_idx + 1
                opts_start = instr_idx + 1
            else:
                non_sp = [j for j in range(1, len(lines))
                          if lines[j].strip() and not lines[j].strip().startswith("Ex:")]
                if len(non_sp) >= 4:
                    q_body_end = non_sp[-4]
                    opts_start = non_sp[-4]
                else:
                    q_body_end = len(lines)
                    opts_start = len(lines)

            extra_q = []
            for qln in lines[1:q_body_end]:
                qln = _DASH_PFX.sub('', qln.strip()).strip()
                if not qln or qln.startswith("Ex:"):
                    continue
                extra_q.append(qln)
            if extra_q:
                question_text = question_text + "\n" + "\n".join(extra_q)

            for ln in lines[opts_start:]:
                ln = _DASH_PFX.sub('', ln.strip()).strip()
                if not ln:
                    continue
                if ln.startswith("Ex:"):
                    explanation = ln[3:].strip()
                    continue
                ln = _NUM_PFX.sub('', ln).strip()
                if not ln:
                    continue
                clean = ln
                if "✅" in clean:
                    correct_option_id = len(options)
                    clean = clean.replace("✅", "").strip()
                if clean:
                    options.append(clean)
        else:
            # Legacy fallback: no A)/B)/C)/D) labels — every line is an option
            for ln in lines[1:]:
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith("Ex:"):
                    explanation = ln[3:].strip()
                    break
                clean = _INLINE_OPT_RE.sub('', ln).strip()
                if "✅" in ln:
                    correct_option_id = len(options)
                    clean = ln.replace("✅", "").strip()
                    clean = _INLINE_OPT_RE.sub('', clean).strip()
                if clean:
                    options.append(clean)

    question_text = _strip_promo_suffix(question_text)
    if explanation:
        explanation = _strip_promo_suffix(explanation)

    return question_text, options, correct_option_id, explanation


@app.on_message(
    (filters.text | filters.poll) & 
    filters.private & 
    ~filters.command([
        "start", "create", "myquizzes", "pause", "features", "gcast", "fast", "slow", "normal",
        "stopcast", "resume", "edit", "info", "ban", "done", "add", "rem", "assignment", "submit",
        "remall", "del", "remove", "clearlist", "stats", "help", "stop", "stopedit", "cancel", "ocr", "login", "quiz", "addfilter", "listfilters", "removefilter", "quizhelp", "fixquiz"
    ])
)
async def handle_all_messages(client, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    

    if user_id in ongoing_edits:
        question_set_id = ongoing_edits[user_id]["question_set_id"]
        field = ongoing_edits[user_id].get("field")
        
        if field in ["quiz_name", "timer", "type", "negative_marking", "promo"]:
            new_value = message.text.strip()
            

            if field == "timer":
                if not new_value.isdigit() or int(new_value) <= 9:
                    await message.reply("❌ Invalid timer! Please enter a number greater than 9 seconds.")
                    return
                new_value = int(new_value)

            elif field == "quiz_name":
                new_value = new_value

            elif field == "promo":
                new_value = message.text.strip()
                if new_value.lower() == "remove":
                    new_value = None

            elif field == "type":
                if new_value.lower() not in ["free", "paid"]:
                    await message.reply("❌ Invalid type! Please enter either 'free' or 'paid'.")
                    return
                new_value = new_value.lower()
                

            elif field == "negative_marking":
                try:
                    if new_value.isdigit():
                        new_value = int(new_value)
                    else:
                        new_value = float(fractions.Fraction(new_value)) if "/" in new_value else float(new_value)
                    
                    if new_value >= 1 or new_value < 0:
                        await message.reply("❌ Negative marking cannot be less than 0 and greater or equal to 1! Send again...")
                        return
                except ValueError:
                    await message.reply("❌ Invalid input! Please enter a number.")
                    return
            

            questions_collection.update_one(
                {"question_set_id": question_set_id},
                {"$set": {field: new_value}}
            )
            
            await message.reply("✅ **Updated Successfully!**")
            del ongoing_edits[user_id]
            
        elif field == "question_number":
            quiz = questions_collection.find_one({"question_set_id": question_set_id})
            total_questions = len(quiz["questions"])
            
            try:
                question_index = int(message.text.strip()) - 1
                if question_index < 0 or question_index >= total_questions:
                    await message.reply("❌ Invalid question number! Please enter a valid number.")
                    return
            except ValueError:
                await message.reply("❌ Please enter a valid number.")
                return
                
            ongoing_edits[user_id]["question_index"] = question_index
            await message.reply(f"📝 Send the **updated question text** for Question `{question_index + 1}`:")
            ongoing_edits[user_id]["field"] = "update_question_text"
            
        elif field == "update_question_text":
            question_index = ongoing_edits[user_id]["question_index"]
            reply_message = message.reply_to_message
            reply_text = reply_message.text if reply_message and reply_message.text else None
            file_id = None
            
            if reply_message and reply_message.photo:
                copied_message = await client.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=reply_message.chat.id,
                    message_id=reply_message.id,
                )
                file_id = copied_message.photo.file_id
                
            new_question_text = message.text.split("\n")
            question_text, options, correct_option_id, explanation = _parse_inline_question(new_question_text)
                    
            if not question_text or len(options) < 2 or correct_option_id is None:
                await message.reply("❌ Invalid question format. Please follow the correct format.")
                return
                

            questions_collection.update_one(
                {"question_set_id": question_set_id},
                {"$set": {f"questions.{question_index}": {
                    "question": question_text,
                    "options": options,
                    "correct_option_id": correct_option_id,
                    "explanation": explanation,
                    "file_id": file_id,
                    "reply_text": reply_text
                }}}
            )
            
            await message.reply("✅ **Question Updated Successfully!**")
            del ongoing_edits[user_id]
            
        elif field == "add_question":
            new_question_text = message.text.split("\n")
            question_text, options, correct_option_id, explanation = _parse_inline_question(new_question_text)
                    
            if not question_text or len(options) < 2 or correct_option_id is None:
                await message.reply("❌ Invalid question format. Please follow the correct format.")
                return
                

            questions_collection.update_one(
                {"question_set_id": question_set_id},
                {"$push": {"questions": {
                    "question": question_text,
                    "options": options,
                    "correct_option_id": correct_option_id,
                    "explanation": explanation,
                    "file_id": None,
                    "reply_text": None
                }}}
            )
            
            await message.reply("✅ **Question Added Successfully!**")
            del ongoing_edits[user_id]
            
        elif field == "delete_question":
            try:
                input_text = message.text.strip()
                

                if input_text.isdigit():
                    question_index = int(input_text) - 1
                    quiz = questions_collection.find_one({"question_set_id": question_set_id})
                    total_questions = len(quiz["questions"])
                    
                    if question_index < 0 or question_index >= total_questions:
                        await message.reply("❌ Invalid question number! Please enter a valid number.")
                        return
                    

                    questions_collection.update_one(
                        {"question_set_id": question_set_id},
                        {"$pull": {"questions": quiz["questions"][question_index]}}
                    )
                    await message.reply("✅ **Question Deleted Successfully!**")
                

                elif "-" in input_text:
                    parts = input_text.split("-")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        start = int(parts[0]) - 1
                        end = int(parts[1]) - 1
                        
                        quiz = questions_collection.find_one({"question_set_id": question_set_id})
                        total_questions = len(quiz["questions"])
                        
                        if start < 0 or end >= total_questions or start > end:
                            await message.reply("❌ Invalid range! Please enter a valid range (e.g., 1-10).")
                            return
                        

                        questions_to_keep = [
                            q for idx, q in enumerate(quiz["questions"])
                            if idx < start or idx > end
                        ]
                        

                        questions_collection.update_one(
                            {"question_set_id": question_set_id},
                            {"$set": {"questions": questions_to_keep}}
                        )
                        
                        deleted_count = end - start + 1
                        await message.reply(f"✅ **Deleted {deleted_count} questions successfully!**")
                    else:
                        await message.reply("❌ Invalid range format! Please use format like '1-10'.")
                else:
                    await message.reply("❌ Invalid input! Please enter a number (e.g., 5) or range (e.g., 1-10).")
                    
                del ongoing_edits[user_id]
                
            except ValueError:
                await message.reply("❌ Please enter a valid number or range.")
            except Exception as e:
                print(f"Error deleting questions: {str(e)}")
                await message.reply("❌ An error occurred while deleting questions.")
        
        return
    

    if user_id in user_quiz_data:
        user_data = user_quiz_data[user_id]
        

        if message.poll:
            poll = message.poll
            

            user_db = users_collection.find_one({"chat_id": chat_id})
            remove_words = user_db.get("remove_words", []) if user_db else []
            
            if poll.type != PollType.QUIZ:
                await message.reply("Invalid poll detected, send Quiz Type Poll")
                return

            question = filter_words(poll.question, remove_words)
            question = await remove_baby(question)

            options = [filter_words(option.text, remove_words) for option in poll.options]

            description = None
            poll_explanation = getattr(poll, "explanation", None)
            if poll_explanation:
                description = filter_words(poll_explanation, remove_words)
                description = await remove_baby(description, keep_links=True)

            reply_message = message.reply_to_message
            reply_text = reply_message.text if reply_message and reply_message.text else None
            file_id = None

            if reply_message and reply_message.photo:
                if BOT_GROUP:
                    copied_message = await client.copy_message(
                        chat_id=BOT_GROUP,
                        from_chat_id=reply_message.chat.id,
                        message_id=reply_message.id,
                    )
                    file_id = copied_message.photo.file_id
                else:
                    file_id = reply_message.photo.file_id

            # Pyrogram exposes `correct_option_id` only when the poll's answer
            # has been revealed to the bot (e.g. user voted, or quiz is closed).
            # For forwarded *open* quiz polls, the value is None even though the
            # user can visually see the right answer in the client. Instead of
            # rejecting these, stash the question and ask the user to tap the
            # correct option via inline buttons.
            correct_option_id = getattr(poll, "correct_option_id", None)
            if correct_option_id is None:
                user_quiz_data[user_id]["pending_poll"] = {
                    "question": question,
                    "options": options,
                    "explanation": description,
                    "file_id": file_id,
                    "reply_text": reply_text,
                }
                buttons = []
                row = []
                for idx, opt_text in enumerate(options):
                    label = f"{idx + 1}. {opt_text}"
                    if len(label) > 30:
                        label = label[:27] + "…"
                    row.append(InlineKeyboardButton(label, callback_data=f"pick_correct:{idx}"))
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
                buttons.append([InlineKeyboardButton("❌ Skip this question", callback_data="pick_correct:skip")])

                await message.reply(
                    "🤔 I couldn't auto-detect the correct answer for this poll "
                    "(it's an open/active quiz, so Telegram doesn't share the answer with bots).\n\n"
                    f"**Q:** {question}\n\n"
                    "👉 Please tap the **correct** option below:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return

            user_quiz_data[user_id]["questions"].append({
                "question": question,
                "options": options,
                "correct_option_id": correct_option_id,
                "explanation": description,
                "file_id": file_id,
                "reply_text": reply_text
            })

            total = len(user_quiz_data[user_id]["questions"])
            await message.reply(f"✅ {total} Question saved! Send the next poll / TestBook Test Link or question set or type /done when finished or /cancel to cancel the quiz creation.")
            await asyncio.sleep(2)
            return
            

        if user_data.get("awaiting_name"):
            quiz_name = message.text.strip()
            if not quiz_name:
                await message.reply("❌ Invalid quiz name. Please send a valid name.")
                return
                
            user_quiz_data[user_id]["quiz_name"] = quiz_name
            user_quiz_data[user_id]["awaiting_name"] = False
            user_quiz_data[user_id]["awaiting_statement_based"] = True
            await message.reply(
                f"✅ Quiz name set to: **{quiz_name}**\n\n"
                "📋 **Is this a statement-based quiz?**\n"
                "_(Questions with I. II. III. sub-statements before the options)_",
                reply_markup=_stmt_keyboard()
            )
            return

        # awaiting_statement_based is now handled by handle_create_callback (cr|stmt|*)
        # awaiting_section_choice is now handled by handle_create_callback (cr|sect|*)

        if user_data.get("awaiting_timer"):
            try:
                timer = int(message.text.strip())
                if timer <= 9:
                    raise ValueError
            except ValueError:
                await message.reply("❌ Invalid timer. Please send the time in seconds greater than 9 seconds (e.g., 60).")
                return
                
            user_quiz_data[user_id]["timer"] = timer
            del user_quiz_data[user_id]["awaiting_timer"]
            await message.reply(
                f"⏰ Timer set to **{timer}s**\n\n"
                "📝 **Select Negative Marking:**",
                reply_markup=_neg_keyboard()
            )
            return
            
        if user_data.get("awaiting_section_count"):
            try:
                section_count = int(message.text.strip())
                if section_count < 2:
                    raise ValueError
            except ValueError:
                await message.reply("❌ Invalid number. Please enter an integer greater than 1.")
                return
                
            user_data["section_count"] = section_count
            user_data["sections"] = []
            user_data["current_section"] = 1
            user_data["last_range_end"] = 0
            del user_data["awaiting_section_count"]
            user_data["awaiting_section_name"] = True
            
            await message.reply(f"📌 Enter the name for section 1:")
            return
            
        if user_data.get("awaiting_section_name"):
            section_name = message.text.strip()
            if not section_name:
                await message.reply("❌ Section name cannot be empty. Please enter a valid name.")
                return
                
            user_data["sections"].append({"name": section_name})
            del user_data["awaiting_section_name"]
            user_data["awaiting_question_range"] = True
            
            total_questions = len(user_data["questions"])
            await message.reply(f"📌 Enter the question range for '{section_name}' (e.g., 1-5). Maximum: {total_questions}")
            return
            
        if user_data.get("awaiting_question_range"):
            try:
                range_text = message.text.strip()
                start, end = map(int, range_text.split("-"))
                total_questions = len(user_data["questions"])
                
                if start < 1 or end > total_questions or start > end:
                    raise ValueError
                    
                if user_data["last_range_end"] and start != user_data["last_range_end"] + 1:
                    raise ValueError("❌ Invalid range. The next section must start immediately after the previous section.")
            except ValueError as e:
                error_msg = str(e) if isinstance(e, ValueError) and str(e) != "invalid literal for int() with base 10" else "❌ Invalid range. Ensure numbers are within total questions and properly formatted (e.g., 1-5)."
                await message.reply(error_msg)
                return
                
            user_data["sections"][-1]["question_range"] = (start, end)
            del user_data["awaiting_question_range"]
            user_data["last_range_end"] = end
            user_data["awaiting_section_timer"] = True
            
            await message.reply(f"⏳ Enter the timer for this section (greater than 10 sec).")
            return
            
        if user_data.get("awaiting_section_timer"):
            try:
                timer = int(message.text.strip())
                if timer <= 10:
                    raise ValueError
            except ValueError:
                await message.reply("❌ Invalid timer. Enter a value greater than 10 seconds.")
                return
                
            user_data["sections"][-1]["timer"] = timer
            del user_data["awaiting_section_timer"]
            
            if len(user_data["sections"]) < user_data["section_count"]:
                user_data["current_section"] += 1
                await message.reply(f"📌 Enter the name for section {user_data['current_section']}:")
                user_data["awaiting_section_name"] = True
            else:
                # All sections done → now pick timer via inline buttons
                await message.reply(
                    "⏰ **Select Quiz Timer:**\n_Time limit per question_",
                    reply_markup=_timer_keyboard()
                )
            return
            
        if user_data.get("awaiting_negative_marking"):
            try:
                input_text = message.text.strip()
                if input_text.isdigit():
                    negative_marking = int(input_text)
                else:
                    negative_marking = float(fractions.Fraction(input_text)) if "/" in input_text else float(input_text)
                    
                if negative_marking < 0 or negative_marking >= 1:
                    raise ValueError
            except ValueError:
                await message.reply("❌ Invalid negative marking value. Please enter a value between 0 and less than 1 (e.g., 1/3, 0.25).")
                return
                
            user_quiz_data[user_id]["negative_marking"] = negative_marking
            del user_quiz_data[user_id]["awaiting_negative_marking"]
            await message.reply(
                f"📝 Negative marking set to **{negative_marking:.2f}**\n\n"
                "🔀 **Shuffle Questions?**\n"
                "_Randomise question order each time the quiz starts_",
                reply_markup=_shuffq_keyboard()
            )
            return

        # awaiting_shuffle_questions → now handled by handle_create_callback (cr|shuffq|*)
        # awaiting_shuffle_options  → now handled by handle_create_callback (cr|shuffo|*)

        if user_data.get("awaiting_promo"):
            promo_text = message.text.strip()
            if promo_text.lower() == "no":
                user_quiz_data[user_id]["promo"] = None
            else:
                user_quiz_data[user_id]["promo"] = promo_text
            del user_quiz_data[user_id]["awaiting_promo"]
            await message.reply(
                "🔗 Promo saved.\n\n"
                "💰 **Select Quiz Type:**",
                reply_markup=_type_keyboard()
            )
            return

        # awaiting_type → now handled by handle_create_callback (cr|type|*) → _finalize_and_save_quiz
            
        if "rojgarwithankit.co.in" in message.text and "/test-series/" in message.text:
            if BOT_GROUP:
                await handle_rojgar_link(client, message, BOT_GROUP, user_quiz_data)
            else:
                await message.reply_text("⚠️ BOT_GROUP not configured. Set BOT_GROUP env var to enable rojgarwithankit imports.")
            return
            

        questions_blocks = message.text.split("\n\n")
        reply_message = message.reply_to_message
        reply_text = reply_message.text if reply_message and reply_message.text else None
        
        for block in questions_blocks:
            lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
            if not lines:
                continue
            lines = _sanitize_input_lines(lines)

            question = ""
            options = []
            correct_option_id = None
            explanation = None
            file_id = None

            if reply_message and reply_message.photo:
                if BOT_GROUP:
                    copied_message = await client.copy_message(
                        chat_id=BOT_GROUP,
                        from_chat_id=reply_message.chat.id,
                        message_id=reply_message.id,
                    )
                    file_id = copied_message.photo.file_id
                else:
                    file_id = reply_message.photo.file_id

            options_marker_idx = None
            explanation_idx = None
            for idx, line in enumerate(lines):
                if line.lower() in ["options", "options:", "option", "option:", "👉 Choose Correct Option"]:
                    options_marker_idx = idx
                elif line.startswith("Ex:") or line.startswith("Explanation:"):
                    explanation_idx = idx
                    break

            if options_marker_idx is not None:
                question = "\n".join(lines[:options_marker_idx]).strip()
                start_idx = options_marker_idx + 1
                end_idx = explanation_idx if explanation_idx else len(lines)
                for line in lines[start_idx:end_idx]:
                    cleaned = line
                    if len(line) > 2 and line[0].isalnum() and line[1] in ['.', ')', ':']:
                        cleaned = line[2:].strip()
                    elif len(line) > 3 and line[0].isalnum() and line[1] == line[2] and line[1] in ['.', ')']:
                        cleaned = line[3:].strip()
                    if "✅" in cleaned:
                        correct_option_id = len(options)
                        options.append(cleaned.replace("✅", "").strip())
                    else:
                        options.append(cleaned)
                if explanation_idx:
                    explanation = lines[explanation_idx]
                    if explanation.startswith("Ex:"):
                        explanation = _strip_promo_suffix(explanation[3:].strip())
                    elif explanation.startswith("Explanation:"):
                        explanation = _strip_promo_suffix(explanation[12:].strip())
            else:
                question, options, correct_option_id, explanation = _parse_inline_question(lines)

            if not question or len(options) < 2 or correct_option_id is None:
                await message.reply("❌ Invalid question format in one of the questions. Please follow the correct format.")
                return
                
            user_quiz_data[user_id]["questions"].append({
                "question": question,
                "options": options,
                "correct_option_id": correct_option_id,
                "explanation": explanation,
                "file_id": file_id,
                "reply_text": reply_text
            })
            
        total = len(user_quiz_data[user_id]["questions"])
        if total > 100:
            await message.reply(f"✅ Reached {total} soon getting 200 it is advised to stop here...")
            return
        await message.reply(f"✅ {total} Questions saved! Send the next question set, .txt or quiz poll or type /done when finished or /cancel to cancel")

@app.on_message(filters.private & filters.reply)
async def handle_creator_reply(client, message):
    if not message.reply_to_message or not message.reply_to_message.caption:

        return

    caption_lines = message.reply_to_message.caption.split("\n")
    
    student_id_line = next((line for line in caption_lines if "🆔 Student ID:" in line), None)
    student_name_line = next((line for line in caption_lines if "👨‍🎓 Student Name:" in line), None)
    assignment_id_line = next((line for line in caption_lines if "🔖 Assignment ID:" in line), None)

    if not student_id_line:

        return

    student_id = int(student_id_line.split(":")[1].strip())  # Extract student ID
    student_name = student_name_line.split(":")[1].strip() if student_name_line else "Student"

    await client.send_message(
        student_id,
        f"Hello {student_name}, you got creator's reply fro assignment ID : `{assignment_id_line}`\n\n{message.text}"
    )

    await message.reply_text("Your reply has been sent to the student.")

app.run()
