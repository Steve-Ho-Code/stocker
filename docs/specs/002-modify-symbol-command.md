# Spec: Modify Symbol Command

**Objective:** To allow authorized users to modify the stock symbol the bot is tracking.

**Actors:**

*   Telegram User (Authorized)
*   Bot

**Preconditions:**

*   The user is an authorized user.

**Success Scenario:**

1.  An authorized user issues the command `/set_symbol <NEW_SYMBOL>` (e.g., `/set_symbol GOOGL`).
2.  The bot validates that the user is authorized.
3.  The bot updates its configuration to use the new symbol.
4.  The bot confirms the change to the user.
5.  Subsequent price updates use the new symbol.

**Error Scenarios:**

*   **Unauthorized user:** If a non-authorized user tries to use the command, the bot should inform them they are not authorized.
*   **Invalid symbol:** If the user provides an invalid or unsupported symbol, the bot should respond with an error message.
*   **Missing symbol:** If the user does not provide a symbol, the bot should respond with a message explaining how to use the command.

**Technical Details:**

*   A new command handler for `/set_symbol` will be created.
*   The handler will check if the user is in the `AUTHORIZED_USER_IDS` list.
*   The handler will update the `SYMBOL` value in the bot's configuration. This may involve editing a configuration file or updating an environment variable.
*   The bot will need a way to validate the new symbol, perhaps by checking it against the `alpha_vantage` API.
