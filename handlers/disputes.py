"""
Dispute system handlers
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import SessionLocal, Deal, User, Dispute
from keyboards import dispute_menu
from config import ADMIN_IDS

router = Router()


class DisputeForm(StatesGroup):
    reason = State()
    txn_id = State()
    evidence = State()


@router.callback_query(F.data.startswith("dispute:"))
async def open_dispute_prompt(cb: CallbackQuery, state: FSMContext):
    txn_id = cb.data.split(":")[1]
    await state.update_data(txn_id=txn_id)
    await state.set_state(DisputeForm.reason)
    await cb.message.answer(
        f"⚠️ *Open a Dispute*\n\nTransaction: `{txn_id}`\n\n"
        "Please describe the reason for the dispute:",
        parse_mode="Markdown",
    )
    await cb.answer()


@router.message(DisputeForm.reason)
async def receive_dispute_reason(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    txn_id = data["txn_id"]

    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    opener = db.query(User).filter_by(telegram_id=msg.from_user.id).first()

    if not deal:
        await msg.answer("❌ Deal not found.")
        db.close()
        return

    existing = db.query(Dispute).filter_by(deal_id=deal.id).first()
    if existing:
        await msg.answer("⚠️ A dispute for this deal already exists.")
        db.close()
        return

    dispute = Dispute(
        deal_id=deal.id,
        opened_by_id=opener.id,
        reason=msg.text.strip(),
        status="open",
    )
    db.add(dispute)
    deal.status = "disputed"
    db.commit()

    # Notify the other party
    other_id = deal.seller_id if deal.buyer_id == opener.id else deal.buyer_id
    other = db.query(User).filter_by(id=other_id).first()
    db.close()

    await msg.answer(
        f"⚠️ *Dispute Opened*\n\n"
        f"Transaction: `{txn_id}`\n"
        "An admin will review and contact both parties.\n\n"
        "You can upload evidence below:",
        parse_mode="Markdown",
        reply_markup=dispute_menu(txn_id),
    )

    if other:
        try:
            await bot.send_message(
                other.telegram_id,
                f"⚠️ *Dispute Opened on Deal* `{txn_id}`\n\n"
                f"Reason: {msg.text.strip()}\n\n"
                "An admin will review shortly.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🚨 *New Dispute!*\n\n"
                f"Transaction: `{txn_id}`\n"
                f"Opened by: @{opener.username}\n"
                f"Reason: {msg.text.strip()}",
                parse_mode="Markdown",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("evidence:"))
async def upload_evidence_prompt(cb: CallbackQuery, state: FSMContext):
    txn_id = cb.data.split(":")[1]
    await state.update_data(txn_id=txn_id)
    await state.set_state(DisputeForm.evidence)
    await cb.message.answer(
        "📎 *Upload Evidence*\n\nSend a photo/screenshot as evidence for your dispute.",
        parse_mode="Markdown",
    )
    await cb.answer()


@router.message(DisputeForm.evidence, F.photo)
async def receive_evidence(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    txn_id = data["txn_id"]
    await state.clear()

    file_id = msg.photo[-1].file_id
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if deal and deal.dispute:
        prev = deal.dispute.evidence or ""
        deal.dispute.evidence = (prev + "," + file_id).strip(",")
        db.commit()
    db.close()

    await msg.answer("✅ Evidence uploaded successfully. Admin will review it.")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo=file_id,
                caption=f"📎 *New Evidence* for dispute on `{txn_id}`",
                parse_mode="Markdown",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("drop_dispute:"))
async def drop_dispute(cb: CallbackQuery, bot: Bot):
    txn_id = cb.data.split(":")[1]
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    if deal and deal.dispute and deal.dispute.status == "open":
        deal.dispute.status = "cancelled"
        deal.status = "in_progress"
        db.commit()
    db.close()
    await cb.message.answer(f"✅ Dispute on `{txn_id}` has been dropped.", parse_mode="Markdown")
    await cb.answer()
