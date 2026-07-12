# Spec XXX: <Feature Name>

**Goal:** <One sentence describing the outcome this spec must deliver.>

## 1. Rationale

<Explain why this change is needed, what problem it solves, and what current limitation or roadmap item it addresses.>

## 2. Scope

In scope:

- <Capability, command, workflow, or system behavior included in this spec.>
- <Another included item.>

Out of scope:

- <Related work intentionally excluded from this spec.>
- <Another excluded item.>

## 3. Actors and Authorization

Actors:

- <Actor, such as Telegram User (Authorized), Channel Admin, Bot, Scheduler, or External API.>
- <Another actor if needed.>

Authorization:

- <State whether the feature is public, admin-only, or super-admin-only.>
- <Reference the existing authorization mechanism if applicable.>

## 4. Preconditions

- <Required configuration, data, external service, or runtime condition.>
- <Required existing command or system behavior.>

## 5. Functional Requirements

### 5.1 <Requirement Area>

- The system MUST <required behavior>.
- The system SHOULD <recommended behavior>.
- The system MAY <optional behavior>.

### 5.2 <Requirement Area>

- <Additional requirement.>
- <Additional requirement.>

## 6. User Flows and Scenarios

### 6.1 Primary Success Scenario

1.  <Actor performs an action.>
2.  <System validates or processes the action.>
3.  <System updates state or calls a service.>
4.  <System returns the expected response.>

### 6.2 Alternative Scenario

1.  <Alternative input or path.>
2.  <Expected behavior.>

## 7. Command Behavior

Use this section for Telegram command features. If the spec has no command behavior, write `N/A`.

Command:

```text
/<command_name> <ARGUMENTS>
```

Valid examples:

- `/<command_name> <valid_example>`

Invalid examples:

- `/<command_name> <invalid_example>`

Expected response:

```text
<Expected plain-text response format, if exact formatting matters.>
```

## 8. Configuration and Persistence

- <List new or changed configuration keys.>
- <State where dynamic settings are persisted, such as Redis, database, environment variables, or files.>
- <State default values and override order if relevant.>

## 9. Technical Requirements

- <Implementation constraint or preferred module boundary.>
- <Existing file, service, or helper that should be used.>
- <Backward compatibility requirement.>
- <Operational concern such as avoiding duplicate jobs, rate limits, or unsafe startup behavior.>

## 10. Error Handling

- <Invalid input case and required response.>
- <Unauthorized access case and required response.>
- <External service or persistence failure behavior.>
- <Logging requirement if relevant.>

## 11. Implementation Steps

1.  **<Step Name>:**
    -   <Concrete implementation task.>
    -   <Files or modules likely to change, if known.>

2.  **<Step Name>:**
    -   <Concrete implementation task.>

3.  **<Step Name>:**
    -   <Concrete implementation task.>

## 12. Test Requirements

- <Unit test requirement.>
- <Handler or integration test requirement.>
- <Persistence or configuration test requirement.>
- <Regression test requirement.>

## 13. Validation

This feature is complete when:

- <Acceptance criterion.>
- <Acceptance criterion.>
- <Relevant automated tests pass.>

## 14. Notes

- <Any open question, decision, migration concern, or follow-up that should be visible before implementation starts.>
