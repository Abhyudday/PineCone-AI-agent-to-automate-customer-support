import os
import json
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

POLYGON_RPC = "https://polygon-rpc.com"
POLYGONSCAN_API = "https://api.etherscan.io/v2/api"
CHAIN_ID = "137"

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


def is_tx_hash(text: str) -> bool:
    return text.startswith("0x") and len(text) == 66


def is_wallet_address(text: str) -> bool:
    return text.startswith("0x") and len(text) == 42


def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🤖 Pinecone Assistant", callback_data=MODE_PINECONE)],
        [InlineKeyboardButton("🔍 Polygon Explorer", callback_data=MODE_POLYGONSCAN)],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Polycop Bot!*\n\n"
        "Choose an option:\n\n"
        "🤖 *Pinecone Assistant* — Ask questions and get AI-powered responses\n\n"
        "🔍 *Polygon Explorer* — Paste a TX hash or wallet address to get detailed on-chain insights, then ask follow-up questions\n",
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
        context.user_data.pop("last_data", None)
        context.user_data.pop("last_summary", None)
        await query.edit_message_text(
            "🔍 *Polygon Explorer Mode*\n\n"
            "Send me a:\n"
            "• *Transaction hash* (66 chars) — to decode a transaction\n"
            "• *Wallet address* (42 chars) — to view recent activity\n\n"
            "After fetching, you can ask follow-up questions!\n\n"
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


# ─── Utility functions ───

def format_wei_to_matic(wei_value) -> str:
    try:
        if isinstance(wei_value, str):
            wei = int(wei_value, 16) if wei_value.startswith("0x") else int(wei_value)
        else:
            wei = int(wei_value)
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
        return str(wei_value)


def format_gas_price(wei_value: str) -> str:
    try:
        wei = int(wei_value, 16) if wei_value.startswith("0x") else int(wei_value)
        gwei = wei / 1e9
        return f"{gwei:.2f} Gwei"
    except:
        return wei_value


def identify_protocol(address: str) -> str:
    if not address:
        return None
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


def short_addr(addr: str) -> str:
    if not addr or len(addr) < 12:
        return addr or "Unknown"
    return f"`{addr[:8]}...{addr[-6:]}`"


# ─── RPC helpers (no API key needed for basic TX data) ───

async def rpc_call(client: httpx.AsyncClient, method: str, params: list) -> dict:
    resp = await client.post(
        POLYGON_RPC,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=15,
    )
    data = resp.json()
    return data.get("result")


async def polygonscan_get(client: httpx.AsyncClient, **params) -> dict:
    params["apikey"] = POLYGONSCAN_API_KEY
    params["chainid"] = CHAIN_ID
    resp = await client.get(POLYGONSCAN_API, params=params, timeout=15)
    data = resp.json()
    logger.info(f"Polygonscan response ({params.get('action')}): status={data.get('status', 'n/a')}")
    return data.get("result")


# ─── Fetch transaction ───

async def fetch_tx_details(tx_hash: str) -> dict:
    async with httpx.AsyncClient() as client:
        tx_result = await rpc_call(client, "eth_getTransactionByHash", [tx_hash])
        if not isinstance(tx_result, dict):
            tx_result = {}
        logger.info(f"RPC tx result keys: {list(tx_result.keys()) if tx_result else 'empty'}")

        receipt_result = await rpc_call(client, "eth_getTransactionReceipt", [tx_hash])
        if not isinstance(receipt_result, dict):
            receipt_result = {}

        internal_result = await polygonscan_get(
            client, module="account", action="txlistinternal", txhash=tx_hash
        )
        if not isinstance(internal_result, list):
            internal_result = []

        from_addr = tx_result.get("from", "")
        token_result = []
        if from_addr:
            token_result = await polygonscan_get(
                client,
                module="account",
                action="tokentx",
                address=from_addr,
                startblock=0,
                endblock=99999999,
                page=1,
                offset=100,
                sort="desc",
            )
            if not isinstance(token_result, list):
                token_result = []

    return {
        "tx": tx_result,
        "receipt": receipt_result,
        "internal": internal_result,
        "tokens": token_result,
    }


# ─── Fetch wallet info ───

async def fetch_wallet_details(address: str) -> dict:
    async with httpx.AsyncClient() as client:
        balance_raw = await rpc_call(client, "eth_getBalance", [address, "latest"])
        balance = format_wei_to_matic(balance_raw) if balance_raw else "Unknown"

        tx_count_raw = await rpc_call(client, "eth_getTransactionCount", [address, "latest"])
        try:
            tx_count = int(tx_count_raw, 16) if tx_count_raw else 0
        except:
            tx_count = 0

        recent_txs = await polygonscan_get(
            client,
            module="account",
            action="txlist",
            address=address,
            startblock=0,
            endblock=99999999,
            page=1,
            offset=10,
            sort="desc",
        )
        if not isinstance(recent_txs, list):
            recent_txs = []

        token_txs = await polygonscan_get(
            client,
            module="account",
            action="tokentx",
            address=address,
            startblock=0,
            endblock=99999999,
            page=1,
            offset=10,
            sort="desc",
        )
        if not isinstance(token_txs, list):
            token_txs = []

    return {
        "address": address,
        "balance": balance,
        "tx_count": tx_count,
        "recent_txs": recent_txs,
        "token_txs": token_txs,
    }


# ─── Format transaction ───

def decode_transaction(data: dict, tx_hash: str) -> tuple[str, str]:
    tx = data.get("tx", {})
    receipt = data.get("receipt", {})
    internal_txs = data.get("internal", [])
    token_txs = data.get("tokens", [])

    if not tx:
        return "❌ Transaction not found. Please check the hash and try again.", ""

    from_addr = tx.get("from", "Unknown")
    to_addr = tx.get("to") or "Contract Creation"
    value = tx.get("value", "0x0")
    gas_price = tx.get("gasPrice", "0")
    gas_used = receipt.get("gasUsed", "0")
    status = receipt.get("status", "0x1")
    input_data = tx.get("input", "0x")
    block_number = tx.get("blockNumber", "Pending")

    status_text = "Success" if status == "0x1" else "Failed"
    status_emoji = "✅" if status == "0x1" else "❌"
    to_protocol = identify_protocol(to_addr)
    method_name = decode_method(input_data)
    value_matic = format_wei_to_matic(value)

    try:
        gu = int(gas_used, 16) if isinstance(gas_used, str) and gas_used.startswith("0x") else int(gas_used)
        gp = int(gas_price, 16) if isinstance(gas_price, str) and gas_price.startswith("0x") else int(gas_price)
        tx_fee = (gu * gp) / 1e18
        tx_fee_str = f"{tx_fee:.6f} MATIC"
        gas_used_str = f"{gu:,}"
    except:
        tx_fee_str = "Unknown"
        gas_used_str = str(gas_used)

    try:
        block_num = int(block_number, 16) if isinstance(block_number, str) and block_number.startswith("0x") else block_number
    except:
        block_num = block_number

    result = (
        f"📋 *TRANSACTION DECODED*\n\n"
        f"{status_emoji} *Status:* {status_text}\n"
        f"🔗 *Hash:* `{tx_hash[:20]}...{tx_hash[-8:]}`\n"
        f"📦 *Block:* {block_num}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *FROM:* {short_addr(from_addr)}\n"
    )

    if to_addr != "Contract Creation":
        result += f"📍 *TO:* {short_addr(to_addr)}\n"
        if to_protocol:
            result += f"🏛️ *Protocol:* {to_protocol}\n"
    else:
        result += "📍 *TO:* Contract Creation\n"

    result += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *VALUE:* {value_matic}\n"
        f"🔧 *METHOD:* {method_name}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⛽ *GAS:*\n"
        f"• Used: {gas_used_str}\n"
        f"• Price: {format_gas_price(gas_price)}\n"
        f"• Fee: {tx_fee_str}\n"
    )

    relevant_tokens = [t for t in token_txs if t.get("hash", "").lower() == tx_hash.lower()]
    if relevant_tokens:
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n🪙 *TOKEN TRANSFERS:*\n"
        for i, ttx in enumerate(relevant_tokens[:10], 1):
            name = ttx.get("tokenName", "Unknown")
            sym = ttx.get("tokenSymbol", "???")
            dec = int(ttx.get("tokenDecimal", "18"))
            try:
                amt = int(ttx.get("value", "0")) / (10 ** dec)
                amt_s = f"{amt:,.4f}" if amt >= 1 else (f"{amt:.6f}" if amt >= 0.0001 else f"{amt:.10f}")
            except:
                amt_s = ttx.get("value", "0")
            fp = identify_protocol(ttx.get("from", ""))
            tp = identify_protocol(ttx.get("to", ""))
            result += (
                f"\n{i}. *{name} ({sym})*\n"
                f"   💸 {amt_s} {sym}\n"
                f"   📤 From: {fp or short_addr(ttx.get('from', ''))}\n"
                f"   📥 To: {tp or short_addr(ttx.get('to', ''))}\n"
            )

    if internal_txs:
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n🔄 *INTERNAL TXS:*\n"
        for i, itx in enumerate(internal_txs[:5], 1):
            fp = identify_protocol(itx.get("from", ""))
            tp = identify_protocol(itx.get("to", ""))
            result += (
                f"\n{i}. *{itx.get('type', 'call').upper()}*\n"
                f"   💰 {format_wei_to_matic(itx.get('value', '0'))}\n"
                f"   📤 From: {fp or short_addr(itx.get('from', ''))}\n"
                f"   📥 To: {tp or short_addr(itx.get('to', ''))}\n"
            )

    result += f"\n━━━━━━━━━━━━━━━━━━━━━━\n\n🔗 [View on Polygonscan](https://polygonscan.com/tx/{tx_hash})\n"
    result += "\n💬 *Ask me anything about this transaction!*"

    summary = (
        f"Transaction {tx_hash}: status={status_text}, from={from_addr}, to={to_addr}, "
        f"protocol={to_protocol or 'unknown'}, method={method_name}, value={value_matic}, "
        f"fee={tx_fee_str}, block={block_num}, "
        f"token_transfers={len(relevant_tokens)}, internal_txs={len(internal_txs)}"
    )
    for ttx in relevant_tokens[:10]:
        dec = int(ttx.get("tokenDecimal", "18"))
        try:
            amt = int(ttx.get("value", "0")) / (10 ** dec)
        except:
            amt = 0
        summary += (
            f"\n  Token: {ttx.get('tokenName','?')} ({ttx.get('tokenSymbol','?')}), "
            f"amount={amt}, from={ttx.get('from','')}, to={ttx.get('to','')}"
        )

    return result, summary


