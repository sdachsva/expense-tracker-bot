
import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from supabase import create_client

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# -----------------------------
# Environment Variables
# -----------------------------
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing environment variables. "
        "Check Render Environment settings."
    )

db = create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------------
# Start Command
# -----------------------------
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        "Welcome to Expense Tracker!\n\n"
        "Commands:\n"
        "/expense Lunch 5000 - Add expense\n"
        "/income Salary 500000 - Add income\n"
        "/summary - View totals\n"
        "/history - View recent transactions"
    )


# -----------------------------
# Add Income / Expense
# -----------------------------
async def add_transaction(update, context, kind):
    if not update.message or not update.effective_user:
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            f"Usage: /{kind} Description Amount\n"
            f"Example: /{kind} Lunch 5000"
        )
        return

    try:
        amount = float(context.args[-1])

        if not 0 < amount < 1_000_000_000:
            raise ValueError("Amount is outside the allowed range.")

    except ValueError:
        await update.message.reply_text(
            "Please enter a valid positive amount."
        )
        return

    description = " ".join(context.args[:-1]).strip()

    if not description:
        await update.message.reply_text(
            "Please enter a transaction description."
        )
        return

    transaction = {
        "user_id": update.effective_user.id,
        "kind": kind,
        "description": description,
        "amount": amount,
    }

    try:
        result = (
            db.table("transactions")
            .insert(transaction)
            .execute()
        )

        logger.info(
            "Transaction saved successfully: kind=%s user_id=%s",
            kind,
            update.effective_user.id,
        )

        await update.message.reply_text(
            f"Saved {kind} successfully!\n"
            f"Description: {description}\n"
            f"Amount: {amount:,.2f} KHR"
        )

    except Exception as e:
        # Log the actual database error for troubleshooting.
        logger.exception(
            "Could not save transaction. Error type: %s",
            type(e).__name__,
        )
        logger.error("Supabase insert error: %s", str(e))

        await update.message.reply_text(
            "Could not save transaction.\n"
            "Please check Render Logs."
        )


async def expense(update, context):
    await add_transaction(update, context, "expense")


async def income(update, context):
    await add_transaction(update, context, "income")


# -----------------------------
# Summary Command
# -----------------------------
async def summary(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.effective_user:
        return

    try:
        result = (
            db.table("transactions")
            .select("kind, amount")
            .eq("user_id", update.effective_user.id)
            .execute()
        )

        records = result.data or []

        income_total = sum(
            float(row["amount"])
            for row in records
            if row["kind"] == "income"
        )

        expense_total = sum(
            float(row["amount"])
            for row in records
            if row["kind"] == "expense"
        )

        balance = income_total - expense_total

        await update.message.reply_text(
            "Your Financial Summary\n\n"
            f"Income: {income_total:,.2f} KHR\n"
            f"Expense: {expense_total:,.2f} KHR\n"
            f"Balance: {balance:,.2f} KHR"
        )

    except Exception as e:
        logger.exception("Summary failed")
        logger.error("Supabase summary error: %s", str(e))

        await update.message.reply_text(
            "Could not load summary. Check Render Logs."
        )


# -----------------------------
# History Command
# -----------------------------
async def history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.effective_user:
        return

    try:
        result = (
            db.table("transactions")
            .select("kind, description, amount, created_at")
            .eq("user_id", update.effective_user.id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        records = result.data or []

        if not records:
            await update.message.reply_text(
                "No transactions yet."
            )
            return

        lines = []

        for row in records:
            lines.append(
                f'{row["kind"].title()}: '
                f'{row["description"]} - '
                f'{float(row["amount"]):,.2f} KHR'
            )

        await update.message.reply_text(
            "Recent Transactions\n\n" + "\n".join(lines)
        )

    except Exception as e:
        logger.exception("History failed")
        logger.error("Supabase history error: %s", str(e))

        await update.message.reply_text(
            "Could not load history. Check Render Logs."
        )


# -----------------------------
# Main / Render Webhook
# -----------------------------
def main():
    render_hostname = os.environ.get(
        "RENDER_EXTERNAL_HOSTNAME"
    )
    port = int(os.environ.get("PORT", "10000"))
    webhook_secret = os.environ.get(
        "WEBHOOK_SECRET_TOKEN"
    )

    if not render_hostname or not webhook_secret:
        raise RuntimeError(
            "Missing Render hostname or webhook secret. "
            "Check Render Environment settings."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("expense", expense))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("history", history))

    logger.info("Expense Tracker Bot starting with webhook.")

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="telegram-webhook",
        webhook_url=(
            f"https://{render_hostname}/telegram-webhook"
        ),
        secret_token=webhook_secret,
    )


if __name__ == "__main__":
    main()
