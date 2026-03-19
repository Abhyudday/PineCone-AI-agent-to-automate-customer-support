import os
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from pinecone import Pinecone
from pinecone_plugins.assistant.models.chat import Message

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY")

pc = Pinecone(api_key=PINECONE_API_KEY)
assistant = pc.assistant.Assistant(assistant_name="polycop")

KNOWN_PROTOCOLS = {
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange Proxy",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap Universal Router",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2 Router",
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "SushiSwap Router",
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506": "SushiSwap Router (Polygon)",
    "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff": "QuickSwap Router",
    "0xf5b509bb0909a69b1c207e495f687a596c168e12": "QuickSwap V3 Router",
    "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270": "WMATIC",
    "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619": "WETH (Polygon)",
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC (Polygon)",
    "0xc2132d05d31c914a87c6611c10748aeb04b58e8f": "USDT (Polygon)",
    "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063": "DAI (Polygon)",
    "0x45dda9cb7c25131df268515131f647d726f50608": "Aave V3 Pool (Polygon)",
    "0x794a61358d6845594f94dc1db02a252b5b4814ad": "Aave V3 Pool",
    "0xba12222222228d8ba445958a75a0704d566bf2c8": "Balancer Vault",
    "0x3d4e44eb1374240ce5f1b871ab261cd16335b76a": "Curve Router",
}

KNOWN_METHODS = {
    "0xa9059cbb": "transfer",
    "0x23b872dd": "transferFrom",
    "0x095ea7b3": "approve",
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x4a25d94a": "swapTokensForExactETH",
    "0x18cbafe5": "swapExactTokensForETH",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0x5c11d795": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
    "0xb6f9de95": "swapExactETHForTokensSupportingFeeOnTransferTokens",
    "0x791ac947": "swapExactTokensForETHSupportingFeeOnTransferTokens",
    "0x414bf389": "exactInputSingle (Uniswap V3)",
    "0xc04b8d59": "exactInput (Uniswap V3)",
    "0xdb3e2198": "exactOutputSingle (Uniswap V3)",
    "0xf28c0498": "exactOutput (Uniswap V3)",
    "0xe449022e": "uniswapV3Swap (1inch)",
    "0x12aa3caf": "swap (1inch)",
    "0x0502b1c5": "unoswap (1inch)",
    "0x2e95b6c8": "unoswapTo (1inch)",
    "0xd0e30db0": "deposit (wrap ETH)",
    "0x2e1a7d4d": "withdraw (unwrap ETH)",
    "0xe8e33700": "addLiquidity",
    "0xf305d719": "addLiquidityETH",
    "0xbaa2abde": "removeLiquidity",
    "0x02751cec": "removeLiquidityETH",
    "0xe9fad8ee": "exit (staking)",
    "0xa694fc3a": "stake",
    "0x2e17de78": "unstake",
    "0x3d18b912": "getReward",
    "0xe2bbb158": "deposit (farming)",
    "0x441a3e70": "withdraw (farming)",
    "0x1249c58b": "mint",
    "0x42966c68": "burn",
    "0x617ba037": "supply (Aave)",
    "0x69328dec": "withdraw (Aave)",
    "0xa415bcad": "borrow (Aave)",
    "0x573ade81": "repay (Aave)",
}

MODE_PINECONE = "pinecone"
MODE_POLYGONSCAN = "polygonscan"

CHOOSING, PINECONE_INPUT, POLYGONSCAN_INPUT = range(3)


def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🤖 Pinecone Assistant", callback_data=MODE_PINECONE)],
        [InlineKeyboardButton("🔍 Polygonscan TX Decoder", callback_data=MODE_POLYGONSCAN)],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Polycop Bot!*\n\n"
        "Choose an option:\n\n"
        "🤖 *Pinecone Assistant* - Ask questions and get AI-powered responses\n\n"
        "🔍 *Polygonscan TX Decoder* - Decode any Polygon transaction hash and get detailed insights\n",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return CHOOSING


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == MODE_PINECONE:
        context.user_data["mode"] = MODE_PINECONE
        await query.edit_message_text(
            "🤖 *Pinecone Assistant Mode*\n\n"
            "Send me any question and I'll get you an answer from the Polycop assistant.\n\n"
            "Type /menu to go back to the main menu.",
            parse_mode="Markdown",
        )
        return PINECONE_INPUT

    elif query.data == MODE_POLYGONSCAN:
        context.user_data["mode"] = MODE_POLYGONSCAN
        await query.edit_message_text(
            "🔍 *Polygonscan TX Decoder Mode*\n\n"
            "Send me a Polygon transaction hash and I'll decode it for you with detailed insights.\n\n"
            "Example: `0x1234...abcd`\n\n"
            "Type /menu to go back to the main menu.",
            parse_mode="Markdown",
        )
        return POLYGONSCAN_INPUT

    return CHOOSING


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Main Menu*\n\nChoose an option:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown",
    )
    return CHOOSING


