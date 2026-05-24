"""
Payment proof upload & fund release handlers
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import SessionLocal, Deal, User
from keyboards import admin_payment_actions, admin_release_actions, deal_actions
from config import ADMIN_IDS, BOT_NAME

router = Router()
logger = logging.getLogger(__name__)


class PaymentProofForm(StatesGroup):
    waiting_proof = State()
    txn_id = State()


class SellerCompletionForm(StatesGroup):
    """Collect seller's completion proof + payout wallet after admin approves payment."""

    waiting_package = State()  # photo with caption containing wallet
    waiting_proof = State()  # photo after wallet text was provided


def _display_name(user: User | None, fallback: str) -> str:
    if not user:
        return fallback
    if user.username:
        return f"@{user.username}"
    return user.first_name or fallback


def _completion_media_file_id(msg: Message) -> str | None:
    if msg.photo:
        return msg.photo[-1].file_id
    if msg.document:
        return msg.document.file_id
    return None


def _message_text_or_caption(msg: Message) -> str:
    return (msg.caption or msg.text or "").strip()


def _get_active_seller_completion_deal(seller: User) -> Deal | None:
    db = SessionLocal()
    try:
        return (
            db.query(Deal)
            .filter(
                Deal.seller_id == seller.id,
                Deal.status.in_(("funds_secured", "in_progress")),
            )
            .order_by(Deal.updated_at.desc())
            .first()
        )
    finally:
        db.close()


async def forward_completion_package_to_admins(
    bot: Bot,
    txn_id: str,
    seller: User,
    deal: Deal,
    photo_file_id: str,
    media_kind: str,
    wallet_text: str,
):
    seller_name = _display_name(seller, "seller")
    wallet_text = wallet_text.strip()

    for admin_id in ADMIN_IDS:
        try:
            if media_kind == "document":
                await bot.send_document(
                    admin_id,
                    document=photo_file_id,
                    caption=(
                        f"📦 *Completion Package Received*\n\n"
                        f"Transaction: `{txn_id}`\n"
                        f"Seller: {seller_name}\n"
                        f"Amount: {deal.amount} {deal.currency}\n\n"
                        "Completion document received."
                    ),
                    parse_mode="Markdown",
                )
            else:
                await bot.send_photo(
                    admin_id,
                    photo=photo_file_id,
                    caption=(
                        f"📦 *Completion Package Received*\n\n"
                        f"Transaction: `{txn_id}`\n"
                        f"Seller: {seller_name}\n"
                        f"Amount: {deal.amount} {deal.currency}\n\n"
                        "Completion screenshot received."
                    ),
                    parse_mode="Markdown",
                )
            await bot.send_message(
                admin_id,
                f"🏦 *Seller Wallet Address*\n\n"
                f"Transaction: `{txn_id}`\n"
                f"Seller: {seller_name}\n"
                f"Amount: {deal.amount} {deal.currency}\n\n"
                f"Wallet: `{wallet_text}`\n\n"
                "If everything checks out, release the funds to the seller.",
                parse_mode="Markdown",
                reply_markup=admin_release_actions(txn_id),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("pay:"))
async def upload_payment_prompt(cb: CallbackQuery, state: FSMContext):
    txn_id = cb.data.split(":")[1]
    await state.update_data(txn_id=txn_id)
    await state.set_state(PaymentProofForm.waiting_proof)
    await cb.message.answer(
        f"✅ *Upload Payment Proof*\n\n"
        f"Transaction: `{txn_id}`\n\n"
        "Please send a *screenshot or photo* of your payment confirmation.",
        parse_mode="Markdown",
    )
    await cb.answer()