# ─── Format wallet ───

def format_wallet_details(data: dict) -> tuple[str, str]:
    address = data["address"]
    balance = data["balance"]
    tx_count = data["tx_count"]
    recent_txs = data.get("recent_txs", [])
    token_txs = data.get("token_txs", [])

    result = (
        f"👛 *WALLET OVERVIEW*\n\n"
        f"📍 *Address:* `{address}`\n"
        f"💰 *MATIC Balance:* {balance}\n"
        f"📊 *Total Transactions:* {tx_count:,}\n"
    )

    if recent_txs:
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n� *RECENT TRANSACTIONS:*\n"
        for i, tx in enumerate(recent_txs[:5], 1):
            tx_hash = tx.get("hash", "")
            from_a = tx.get("from", "")
            to_a = tx.get("to", "")
            val = tx.get("value", "0")
            method = tx.get("functionName", "").split("(")[0] or "transfer"
            direction = "📤 OUT" if from_a.lower() == address.lower() else "📥 IN"
            prot = identify_protocol(to_a)
            result += (
                f"\n{i}. {direction} — *{method}*\n"
                f"   💰 {format_wei_to_matic(val)}\n"
                f"   🔗 `{tx_hash[:16]}...`\n"
            )
            if prot:
                result += f"   🏛️ {prot}\n"

    if token_txs:
        result += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n🪙 *RECENT TOKEN ACTIVITY:*\n"
        for i, ttx in enumerate(token_txs[:5], 1):
            name = ttx.get("tokenName", "Unknown")
            sym = ttx.get("tokenSymbol", "???")
            dec = int(ttx.get("tokenDecimal", "18"))
            try:
                amt = int(ttx.get("value", "0")) / (10 ** dec)
                amt_s = f"{amt:,.4f}" if amt >= 1 else f"{amt:.6f}"
            except:
                amt_s = ttx.get("value", "0")
            direction = "📤 OUT" if ttx.get("from", "").lower() == address.lower() else "📥 IN"
            result += f"\n{i}. {direction} *{name} ({sym})* — {amt_s} {sym}\n"

    result += f"\n━━━━━━━━━━━━━━━━━━━━━━\n\n🔗 [View on Polygonscan](https://polygonscan.com/address/{address})\n"
    result += "\n💬 *Ask me anything about this wallet!*"

    summary = (
        f"Wallet {address}: balance={balance}, total_txs={tx_count}, "
        f"recent_txs={len(recent_txs)}, recent_token_txs={len(token_txs)}"
    )
    for tx in recent_txs[:5]:
        summary += f"\n  TX: hash={tx.get('hash','')}, from={tx.get('from','')}, to={tx.get('to','')}, value={tx.get('value','0')}, method={tx.get('functionName','')}"

    return result, summary


