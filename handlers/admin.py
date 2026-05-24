"""
Admin panel handlers
"""
import logging
from datetime import datetime
from aiogram import Router, F, Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import SessionLocal, User, Deal, Dispute, AdminLog
from config import ADMIN_IDS
from keyboards import deal_actions
from handlers.payments import SellerCompletionForm

router = Router()
logger = logging.getLogger(__name__)


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def log_action(admin_id: int, action: str, target_id: int = None, notes: str = None):
    db = SessionLocal()
    entry = AdminLog(admin_id=admin_id, action=action, target_id=target_id, notes=notes)
    db.add(entry)
    db.commit()
    db.close()


class BroadcastForm(StatesGroup):
    message = State()


# ─── Admin Commands ──────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    db = SessionLocal()
    total_users = db.query(User).count()
    total_deals = db.query(Deal).count()
    open_disputes = db.query(Dispute).filter_by(status="open").count()
    completed = db.query(Deal).filter_by(status="completed").count()
    db.close()

    await msg.answer(
        "🛡️ *Admin Panel*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🤝 Total Deals: {total_deals}\n"
        f"✅ Completed Deals: {completed}\n"
        f"⚠️ Open Disputes: {open_disputes}\n\n"
        "*Commands:*\n"
        "/ban <user_id> — Ban a user\n"
        "/unban <user_id> — Unban a user\n"
        "/lookup <txn_id> — View deal details\n"
        "/broadcast — Send message to all users\n"
        "/disputes — List open disputes\n"
        "/freeze <txn_id> — Freeze a deal\n",
        parse_mode="Markdown",
    )


@router.message(Command("ban"))
async def ban_user(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /ban <telegram_user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await msg.answer("Invalid user ID.")
        return
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=target_id).first()
    if user:
        user.is_banned = True
        db.commit()
        log_action(msg.from_user.id, "ban", target_id)
        await msg.answer(f"✅ User {target_id} has been banned.")
    else:
        await msg.answer("User not found.")
    db.close()


@router.message(Command("unban"))
async def unban_user(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /unban <telegram_user_id>")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await msg.answer("Invalid user ID.")
        return
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=target_id).first()
    if user:
        user.is_banned = False
        db.commit()
        log_action(msg.from_user.id, "unban", target_id)
        await msg.answer(f"✅ User {target_id} has been unbanned.")
    else:
        await msg.answer("User not found.")
    db.close()