@router.message(PaymentProofForm.waiting_proof, F.photo)
async def receive_payment_proof(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    txn_id = data.get("txn_id")
    await state.clear()

    photo_file_id = msg.photo[-1].file_id

    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if not deal:
        await msg.answer("❌ Deal not found.")
        db.close()
        return

    deal.payment_proof = photo_file_id
    deal.status = "payment_submitted"
    db.commit()

    # Notify seller
    seller = db.query(User).filter_by(id=deal.seller_id).first()
    db.close()

    await msg.answer(
        f"✅ *Payment proof submitted!*\n\n"
        f"Transaction `{txn_id}` status: 🧾 *Awaiting Admin Approval*\n\n"
        "An admin will confirm the payment, then ask the seller for their completion proof + wallet.\n"
        "After that, the admin will release the funds.",
        parse_mode="Markdown",
    )

    # Notify seller
    if seller:
        try:
            await bot.send_photo(
                seller.telegram_id,
                photo=photo_file_id,
                caption=(
                    f"🔔 *Payment Proof Submitted*\n\n"
                    f"Transaction: `{txn_id}`\n"
                    f"💰 Amount: {deal.amount} {deal.currency}\n\n"
                    "The buyer has submitted payment proof.\n"
                    "Please wait for *admin approval* before proceeding.\n\n"
                    "After admin approval, you will be asked to send:\n"
                    "• a screenshot/photo proving the service was completed\n"
                    "• your payout wallet address"
                ),
                parse_mode="Markdown",
                reply_markup=deal_actions(txn_id, "seller"),
            )
        except Exception:
            pass

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo=photo_file_id,
                caption=(
                    f"🔔 *Payment Proof Submitted*\n\n"
                    f"Transaction: `{txn_id}`\n"
                    f"Amount: {deal.amount} {deal.currency}\n"
                    f"Verify and approve."
                ),
                parse_mode="Markdown",
                reply_markup=admin_payment_actions(txn_id),
            )
        except Exception:
            pass


@router.message(PaymentProofForm.waiting_proof)
async def proof_not_photo(msg: Message):
    await msg.answer("❌ Please send a *payment screenshot or photo* as proof.", parse_mode="Markdown")


