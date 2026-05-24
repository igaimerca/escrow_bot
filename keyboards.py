"""
Inline and Reply keyboards for the bot
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤝 Start Deal"), KeyboardButton(text="📋 My Transactions")],
            [KeyboardButton(text="⚖️ Support"), KeyboardButton(text="📜 Terms & Rules")],
        ],
        resize_keyboard=True,
    )


def main_menu_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤝 Start Deal", callback_data="menu:start_deal")],
        [InlineKeyboardButton(text="📋 My Transactions", callback_data="menu:transactions")],
        [InlineKeyboardButton(text="⚖️ Support", callback_data="menu:support")],
        [InlineKeyboardButton(text="📜 Terms & Rules", callback_data="menu:terms")],
    ])


def deal_actions(transaction_id: str, role: str, phase: str = "default") -> InlineKeyboardMarkup:
    buttons = []
    if role == "buyer":
        if phase != "post_delivery":
            buttons.append([InlineKeyboardButton(text="✅ I Have Paid", callback_data=f"pay:{transaction_id}")])
        buttons.append([InlineKeyboardButton(text="⚠️ Open Dispute", callback_data=f"dispute:{transaction_id}")])
    elif role == "seller":
        buttons.append([InlineKeyboardButton(text="⚠️ Open Dispute", callback_data=f"dispute:{transaction_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Cancel Deal", callback_data=f"cancel:{transaction_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟠 BTC", callback_data="pm:BTC")],
        [InlineKeyboardButton(text="🟢 USDT (ERC20)", callback_data="pm:USDT_ERC20")],
        [InlineKeyboardButton(text="🔵 ETH", callback_data="pm:ETH")],
    ])


def currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USD", callback_data="cur:USD")],
        [InlineKeyboardButton(text="💶 EUR", callback_data="cur:EUR")],
        [InlineKeyboardButton(text="🪙 USDT", callback_data="cur:USDT")],
    ])


def admin_payment_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve Payment", callback_data=f"admin_verify:{transaction_id}")]
    ])


def admin_release_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Release Funds", callback_data=f"admin_release:{transaction_id}")]
    ])


def admin_deal_actions(transaction_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Verify Payment", callback_data=f"admin_verify:{transaction_id}"),
            InlineKeyboardButton(text="🔒 Freeze Deal", callback_data=f"admin_freeze:{transaction_id}"),
        ],
        [
            InlineKeyboardButton(text="👤 Buyer Wins", callback_data=f"admin_buyer:{transaction_id}"),
            InlineKeyboardButton(text="👤 Seller Wins", callback_data=f"admin_seller:{transaction_id}"),
        ],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
    ])


def confirm_cancel(transaction_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Yes, Cancel", callback_data=f"confirm_cancel:{transaction_id}"),
            InlineKeyboardButton(text="No, Keep", callback_data=f"keep:{transaction_id}"),
        ]
    ])


def dispute_menu(transaction_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Upload Evidence", callback_data=f"evidence:{transaction_id}")],
        [InlineKeyboardButton(text="🏳️ Drop Dispute", callback_data=f"drop_dispute:{transaction_id}")],
    ])
