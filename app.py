
import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from supabase import create_client

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing environment variables. Check your CMD settings."
    )

db = create_client(SUPABASE_URL, SUPABASE_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Expense Tracker!\n\n"
        "/expense Lunch 5000 - Add expense\n"
        "/income Salary 500000 - Add income\n"
        "/summary - View totals\n"
        "/history - View recent transactions"
    )


async def add_transaction(update, context, kind):
    if len(context.args) < 2:
        await update.message.reply_text(
            f"Usage: /{kind} Description Amount\n"
            f"Example: /{kind} Lunch 5000"
        )
        return

    try:
        amount = float(context.args[-1])
        if not 0 < amount < 1_000_000_000:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid positive amount."
        )
        return

    description = " ".join(context.args[:-1])

    try:
        db.table("transactions").insert({
            "user_id": update.effective_user.id,
            "kind": kind,
            "description": description,
            "amount": amount,
        }).execute()

        await update.message.reply_text(
            f"Saved {kind}: {description} - {amount:,.2f} KHR"
        )
    except Exception:
        logging.exception("Could not save transaction")
        await update.message.reply_text(
            "Could not save transaction. Check Supabase settings."
        )


async def expense(update, context):
    await add_transaction(update, context, "expense")


async def income(update, context):
    await add_transaction(update, context, "income")


async def summary(update, context):
    try:
        result = (
            db.table("transactions")
            .select("kind, amount")
            .eq("user_id", update.effective_user.id)
            .execute()
        )

        income_total = sum(
            float(r["amount"]) for r in result.data
            if r["kind"] == "income"
        )
        expense_total = sum(
            float(r["amount"]) for r in result.data
            if r["kind"] == "expense"
        )

        await update.message.reply_text(
            f"Income: {income_total:,.2f} KHR\n"
            f"Expense: {expense_total:,.2f} KHR\n"
            f"Balance: {income_total - expense_total:,.2f} KHR"
        )
    except Exception:
        logging.exception("Summary failed")
        await update.message.reply_text(
            "Could not load summary. Check Supabase."
        )


async def history(update, context):
    try:
        result = (
            db.table("transactions")
            .select("kind, description, amount, created_at")
            .eq("user_id", update.effective_user.id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        if not result.data:
            await update.message.reply_text("No transactions yet.")
            return

        lines = [
            f'{r["kind"].title()}: {r["description"]} '
            f'{float(r["amount"]):,.2f} KHR'
            for r in result.data
        ]

        await update.message.reply_text("\n".join(lines))
    except Exception:
        logging.exception("History failed")
        await update.message.reply_text(
            "Could not load history. Check Supabase."
        )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("expense", expense))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("history", history))

    print("Expense Tracker Bot is running!")
    app.run_polling()


if __name__ == "__main__":
    main()