@router.message(Command("lookup"))
async def lookup_deal(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /lookup <transaction_id>")
        return
    txn_id = args[1].upper()
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if not deal:
        await msg.answer("Deal not found.")
        db.close()
        return
    buyer = db.query(User).filter_by(id=deal.buyer_id).first()
    seller = db.query(User).filter_by(id=deal.seller_id).first()
    db.close()
    await msg.answer(
        f"🔍 *Deal Lookup*\n\n"
        f"🔖 ID: `{deal.transaction_id}`\n"
        f"💰 Amount: {deal.amount} {deal.currency}\n"
        f"📝 {deal.description}\n"
        f"💳 Payment: {deal.payment_method}\n"
        f"📌 Status: {deal.status}\n"
        f"👤 Buyer: @{buyer.username if buyer else '?'}\n"
        f"👤 Seller: @{seller.username if seller else '?'}\n"
        f"📅 Created: {deal.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"💸 Fee: {deal.fee_amount} {deal.currency}",
        parse_mode="Markdown",
    )


@router.message(Command("freeze"))
async def freeze_deal(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /freeze <transaction_id>")
        return
    txn_id = args[1].upper()
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if deal:
        deal.status = "disputed"
        db.commit()
        log_action(msg.from_user.id, "freeze", notes=txn_id)
        await msg.answer(f"🔒 Deal `{txn_id}` has been frozen.", parse_mode="Markdown")
    else:
        await msg.answer("Deal not found.")
    db.close()


@router.message(Command("disputes"))
async def list_disputes(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    db = SessionLocal()
    disputes = db.query(Dispute).filter_by(status="open").all()
    db.close()
    if not disputes:
        await msg.answer("✅ No open disputes.")
        return
    lines = [f"⚠️ *Open Disputes ({len(disputes)}):*\n"]
    for d in disputes:
        lines.append(f"• Dispute #{d.id} — Deal ID {d.deal_id} | {d.reason[:50]}...")
    await msg.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("broadcast"))
async def broadcast_prompt(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer("📢 Send the message you want to broadcast to ALL users:")
    await state.set_state(BroadcastForm.message)


@router.message(BroadcastForm.message)
async def do_broadcast(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    db = SessionLocal()
    users = db.query(User).filter_by(is_banned=False).all()
    db.close()

    sent = 0
    for user in users:
        try:
            await bot.send_message(user.telegram_id, f"📢 *Announcement:*\n\n{msg.text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            pass

    log_action(msg.from_user.id, "broadcast", notes=f"Sent to {sent} users")
    await msg.answer(f"✅ Broadcast sent to {sent} users.")


# ─── Admin Callbacks ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_verify:"))
async def admin_verify_payment(cb: CallbackQuery, bot: Bot, dispatcher: Dispatcher):
    if not is_admin(cb.from_user.id):
        await cb.answer("Unauthorized.", show_alert=True)
        return
    txn_id = cb.data.split(":")[1]
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if deal:
        if not deal.payment_proof:
            db.close()
            await cb.answer("No payment proof found for this deal.", show_alert=True)
            return
        deal.status = "funds_secured"
        db.commit()
        buyer = db.query(User).filter_by(id=deal.buyer_id).first()
        seller = db.query(User).filter_by(id=deal.seller_id).first()
        buyer_name = "Unknown buyer"
        if buyer:
            buyer_name = f"@{buyer.username}" if buyer.username else (buyer.first_name or "buyer")
            try:
                await bot.send_message(
                    buyer.telegram_id,
                    f"✅ *Payment Approved*\n\n"
                    f"Your payment for deal `{txn_id}` has been verified.\n"
                    "The seller has been notified to proceed.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        if seller:
            try:
                await bot.send_message(
                    seller.telegram_id,
                    f"✅ *Payment Approved*\n\n"
                    f"{buyer_name} payment for deal `{txn_id}` has been verified.\n"
                    f"💰 Amount: {deal.amount} {deal.currency}\n\n"
                    "*Next step (Seller):*\n"
                    "1) Deliver the service/product\n"
                    "2) When completed, send *ONE message* here containing:\n"
                    "   • a screenshot/photo proof that the service was done\n"
                    "   • your payout wallet address (put it in the photo caption, or send as text first)\n\n"
                    "After the admin receives this, the admin will *release the funds* to you.",
                    parse_mode="Markdown",
                    reply_markup=deal_actions(txn_id, "seller"),
                )
                seller_state = await dispatcher.fsm.get_context(
                    bot=bot,
                    chat_id=seller.telegram_id,
                    user_id=seller.telegram_id,
                )
                await seller_state.update_data(txn_id=txn_id)
                await seller_state.set_state(SellerCompletionForm.waiting_package)
                logger.info(
                    "Seller completion flow armed: txn_id=%s seller_telegram_id=%s state=%s",
                    txn_id,
                    seller.telegram_id,
                    await seller_state.get_state(),
                )
            except Exception:
                pass
        log_action(cb.from_user.id, "verify_payment", notes=txn_id)
    db.close()
    await cb.answer("Payment verified ✅", show_alert=True)


@router.callback_query(F.data.startswith("admin_buyer:"))
async def admin_resolve_buyer(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        await cb.answer("Unauthorized.", show_alert=True)
        return
    txn_id = cb.data.split(":")[1]
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if deal and deal.dispute:
        deal.dispute.status = "resolved_buyer"
        deal.dispute.resolved_at = datetime.utcnow()
        deal.status = "cancelled"
        db.commit()
        buyer = db.query(User).filter_by(id=deal.buyer_id).first()
        if buyer:
            try:
                await bot.send_message(buyer.telegram_id, f"⚖️ Dispute on `{txn_id}` resolved in *your favor*.", parse_mode="Markdown")
            except Exception:
                pass
        log_action(cb.from_user.id, "resolve_buyer", notes=txn_id)
    db.close()
    await cb.answer("Resolved: Buyer wins", show_alert=True)


@router.callback_query(F.data.startswith("admin_seller:"))
async def admin_resolve_seller(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        await cb.answer("Unauthorized.", show_alert=True)
        return
    txn_id = cb.data.split(":")[1]
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if deal and deal.dispute:
        deal.dispute.status = "resolved_seller"
        deal.dispute.resolved_at = datetime.utcnow()
        deal.status = "completed"
        db.commit()
        seller = db.query(User).filter_by(id=deal.seller_id).first()
        if seller:
            try:
                await bot.send_message(seller.telegram_id, f"⚖️ Dispute on `{txn_id}` resolved in *your favor*.", parse_mode="Markdown")
            except Exception:
                pass
        log_action(cb.from_user.id, "resolve_seller", notes=txn_id)
    db.close()
    await cb.answer("Resolved: Seller wins", show_alert=True)
