# Spec: Manage Timer Command

**Objective:** To allow authorized users to modify the interval of a recurring timer message.

**Actors:**

*   Telegram User (Authorized)
*   Bot

**Preconditions:**

*   The user is an authorized user.
*   The bot is configured with a default timer interval.

**Success Scenario:**

1.  An authorized user issues the command `/set_timer <NEW_INTERVAL>` (e.g., `/set_timer 5`).
2.  The bot validates that the user is authorized.
3.  The bot updates its configuration to use the new timer interval.
4.  The bot confirms the change to the user.
5.  Subsequent timer messages are sent at the new interval.

**Error Scenarios:**

*   **Unauthorized user:** If a non-authorized user tries to use the command, the bot should inform them they are not authorized.
*   **Invalid interval:** If the user provides an invalid or non-numeric interval, the bot should respond with an error message.
*   **Missing interval:** If the user does not provide an interval, the bot should respond with a message explaining how to use the command.

**Technical Details:**

*   A new command handler for `/set_timer` will be created.
*   The handler will check if the user is in the `AUTHORIZED_USER_IDS` list.
*   The handler will update the timer interval value in the bot's configuration.
*   The bot's timer logic will need to be updated to use the new interval.
