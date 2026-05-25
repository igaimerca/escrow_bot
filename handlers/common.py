"""
Common handlers: /start, /help, terms, support
"""
import asyncio
import logging
import os
from pathlib import Path
import random
import string
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.fsm.context import FSMContext
from database import SessionLocal, User, init_db
from keyboards import main_menu, main_menu_inline
from config import ADMIN_CONTACT_USERNAME, BOT_NAME

logger = logging.getLogger(__name__)
router = Router()
init_db()
WELCOME_VIDEO_PATH = Path(__file__).resolve().parent.parent / "public" / "TrustHold Escrow Bolt.mp4"
WELCOME_VIDEO_FILE_ID = os.getenv("WELCOME_VIDEO_FILE_ID", "")


def build_terms_text() -> str:
    return (
        f"📜 {BOT_NAME} — Terms & Rules\n\n"
        "By using this escrow bot, both buyer and seller agree to the following terms and conditions.\n\n"
        "1. Neutral Middleman\n\n"
        "The escrow bot acts only as a neutral middleman between both parties during transactions.\n\n"
        "2. Deal Confirmation\n\n"
        "Before funds are deposited, both buyer and seller must clearly agree on:\n"
        "• Product/Service\n"
        "• Amount\n"
        "• Payment Method\n"
        "• Delivery Terms\n\n"
        "3. Prohibited Activities\n\n"
        "This bot may NOT be used for:\n"
        "• Fraud or scams\n"
        "• Stolen accounts or stolen goods\n"
        "• Illegal products/services\n"
        "• Money laundering\n"
        "• Any activity that violates laws or Telegram policies\n\n"
        "Any prohibited transaction may be canceled without notice.\n\n"
        "4. Escrow Deposit\n\n"
        "Funds must be fully deposited into escrow before the seller begins delivery.\n\n"
        "5. Release of Funds\n\n"
        "Funds will only be released when:\n"
        "• The buyer confirms delivery, OR\n"
        "• Staff/Admin resolves the dispute\n\n"
        "6. Disputes\n\n"
        "In case of a dispute:\n"
        "• Both parties must provide valid proof/screenshots\n"
        "• Admin decisions are final\n"
        "• Fake or edited evidence may result in a permanent ban\n\n"
        "7. Refund Policy\n\n"
        "Refunds are only issued if:\n"
        "• The seller fails to deliver, OR\n"
        "• Both parties agree to cancel the deal\n\n"
        "Network or transaction fees may not be refundable.\n\n"
        "8. User Responsibility\n\n"
        "Users are responsible for:\n"
        "• Double-checking wallet addresses\n"
        "• Verifying usernames before sending funds\n"
        "• Keeping their Telegram account secure\n\n"
        "The bot is not responsible for losses caused by user mistakes.\n\n"
        "9. Fees\n\n"
        "All escrow fees will be shown before the transaction begins.\n"
        "• $5.00 flat for deals of $100 or less\n"
        "• 5.0% for deals over $100\n\n"
        "10. Right to Refuse Service\n\n"
        "The bot/admin reserves the right to refuse or cancel any transaction suspected of fraud, abuse, or suspicious activity.\n\n"
        "⚠️ Warning:\n"
        "Never send funds outside the escrow bot.\n"
        "Admins will never DM first."
    )