async def handle_pinecone_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info(f"Pinecone query: {user_text}")

    await update.message.chat.send_action("typing")

    try:
        msg = Message(content=user_text)
        resp = assistant.chat(messages=[msg])
        reply = resp["message"]["content"]
    except Exception as e:
        logger.error(f"Pinecone error: {e}")
        reply = "❌ Sorry, something went wrong while processing your request."

    await update.message.reply_text(reply)
    return PINECONE_INPUT


def format_wei_to_matic(wei_value: str) -> str:
    try:
        wei = int(wei_value, 16) if wei_value.startswith("0x") else int(wei_value)
        matic = wei / 1e18
        if matic == 0:
            return "0 MATIC"
        elif matic < 0.0001:
            return f"{matic:.10f} MATIC"
        elif matic < 1:
            return f"{matic:.6f} MATIC"
        else:
            return f"{matic:,.4f} MATIC"
    except:
        return wei_value


def format_gas_price(wei_value: str) -> str:
    try:
        wei = int(wei_value, 16) if wei_value.startswith("0x") else int(wei_value)
        gwei = wei / 1e9
        return f"{gwei:.2f} Gwei"
    except:
        return wei_value


def identify_protocol(address: str) -> str:
    addr_lower = address.lower()
    if addr_lower in KNOWN_PROTOCOLS:
        return KNOWN_PROTOCOLS[addr_lower]
    return None


def decode_method(input_data: str) -> str:
    if not input_data or input_data == "0x":
        return "Native Transfer (no contract interaction)"
    
    method_id = input_data[:10].lower()
    if method_id in KNOWN_METHODS:
        return KNOWN_METHODS[method_id]
    return f"Unknown Method ({method_id})"


async def fetch_tx_details(tx_hash: str) -> dict:
    async with httpx.AsyncClient() as client:
        tx_response = await client.get(
            "https://api.polygonscan.com/api",
            params={
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": POLYGONSCAN_API_KEY,
            },
        )
        tx_data = tx_response.json()
        logger.info(f"TX API response: {tx_data}")
        tx_result = tx_data.get("result")
        if tx_result is None or not isinstance(tx_result, dict):
            tx_result = {}

        receipt_response = await client.get(
            "https://api.polygonscan.com/api",
            params={
                "module": "proxy",
                "action": "eth_getTransactionReceipt",
                "txhash": tx_hash,
                "apikey": POLYGONSCAN_API_KEY,
            },
        )
        receipt_data = receipt_response.json()
        receipt_result = receipt_data.get("result", {})
        if not isinstance(receipt_result, dict):
            receipt_result = {}

        internal_response = await client.get(
            "https://api.polygonscan.com/api",
            params={
                "module": "account",
                "action": "txlistinternal",
                "txhash": tx_hash,
                "apikey": POLYGONSCAN_API_KEY,
            },
        )
        internal_data = internal_response.json()
        internal_result = internal_data.get("result", [])
        if not isinstance(internal_result, list):
            internal_result = []

        from_addr = tx_result.get("from", "")
        token_result = []
        if from_addr:
            token_response = await client.get(
                "https://api.polygonscan.com/api",
                params={
                    "module": "account",
                    "action": "tokentx",
                    "address": from_addr,
                    "startblock": 0,
                    "endblock": 99999999,
                    "page": 1,
                    "offset": 100,
                    "sort": "desc",
                    "apikey": POLYGONSCAN_API_KEY,
                },
            )
            token_data = token_response.json()
            token_result = token_data.get("result", [])
            if not isinstance(token_result, list):
                token_result = []

    return {
        "tx": tx_result,
        "receipt": receipt_result,
        "internal": internal_result,
        "tokens": token_result,
    }


