def main():
    render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    port = int(os.environ.get("PORT", "10000"))
    webhook_secret = os.environ.get("WEBHOOK_SECRET_TOKEN")

    if not render_hostname or not webhook_secret:
        raise RuntimeError(
            "Missing Render hostname or webhook secret."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("expense", expense))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("history", history))

    print("Expense Tracker Bot is starting with Webhook!")

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