# BlitzLLM

BlitzLLM exposes a small set of REST endpoints used by B2B partners to query baseball data and record feedback. All endpoints require an `X-API-Key` header with a valid key.

## Endpoints

### `POST /generate-insights`
Generates a text response based on the provided question and optional context.

| Field | Type | Description |
|-------|------|-------------|
| `question` | `string` | The question or request to answer. **Required**. |
| `custom_data` | `object` | Arbitrary JSON data used to augment the prompt. Optional. |
| `partner_id` | `integer` | Identifier for the calling partner. Optional. |
| `simple` | `boolean` | When `true`, request a short one-sentence answer. Defaults to `false`. |
| `league` | `string` | League code (e.g. `"mlb"`). Defaults to `"mlb"`. |

### `POST /conversation`
Provides a conversation style interface that keeps track of previous questions and answers.

The request body accepts the same fields as `/generate-insights` plus:

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `integer` | Identifier for the end user. Optional. |
| `conversation_id` | `integer` | Conversation identifier. Defaults to `0`. |

### `POST /feedback`
Stores user feedback. The body must contain:

| Field | Type | Description |
|-------|------|-------------|
| `call_id` | `string` | Identifier of the API call being rated. **Required**. |
| `helpful` | `boolean` | Whether the response was helpful. **Required**. |