# ─── Polygonscan message handler ───

async def handle_polygonscan_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    logger.info(f"Explorer query: {user_text}")

    await update.message.chat.send_action("typing")

    if is_tx_hash(user_text):
        try:
            data = await fetch_tx_details(user_text)
            decoded, summary = decode_transaction(data, user_text)
            context.user_data["last_data"] = data
            context.user_data["last_summary"] = summary
            context.user_data["last_type"] = "tx"
            await update.message.reply_text(decoded, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"TX fetch error: {e}", exc_info=True)
            await update.message.reply_text("❌ Error fetching transaction. Please try again.")
        return POLYGONSCAN_INPUT

    elif is_wallet_address(user_text):
        try:
            data = await fetch_wallet_details(user_text)
            formatted, summary = format_wallet_details(data)
            context.user_data["last_data"] = data
            context.user_data["last_summary"] = summary
            context.user_data["last_type"] = "wallet"
            await update.message.reply_text(formatted, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Wallet fetch error: {e}", exc_info=True)
            await update.message.reply_text("❌ Error fetching wallet data. Please try again.")
        return POLYGONSCAN_INPUT

    else:
        last_summary = context.user_data.get("last_summary")
        if last_summary:
            try:
                context_prompt = (
                    f"You are a blockchain analyst. The user previously looked up this on-chain data:\n\n"
                    f"{last_summary}\n\n"
                    f"Answer the user's question based on the data above. Be detailed and specific.\n\n"
                    f"User question: {user_text}"
                )
                msg = Message(content=context_prompt)
                resp = assistant.chat(messages=[msg])
                reply = resp["message"]["content"]
            except Exception as e:
                logger.error(f"Follow-up error: {e}")
                reply = "❌ Could not process your question. Please try again."
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text(
                "Please paste a *transaction hash* (66 chars) or *wallet address* (42 chars) first.\n\n"
                "After that, you can ask follow-up questions!",
                parse_mode="Markdown",
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
