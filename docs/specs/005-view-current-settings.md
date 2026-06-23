# Spec 005: View Current Bot Configuration

**Goal:** Implement a `/config_status` command to allow authorized users to view the bot's current dynamic configuration settings.

## 1. Command

`/config_status`

## 2. Description

This command provides a quick and secure way for authorized administrators to check the bot's active configuration parameters, such as the target symbol and polling interval, without accessing the server or application logs.

## 3. Authorization

-   **Restricted:** This command MUST be restricted to authorized users.
-   **Mechanism:** Access control will be handled by the existing `authorized_users_only` decorator located in `src/bot/handlers.py`.

## 4. Functionality

-   Upon receiving `/config_status` from an authorized user, the bot will retrieve the current values of its dynamic settings.
-   The following settings MUST be retrieved and displayed:
    -   `SYMBOL`: The stock or asset symbol the bot is currently monitoring.
    -   `TIMER_INTERVAL`: The interval (in minutes) at which the bot fetches and reports data.
-   The implementation should source these values from the application's runtime state (e.g., `src/config.py`).

## 5. Output Format

The bot MUST reply with a plain text message formatted as follows:

```text
Current Bot Configuration:
- Symbol: <VALUE>
- Timer Interval: <VALUE> minute(s)
```

**Example:**

```text
Current Bot Configuration:
- Symbol: AAPL
- Timer Interval: 1 minute(s)
```

## 6. Error Handling

-   If an unauthorized user attempts to execute the command, the bot will ignore the request or reply with a standard "Unauthorized" message, consistent with the behavior of other restricted commands.

## 7. Implementation Steps

1.  **Define Handler (`src/bot/handlers.py`):**
    -   Create a new asynchronous function `config_status(update, context)`.
    -   Apply the `@authorized_users_only` decorator to the function.
    -   Inside the function, retrieve the `SYMBOL` and `TIMER_INTERVAL` values from the configuration.
    -   Format the retrieved values into the specified string format.
    -   Send the formatted string as a reply to the user.

2.  **Register Handler (`src/main.py`):**
    -   Import the `config_status` handler from `src/bot/handlers.py`.
    -   Create a new `CommandHandler` for `config_status` and add it to the `Application` instance.

3.  **Add Test Case (`tests/test_handlers.py`):**
    -   (Recommended) Create a new test function to verify the `/config_status` command.
    -   The test should simulate a call from an authorized user and assert that the bot's reply matches the expected format and contains the correct configuration values.
