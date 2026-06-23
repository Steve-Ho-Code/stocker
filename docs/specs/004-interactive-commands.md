# Spec: Interactive Prompts for Missing Arguments

**Objective:** To make the `/set_timer` and `/set_symbol` commands more user-friendly by interactively prompting for missing values instead of just showing a help message.

**Actors:**

*   Telegram User (Authorized)
*   Bot

**Preconditions:**

*   The user is an authorized user.

**Success Scenario (for /set_timer):**

1.  An authorized user issues the command `/set_timer` without an interval.
2.  The bot recognizes the missing argument and prompts the user to "Please enter the timer interval in minutes."
3.  The user replies with a valid number (e.g., "15").
4.  The bot validates the input.
5.  The bot updates its configuration to use the new timer interval.
6.  The bot confirms the change to the user: "Timer interval updated to 15 minutes."

**Success Scenario (for /set_symbol):**

1.  An authorized user issues the command `/set_symbol` without a symbol.
2.  The bot recognizes the missing argument and prompts the user to "Please enter the stock symbol."
3.  The user replies with a valid symbol (e.g., "MSFT").
4.  The bot validates the input.
5.  The bot updates its configuration to use the new symbol.
6.  The bot confirms the change to the user: "Stock symbol updated to MSFT."

**Alternative Scenario (Argument Provided):**

1.  An authorized user issues the command with the required value (e.g., `/set_timer 30` or `/set_symbol AAPL`).
2.  The bot skips the interactive prompt.
3.  The bot updates its configuration directly.
4.  The bot confirms the change to the user.

**Error Scenarios:**

*   **Unauthorized user:** If a non-authorized user tries to use the command, the bot should inform them they are not authorized. This behavior remains unchanged.
*   **Invalid input to prompt:** If the user provides an invalid value in response to the prompt (e.g., "abc" for the timer interval), the bot should respond with an error message and re-prompt for the correct value.
*   **User does not reply:** If the user does not reply to the prompt within 60 seconds, the conversation state should expire, and the bot should send a message saying "Request timed out. Please try again."
*   **User cancels:** If the user sends `/cancel` during the prompt, the conversation should be terminated, and the bot should confirm with a message like "Operation cancelled."

**Technical Details:**

*   The command handlers for `/set_timer` and `/set_symbol` in `src/bot/handlers.py` will be modified.
*   The handlers will check if the required argument (interval or symbol) is present.
*   If the argument is missing, the bot will initiate a conversation-based flow. In `python-telegram-bot`, this can be achieved using `ConversationHandler`.
*   A new state will be defined for waiting for the user's input.
*   A new handler will be created to process the user's reply, validate it, update the configuration, and end the conversation.
*   The existing logic for handling authorized users and updating the configuration will be integrated into this new flow.
