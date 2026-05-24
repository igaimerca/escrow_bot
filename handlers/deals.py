"""
Deal creation & listing handlers
"""
import random
import string
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy import func
from database import SessionLocal, User, Deal
from keyboards import currency_keyboard, deal_actions, confirm_cancel, payment_method_keyboard
from config import ESCROW_FEE_PERCENT

router = Router()
PAYMENT_METHODS = {
    "BTC": {
        "label": "BTC",
        "emoji": "🟠",
        "wallet": "bc1q89tjz2q6trppwjqf8t6lxs0acaz0fzwvpzs85s",
    },
    "USDT_ERC20": {
        "label": "USDT (ERC20)",
        "emoji": "🟢",
        "wallet": "0x0506d23efca7eecc83015e663512f59a7c08e9b2",
    },
    "ETH": {
        "label": "ETH",
        "emoji": "🔵",
        "wallet": "0x0506d23efca7eecc83015e663512f59a7c08e9b2",
    },
}


class DealForm(StatesGroup):
    seller_username = State()
    amount = State()
    currency = State()
    description = State()
    payment_method = State()


def gen_txn_id():
    return "SD-" + "".join(random.choices(string.digits + string.ascii_uppercase, k=8))


def get_user(telegram_id: int):
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    db.close()
    return user


def create_deal_record(
    telegram_id: int,
    payment_method: str,
    wallet_address: str,
    data: dict,
):
    db = SessionLocal()
    buyer = db.query(User).filter_by(telegram_id=telegram_id).first()
    seller = db.query(User).filter(
        func.lower(User.username) == data["seller_username"].lower()
    ).first()
    buyer_username = buyer.username or "buyer"
    seller_telegram_id = seller.telegram_id

    txn_id = gen_txn_id()
    deal = Deal(
        transaction_id=txn_id,
        buyer_id=buyer.id,
        seller_id=seller.id,
        amount=data["amount"],
        currency=data["currency"],
        description=data["description"],
        payment_method=payment_method,
        fee_amount=data["fee"],
        status="waiting_payment",
    )
    db.add(deal)
    db.commit()
    db.close()

    wallet_message = f"`{wallet_address}`"

    summary = (
        f"🔖 Transaction ID: `{txn_id}`\n"
        f"💳 Payment Method: *{payment_method}*\n"
        f"💰 Amount: *{data['amount']} {data['currency']}*\n"
        f"📝 Description: {data['description']}\n"
        f"👤 Seller: @{data['seller_username']}\n\n"
        "⚠️ Double check the network before sending funds.\n\n"
        "After payment:\n"
        "1. Send the funds\n"
        "2. Tap `I Have Paid`\n"
        "3. Upload your payment screenshot"
    )

    seller_msg = (
        f"🔔 *New Escrow Deal!*\n\n"
        f"🔖 Transaction ID: `{txn_id}`\n"
        f"💰 Amount: *{data['amount']} {data['currency']}*\n"
        f"📝 {data['description']}\n"
        f"💳 Payment: {payment_method}\n"
        f"👤 Buyer: @{buyer_username}\n\n"
        f"_Wait for buyer to upload payment proof._"
    )

    return seller_telegram_id, txn_id, wallet_message, summary, seller_msg


@router.message(F.text == "🤝 Start Deal")
async def start_deal(msg: Message, state: FSMContext):
    user = get_user(msg.from_user.id)
    if not user:
        await msg.answer("Please /start first.")
        return
    if user.is_banned:
        await msg.answer("🚫 You are banned.")
        return
    await msg.answer(
        "🤝 *Create a New Escrow Deal*\n\n"
        "Step 1/5 — Enter the *seller's Telegram username* (without @):",
        parse_mode="Markdown",
    )
    await state.set_state(DealForm.seller_username)


@router.callback_query(F.data == "menu:start_deal")
async def start_deal_callback(cb: CallbackQuery, state: FSMContext):
    user = get_user(cb.from_user.id)
    if not user:
        await cb.message.answer("Please /start first.")
        await cb.answer()
        return
    if user.is_banned:
        await cb.message.answer("🚫 You are banned.")
        await cb.answer()
        return
    await cb.message.answer(
        "🤝 *Create a New Escrow Deal*\n\n"
        "Step 1/5 — Enter the *seller's Telegram username* (without @):",
        parse_mode="Markdown",
    )
    await state.set_state(DealForm.seller_username)
    await cb.answer()