@router.message(SellerCompletionForm.waiting_package, F.photo | F.document)
async def receive_completion_package_photo(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    txn_id = data.get("txn_id")
    if not txn_id:
        await msg.answer(
            "❌ Missing transaction context. Please ask the admin to verify the payment again.",
            parse_mode="Markdown",
        )
        await state.clear()
        return

    wallet_text = _message_text_or_caption(msg)
    if not wallet_text:
        await msg.answer(
            "❌ Please resend the *completion screenshot/photo* with your *wallet address* in the caption.\n\n"
            "Example caption:\n`0xABC...`",
            parse_mode="Markdown",
        )
        return

    media_file_id = _completion_media_file_id(msg)
    if not media_file_id:
        await msg.answer(
            "❌ Please send the completion proof as a photo or document.",
            parse_mode="Markdown",
        )
        return
    media_kind = "document" if msg.document else "photo"

    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    seller = db.query(User).filter_by(telegram_id=msg.from_user.id).first()

    if not deal or not seller or deal.seller_id != seller.id:
        db.close()
        await state.clear()
        await msg.answer("❌ Deal not found or unauthorized.", parse_mode="Markdown")
        return

    if deal.status != "funds_secured":
        db.close()
        await msg.answer(
            f"❌ This deal is not ready for completion submission (status: `{deal.status}`).",
            parse_mode="Markdown",
        )
        return

    deal.status = "in_progress"
    db.commit()
    buyer = db.query(User).filter_by(id=deal.buyer_id).first()
    db.close()

    await forward_completion_package_to_admins(
        bot=bot,
        txn_id=txn_id,
        seller=seller,
        deal=deal,
        photo_file_id=media_file_id,
        media_kind=media_kind,
        wallet_text=wallet_text,
    )
    await state.clear()

    await msg.answer(
        "✅ *Received!* Your completion proof + wallet were sent to the admin.\n"
        "Admin will review and release the funds.",
        parse_mode="Markdown",
        reply_markup=deal_actions(txn_id, "seller"),
    )

    if buyer:
        try:
            await bot.send_message(
                buyer.telegram_id,
                f"🔔 *Seller submitted completion details*\n\n"
                f"Transaction `{txn_id}`\n\n"
                "Admin will review and release the funds.",
                parse_mode="Markdown",
            )
        except Exception:
            pass


@router.message(SellerCompletionForm.waiting_package, F.text)
async def receive_completion_wallet_text(msg: Message, state: FSMContext):
    wallet_text = _message_text_or_caption(msg)
    if not wallet_text:
        await msg.answer("❌ Please send your wallet address as text.", parse_mode="Markdown")
        return

    await state.update_data(wallet_text=wallet_text)
    await state.set_state(SellerCompletionForm.waiting_proof)
    await msg.answer(
        "✅ Wallet received. Now send the *completion screenshot/photo*.",
        parse_mode="Markdown",
    )


@router.message(SellerCompletionForm.waiting_package)
async def completion_package_fallback(msg: Message):
    await msg.answer(
        "Please send a *completion screenshot/photo* with your *wallet address* in the caption,\n"
        "or send your wallet as text first.",
        parse_mode="Markdown",
    )


@router.message(SellerCompletionForm.waiting_proof, F.photo | F.document)
async def receive_completion_photo_after_wallet(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    txn_id = data.get("txn_id")
    wallet_text = (data.get("wallet_text") or "").strip()

    if not txn_id or not wallet_text:
        await msg.answer(
            "❌ Missing transaction context. Please ask the admin to verify the payment again.",
            parse_mode="Markdown",
        )
        await state.clear()
        return

    media_file_id = _completion_media_file_id(msg)
    if not media_file_id:
        await msg.answer(
            "❌ Please send the completion proof as a photo or document.",
            parse_mode="Markdown",
        )
        return
    media_kind = "document" if msg.document else "photo"

    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    seller = db.query(User).filter_by(telegram_id=msg.from_user.id).first()

    if not deal or not seller or deal.seller_id != seller.id:
        db.close()
        await state.clear()
        await msg.answer("❌ Deal not found or unauthorized.", parse_mode="Markdown")
        return

    if deal.status != "funds_secured":
        db.close()
        await msg.answer(
            f"❌ This deal is not ready for completion submission (status: `{deal.status}`).",
            parse_mode="Markdown",
        )
        return

    deal.status = "in_progress"
    db.commit()
    buyer = db.query(User).filter_by(id=deal.buyer_id).first()
    db.close()

    await forward_completion_package_to_admins(
        bot=bot,
        txn_id=txn_id,
        seller=seller,
        deal=deal,
        photo_file_id=media_file_id,
        media_kind=media_kind,
        wallet_text=wallet_text,
    )
    await state.clear()

    await msg.answer(
        "✅ *Received!* Your completion proof + wallet were sent to the admin.\n"
        "Admin will review and release the funds.",
        parse_mode="Markdown",
        reply_markup=deal_actions(txn_id, "seller"),
    )

    if buyer:
        try:
            await bot.send_message(
                buyer.telegram_id,
                f"🔔 *Seller submitted completion details*\n\n"
                f"Transaction `{txn_id}`\n\n"
                "Admin will review and release the funds.",
                parse_mode="Markdown",
            )
        except Exception:
            pass


@router.message(SellerCompletionForm.waiting_proof)
async def completion_proof_fallback(msg: Message):
    await msg.answer("❌ Please send the completion screenshot/photo.", parse_mode="Markdown")


@router.message(F.photo | F.document)
async def seller_completion_no_state_fallback(msg: Message, state: FSMContext, bot: Bot):
    if await state.get_state():
        return

    seller_db = SessionLocal()
    try:
        seller = seller_db.query(User).filter_by(telegram_id=msg.from_user.id).first()
    finally:
        seller_db.close()

    if not seller:
        return

    deal = _get_active_seller_completion_deal(seller)
    if not deal:
        return

    wallet_text = _message_text_or_caption(msg)
    if not wallet_text:
        logger.info(
            "Seller completion no-state skipped: seller=%s txn_id=%s reason=missing_wallet_text content_type=%s",
            seller.telegram_id,
            deal.transaction_id,
            msg.content_type,
        )
        await msg.answer(
            "Send the completion proof with your wallet address in the caption, or send the wallet as text first.",
            parse_mode="Markdown",
        )
        return

    media_file_id = _completion_media_file_id(msg)
    if not media_file_id:
        return

    media_kind = "document" if msg.document else "photo"
    logger.info(
        "Seller completion no-state recovered: seller=%s txn_id=%s content_type=%s media_kind=%s",
        seller.telegram_id,
        deal.transaction_id,
        msg.content_type,
        media_kind,
    )

    db = SessionLocal()
    try:
        deal = db.query(Deal).filter_by(transaction_id=deal.transaction_id).first()
        if not deal or deal.seller_id != seller.id or deal.status not in ("funds_secured", "in_progress"):
            return

        deal.status = "in_progress"
        db.commit()
        buyer = db.query(User).filter_by(id=deal.buyer_id).first()
    finally:
        db.close()

    await forward_completion_package_to_admins(
        bot=bot,
        txn_id=deal.transaction_id,
        seller=seller,
        deal=deal,
        photo_file_id=media_file_id,
        media_kind=media_kind,
        wallet_text=wallet_text,
    )

    await msg.answer(
        "✅ *Received!* Your completion proof + wallet were sent to the admin.\n"
        "Admin will review and release the funds.",
        parse_mode="Markdown",
        reply_markup=deal_actions(deal.transaction_id, "seller"),
    )

    if buyer:
        try:
            await bot.send_message(
                buyer.telegram_id,
                f"🔔 *Seller submitted completion details*\n\n"
                f"Transaction `{deal.transaction_id}`\n\n"
                "Admin will review and release the funds.",
                parse_mode="Markdown",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("admin_release:"))
async def admin_release_funds(cb: CallbackQuery, bot: Bot):
    txn_id = cb.data.split(":")[1]
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Unauthorized.", show_alert=True)
        return

    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if not deal:
        await cb.answer("Deal not found.", show_alert=True)
        db.close()
        return

    if deal.status != "in_progress":
        await cb.answer(f"Cannot release yet — current status: {deal.status}", show_alert=True)
        db.close()
        return

    seller = db.query(User).filter_by(id=deal.seller_id).first()
    buyer = db.query(User).filter_by(id=deal.buyer_id).first()
    seller_telegram_id = seller.telegram_id if seller else None
    buyer_telegram_id = buyer.telegram_id if buyer else None
    amount = deal.amount
    currency = deal.currency
    seller_name = _display_name(seller, "sender")
    buyer_name = _display_name(buyer, "receiver")
    deal.status = "completed"
    db.commit()
    db.close()

    await cb.message.answer(
        f"🎉 *Funds Released by Admin!*\n\n"
        f"Transaction `{txn_id}` is now ✅ *Completed*.",
        parse_mode="Markdown",
    )

    if seller_telegram_id:
        try:
            await bot.send_message(
                seller_telegram_id,
                f"Hello {seller_name},\n\n"
                f"Amount Released by Admin\n\n"
                f"Transaction {txn_id} has been completed.\n"
                f"Amount released: {amount} {currency}\n\n"
                f"Thank you for using {BOT_NAME}!",
            )
        except Exception:
            logger.exception(
                "Failed to send release notification to sender seller_id=%s txn_id=%s",
                seller_telegram_id,
                txn_id,
            )

    if buyer_telegram_id:
        try:
            await bot.send_message(
                buyer_telegram_id,
                f"Hello {buyer_name},\n\n"
                f"Amount Released to Receiver\n\n"
                f"Transaction {txn_id} has been completed by the admin.\n"
                f"Amount released to you: {amount} {currency}\n\n"
                f"Thank you for using {BOT_NAME}!",
            )
        except Exception:
            logger.exception(
                "Failed to send release notification to receiver buyer_id=%s txn_id=%s",
                buyer_telegram_id,
                txn_id,
            )

    await cb.answer("Funds released ✅", show_alert=True)