def decode_transaction(data: dict, tx_hash: str) -> str:
    tx = data.get("tx", {})
    receipt = data.get("receipt", {})
    internal_txs = data.get("internal", [])
    token_txs = data.get("tokens", [])

    if not tx:
        return "❌ Transaction not found. Please check the hash and try again."

    from_addr = tx.get("from", "Unknown")
    to_addr = tx.get("to", "Contract Creation")
    value = tx.get("value", "0x0")
    gas_price = tx.get("gasPrice", "0")
    gas_used = receipt.get("gasUsed", "0")
    status = receipt.get("status", "0x1")
    input_data = tx.get("input", "0x")
    block_number = tx.get("blockNumber", "Pending")

    status_emoji = "✅" if status == "0x1" else "❌"
    status_text = "Success" if status == "0x1" else "Failed"

    to_protocol = identify_protocol(to_addr) if to_addr else None
    method_name = decode_method(input_data)

    try:
        gas_used_int = int(gas_used, 16) if gas_used.startswith("0x") else int(gas_used)
        gas_price_int = int(gas_price, 16) if gas_price.startswith("0x") else int(gas_price)
        tx_fee_wei = gas_used_int * gas_price_int
        tx_fee = tx_fee_wei / 1e18
        tx_fee_str = f"{tx_fee:.6f} MATIC"
    except:
        tx_fee_str = "Unknown"

    result = f"""
📋 *TRANSACTION DECODED*

{status_emoji} *Status:* {status_text}
🔗 *Hash:* `{tx_hash[:20]}...{tx_hash[-8:]}`
📦 *Block:* {int(block_number, 16) if block_number.startswith("0x") else block_number}

━━━━━━━━━━━━━━━━━━━━━━

👤 *FROM:* `{from_addr[:10]}...{from_addr[-8:]}`
"""

    if to_addr:
        result += f"📍 *TO:* `{to_addr[:10]}...{to_addr[-8:]}`\n"
        if to_protocol:
            result += f"🏛️ *Protocol:* {to_protocol}\n"
    else:
        result += "📍 *TO:* Contract Creation\n"

    result += f"""
━━━━━━━━━━━━━━━━━━━━━━

💰 *VALUE TRANSFERRED:* {format_wei_to_matic(value)}
🔧 *METHOD:* {method_name}

━━━━━━━━━━━━━━━━━━━━━━

⛽ *GAS DETAILS:*
• Gas Used: {int(gas_used, 16) if gas_used.startswith("0x") else gas_used:,}
• Gas Price: {format_gas_price(gas_price)}
• Transaction Fee: {tx_fee_str}
"""

    relevant_token_txs = [t for t in token_txs if t.get("hash", "").lower() == tx_hash.lower()]
    
    if relevant_token_txs:
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n🪙 *TOKEN TRANSFERS:*\n"
        for i, token_tx in enumerate(relevant_token_txs[:10], 1):
            token_name = token_tx.get("tokenName", "Unknown Token")
            token_symbol = token_tx.get("tokenSymbol", "???")
            token_from = token_tx.get("from", "")
            token_to = token_tx.get("to", "")
            token_value = token_tx.get("value", "0")
            token_decimals = int(token_tx.get("tokenDecimal", "18"))

            try:
                amount = int(token_value) / (10 ** token_decimals)
                if amount < 0.0001:
                    amount_str = f"{amount:.10f}"
                elif amount < 1:
                    amount_str = f"{amount:.6f}"
                else:
                    amount_str = f"{amount:,.4f}"
            except:
                amount_str = token_value

            from_protocol = identify_protocol(token_from)
            to_protocol_name = identify_protocol(token_to)

            from_display = from_protocol if from_protocol else f"`{token_from[:8]}...{token_from[-6:]}`"
            to_display = to_protocol_name if to_protocol_name else f"`{token_to[:8]}...{token_to[-6:]}`"

            result += f"\n{i}. *{token_name} ({token_symbol})*\n"
            result += f"   💸 {amount_str} {token_symbol}\n"
            result += f"   📤 From: {from_display}\n"
            result += f"   📥 To: {to_display}\n"

    if internal_txs and isinstance(internal_txs, list) and len(internal_txs) > 0:
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n🔄 *INTERNAL TRANSACTIONS:*\n"
        for i, itx in enumerate(internal_txs[:5], 1):
            itx_from = itx.get("from", "")
            itx_to = itx.get("to", "")
            itx_value = itx.get("value", "0")
            itx_type = itx.get("type", "call")

            from_protocol = identify_protocol(itx_from)
            to_protocol_name = identify_protocol(itx_to)

            from_display = from_protocol if from_protocol else f"`{itx_from[:8]}...{itx_from[-6:]}`"
            to_display = to_protocol_name if to_protocol_name else f"`{itx_to[:8]}...{itx_to[-6:]}`"

            result += f"\n{i}. *{itx_type.upper()}*\n"
            result += f"   💰 {format_wei_to_matic(itx_value)}\n"
            result += f"   📤 From: {from_display}\n"
            result += f"   📥 To: {to_display}\n"

    result += f"""
━━━━━━━━━━━━━━━━━━━━━━

🔗 [View on Polygonscan](https://polygonscan.com/tx/{tx_hash})
"""

    return result


async def handle_polygonscan_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    logger.info(f"Polygonscan query: {user_text}")

    if not user_text.startswith("0x") or len(user_text) != 66:
        await update.message.reply_text(
            "❌ Invalid transaction hash format.\n\n"
            "Please provide a valid Polygon transaction hash (66 characters starting with 0x).\n\n"
            "Example: `0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef`",
            parse_mode="Markdown",
        )
        return POLYGONSCAN_INPUT

    await update.message.chat.send_action("typing")

    try:
        data = await fetch_tx_details(user_text)
        decoded = decode_transaction(data, user_text)
        await update.message.reply_text(decoded, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Polygonscan error: {e}")
        await update.message.reply_text(
            "❌ Error fetching transaction details. Please try again later."
        )

    return POLYGONSCAN_INPUT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Goodbye! Use /start to begin again.")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(menu_callback)],
            PINECONE_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pinecone_message),
                CommandHandler("menu", menu_command),
            ],
            POLYGONSCAN_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_polygonscan_message),
                CommandHandler("menu", menu_command),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("menu", menu_command),
        ],
    )

    app.add_handler(conv_handler)

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