@router.message(DealForm.seller_username)
async def deal_seller(msg: Message, state: FSMContext):
    username = msg.text.strip().lstrip("@")
    db = SessionLocal()
    seller = db.query(User).filter(func.lower(User.username) == username.lower()).first()
    db.close()
    if not seller:
        await msg.answer(
            f"❌ User @{username} not found or hasn't started the bot.\n"
            "Ask them to start the bot first, then try again."
        )
        return
    if seller.telegram_id == msg.from_user.id:
        await msg.answer("❌ You can't create a deal with yourself.")
        return
    await state.update_data(seller_username=username, seller_telegram_id=seller.telegram_id)
    await msg.answer("Step 2/5 — Enter the *deal amount* (numbers only, e.g. 150):", parse_mode="Markdown")
    await state.set_state(DealForm.amount)


@router.message(DealForm.amount)
async def deal_amount(msg: Message, state: FSMContext):
    try:
        amount = float(msg.text.strip().replace(",", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Invalid amount. Please enter a positive number:")
        return
    fee = round(amount * ESCROW_FEE_PERCENT / 100, 2)
    await state.update_data(amount=amount, fee=fee)
    await msg.answer(
        f"✅ Amount: *${amount}*\n📊 Escrow Fee ({ESCROW_FEE_PERCENT}%): *${fee}*\n\n"
        "Step 3/5 — Choose the *currency*:",
        parse_mode="Markdown",
        reply_markup=currency_keyboard(),
    )
    await state.set_state(DealForm.currency)


@router.callback_query(F.data.startswith("cur:"))
async def deal_currency_callback(cb: CallbackQuery, state: FSMContext):
    if await state.get_state() != DealForm.currency.state:
        await cb.answer()
        return
    currency = cb.data.split("cur:", 1)[1]
    await state.update_data(currency=currency)
    await cb.message.answer("Step 4/5 — Enter a *deal description* (what is being sold/bought):", parse_mode="Markdown")
    await state.set_state(DealForm.description)
    await cb.answer(f"Selected {currency}")


@router.message(DealForm.currency)
async def deal_currency(msg: Message):
    await msg.answer(
        "Please choose the currency using the buttons: *USD*, *EUR*, or *USDT*.",
        parse_mode="Markdown",
        reply_markup=currency_keyboard(),
    )


@router.message(DealForm.description)
async def deal_description(msg: Message, state: FSMContext):
    await state.update_data(description=msg.text.strip())
    await msg.answer(
        "Step 5/5 — Choose the *payment method*:",
        parse_mode="Markdown",
        reply_markup=payment_method_keyboard(),
    )
    await state.set_state(DealForm.payment_method)


@router.callback_query(F.data.startswith("pm:"))
async def deal_payment_method_callback(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if await state.get_state() != DealForm.payment_method.state:
        await cb.answer()
        return
    payment_key = cb.data.split("pm:", 1)[1]
    payment_config = PAYMENT_METHODS.get(payment_key)
    if not payment_config:
        await cb.answer("Invalid payment method.", show_alert=True)
        return
    data = await state.get_data()
    seller_telegram_id, txn_id, wallet_message, summary, seller_msg = create_deal_record(
        cb.from_user.id,
        payment_config["label"],
        payment_config["wallet"],
        data,
    )
    await state.clear()
    await cb.message.answer(wallet_message, parse_mode="Markdown")
    await cb.message.answer(summary, parse_mode="Markdown", reply_markup=deal_actions(txn_id, "buyer"))
    await cb.answer(f"Selected {payment_config['label']}")

    # Notify seller
    try:
        await bot.send_message(seller_telegram_id, seller_msg, parse_mode="Markdown",
                               reply_markup=deal_actions(txn_id, "seller"))
    except Exception:
        pass


@router.message(DealForm.payment_method)
async def deal_payment_method(msg: Message):
    await msg.answer(
        "Please choose a payment method using the buttons: *BTC*, *USDT (ERC20)*, or *ETH*.",
        parse_mode="Markdown",
        reply_markup=payment_method_keyboard(),
    )


@router.message(F.text == "📋 My Transactions")
async def my_transactions(msg: Message):
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=msg.from_user.id).first()
    if not user:
        await msg.answer("Please /start first.")
        db.close()
        return
    deals = db.query(Deal).filter(
        (Deal.buyer_id == user.id) | (Deal.seller_id == user.id)
    ).order_by(Deal.created_at.desc()).limit(10).all()
    db.close()

    if not deals:
        await msg.answer("📋 You have no transactions yet.\nUse *Start Deal* to create one!", parse_mode="Markdown")
        return

    STATUS_EMOJI = {
        "pending": "⏳",
        "waiting_payment": "💳",
        "payment_submitted": "🧾",
        "funds_secured": "🔒",
        "in_progress": "🔄",
        "completed": "✅",
        "cancelled": "❌",
        "disputed": "⚠️",
    }

    lines = ["📋 *Your Last 10 Transactions:*\n"]
    for d in deals:
        emoji = STATUS_EMOJI.get(d.status, "❓")
        role = "Buyer" if d.buyer_id == user.id else "Seller"
        lines.append(f"{emoji} `{d.transaction_id}` — {d.amount} {d.currency} [{role}]")

    await msg.answer("\n".join(lines), parse_mode="Markdown")


@router.callback_query(F.data == "menu:transactions")
async def my_transactions_callback(cb: CallbackQuery):
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=cb.from_user.id).first()
    if not user:
        await cb.message.answer("Please /start first.")
        db.close()
        await cb.answer()
        return
    deals = db.query(Deal).filter(
        (Deal.buyer_id == user.id) | (Deal.seller_id == user.id)
    ).order_by(Deal.created_at.desc()).limit(10).all()
    db.close()

    if not deals:
        await cb.message.answer("📋 You have no transactions yet.\nUse *Start Deal* to create one!", parse_mode="Markdown")
        await cb.answer()
        return

    status_emoji = {
        "pending": "⏳",
        "waiting_payment": "💳",
        "payment_submitted": "🧾",
        "funds_secured": "🔒",
        "in_progress": "🔄",
        "completed": "✅",
        "cancelled": "❌",
        "disputed": "⚠️",
    }

    lines = ["📋 *Your Last 10 Transactions:*\n"]
    for deal in deals:
        emoji = status_emoji.get(deal.status, "❓")
        role = "Buyer" if deal.buyer_id == user.id else "Seller"
        lines.append(f"{emoji} `{deal.transaction_id}` — {deal.amount} {deal.currency} [{role}]")

    await cb.message.answer("\n".join(lines), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_deal_prompt(cb: CallbackQuery):
    txn_id = cb.data.split(":")[1]
    await cb.message.answer(
        f"❓ Are you sure you want to cancel deal `{txn_id}`?",
        parse_mode="Markdown",
        reply_markup=confirm_cancel(txn_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_cancel:"))
async def confirm_cancel_deal(cb: CallbackQuery, bot: Bot):
    txn_id = cb.data.split(":")[1]
    db = SessionLocal()
    deal = db.query(Deal).filter_by(transaction_id=txn_id).first()
    user = db.query(User).filter_by(telegram_id=cb.from_user.id).first()
    if deal and deal.status not in ("completed", "cancelled", "disputed"):
        deal.status = "cancelled"
        db.commit()
        # Notify other party
        other_id = deal.seller_id if deal.buyer_id == user.id else deal.buyer_id
        other = db.query(User).filter_by(id=other_id).first()
        if other:
            try:
                await bot.send_message(
                    other.telegram_id,
                    f"❌ Deal `{txn_id}` has been *cancelled* by the other party.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
    db.close()
    await cb.message.answer(f"✅ Deal `{txn_id}` has been cancelled.", parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data.startswith("keep:"))
async def keep_deal(cb: CallbackQuery):
    await cb.message.answer("✅ Deal kept active.")
    await cb.answer()