def generate_referral_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_or_create_user(telegram_id: int, username: str, first_name: str):
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    normalized_username = (username or "").strip()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=normalized_username,
            first_name=first_name,
            referral_code=generate_referral_code(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        updated = False
        if normalized_username and user.username != normalized_username:
            user.username = normalized_username
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if updated:
            db.commit()
            db.refresh(user)
    db.close()
    return user


async def send_welcome_video(msg: Message):
    global WELCOME_VIDEO_FILE_ID

    if WELCOME_VIDEO_FILE_ID:
        await asyncio.wait_for(msg.answer_video(video=WELCOME_VIDEO_FILE_ID), timeout=10)
        return

    if not WELCOME_VIDEO_PATH.exists():
        return

    sent_message = await asyncio.wait_for(msg.answer_video(video=FSInputFile(WELCOME_VIDEO_PATH)), timeout=10)
    if sent_message.video:
        WELCOME_VIDEO_FILE_ID = sent_message.video.file_id


@router.message(CommandStart())
async def start_handler(msg: Message, state: FSMContext):
    # If user is mid-flow, don't spam the welcome text; continue the pending step.
    try:
        from handlers.payments import PaymentProofForm, SellerCompletionForm
    except Exception:
        PaymentProofForm = None
        SellerCompletionForm = None

    current_state = await state.get_state()

    if PaymentProofForm and current_state == PaymentProofForm.waiting_proof.state:
        data = await state.get_data()
        txn_id = data.get("txn_id")
        if txn_id:
            await msg.answer(
                f"✅ *Upload Payment Proof*\n\n"
                f"Transaction: `{txn_id}`\n\n"
                "Please send a *screenshot or photo* of your payment confirmation.",
                parse_mode="Markdown",
            )
            return

    if SellerCompletionForm and current_state in (
        SellerCompletionForm.waiting_package.state,
        SellerCompletionForm.waiting_proof.state,
    ):
        data = await state.get_data()
        txn_id = data.get("txn_id")
        if txn_id:
            await msg.answer(
                f"📦 *Completion Submission*\n\n"
                f"Transaction: `{txn_id}`\n\n"
                "Send *ONE message* containing:\n"
                "• completion screenshot/photo\n"
                "• your payout wallet address (in caption, or send wallet as text first)",
                parse_mode="Markdown",
            )
            return

    user = get_or_create_user(
        telegram_id=msg.from_user.id,
        username=msg.from_user.username or "",
        first_name=msg.from_user.first_name or "",
    )

    if user.is_banned:
        await msg.answer("🚫 You have been banned from using this bot.")
        return

    welcome_text = (
        f"🛡️ *Welcome to {BOT_NAME}!*\n\n"
        "We help buyers and sellers complete safe, secure transactions.\n\n"
        "💼 *How it works:*\n"
        "1️⃣ Buyer creates a deal & sends payment\n"
        "2️⃣ Buyer uploads payment proof\n"
        "3️⃣ Admin approves payment\n"
        "4️⃣ Seller submits completion proof + wallet\n"
        "5️⃣ Admin releases funds ✅\n\n"
        "🔒 Funds are protected until the admin releases them.\n\n"
        "Use the menu below to get started:\n\n"
        "💵 *ESCROW FEE*\n"
        "• $5.00 flat for deals of $100 or less\n"
        "• 5.0% for deals over $100\n\n"
        "For full terms and conditions, select 'Terms & Rules' in the menu."
    )
    try:
        await send_welcome_video(msg)
    except Exception:
        logger.exception("Failed to send welcome video")
    await msg.answer(welcome_text, parse_mode="Markdown", reply_markup=main_menu_inline())
    await msg.answer("Quick menu enabled below as well.", reply_markup=main_menu())


@router.message(F.text == "📜 Terms & Rules")
async def terms_handler(msg: Message):
    await msg.answer(build_terms_text(), parse_mode="Markdown")


@router.callback_query(F.data == "menu:terms")
async def terms_handler_callback(cb: CallbackQuery):
    await cb.message.answer(build_terms_text(), parse_mode="Markdown")
    await cb.answer()


@router.message(F.text == "⚖️ Support")
async def support_handler(msg: Message):
    await msg.answer(
        "⚖️ *Support*\n\n"
        "If you need help:\n"
        "• Use /dispute inside a deal\n"
        f"• Contact {ADMIN_CONTACT_USERNAME}\n"
        "• Provide your transaction ID\n\n"
        "⏱️ Response time: within 24 hours.",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "menu:support")
async def support_handler_callback(cb: CallbackQuery):
    await cb.message.answer(
        "⚖️ *Support*\n\n"
        "If you need help:\n"
        "• Use /dispute inside a deal\n"
        f"• Contact {ADMIN_CONTACT_USERNAME}\n"
        "• Provide your transaction ID\n\n"
        "⏱️ Response time: within 24 hours.",
        parse_mode="Markdown",
    )
    await cb.answer()


@router.message(Command("stats"))
async def my_stats_handler(msg: Message):
    db = SessionLocal()
    from database import Deal
    user = db.query(User).filter_by(telegram_id=msg.from_user.id).first()
    if not user:
        await msg.answer("Please /start first.")
        db.close()
        return
    bought = db.query(Deal).filter_by(buyer_id=user.id).count()
    sold = db.query(Deal).filter_by(seller_id=user.id).count()
    completed = db.query(Deal).filter(
        (Deal.buyer_id == user.id) | (Deal.seller_id == user.id),
        Deal.status == "completed"
    ).count()
    db.close()
    await msg.answer(
        f"📊 *Your Stats*\n\n"
        f"🛒 Deals as Buyer: {bought}\n"
        f"💼 Deals as Seller: {sold}\n"
        f"✅ Completed Deals: {completed}\n"
        f"🏷️ Referral Code: `{user.referral_code}`",
        parse_mode="Markdown",
    )
