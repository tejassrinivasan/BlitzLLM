# BlitzLLM

BlitzLLM exposes a small set of REST endpoints used by B2B partners to query baseball data and record feedback. All endpoints require an `X-API-Key` header with a valid key.

## Endpoints

### `POST /generate-insights`
Generates a text response based on the provided question and optional context. The call returns immediately with a `response_id` while processing continues asynchronously.

| Field | Type | Description |
|-------|------|-------------|
| `question` | `string` | The question or request to answer. **Required**. |
| `custom_data` | `object` | Arbitrary JSON data used to augment the prompt. Optional. |
| `partner_id` | `integer` | Identifier for the calling partner. Optional. |
| `simple` | `boolean` | When `true`, request a short one-sentence answer. Defaults to `false`. |
| `league` | `string` | League code (e.g. `"mlb"`). Defaults to `"mlb"`. |

The response will include a unique `response_id` that can be polled later.

### `GET /insights/{response_id}`
Retrieve a previously generated response. Include the `partner_id` as a query parameter if used when creating the response.

### `POST /conversation`
Provides a conversation style interface that keeps track of previous questions and answers. The request schedules processing and returns a `response_id` immediately.

The request body accepts the same fields as `/generate-insights` plus:

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `integer` | Identifier for the end user. Optional. |
| `conversation_id` | `integer` | Conversation identifier. Optional. |
| `message_id` | `integer` | Message identifier. Optional. |
| `retry` | `boolean` | When `true`, retry the message at the given `message_id`. |

If `conversation_id` and `message_id` are omitted a new conversation is started and both identifiers are generated automatically. The API response always includes the current `conversation_id` together with the `response_id`.

### `POST /feedback`
Stores user feedback. The body must contain:

| Field | Type | Description |
|-------|------|-------------|
| `call_id` | `string` | Identifier of the API call being rated. **Required**. |
| `helpful` | `boolean` | Whether the response was helpful. **Required**. |


## Embeddable Conversation Widget

A simple JavaScript widget is provided in the [`widget`](widget) directory. It
creates a chat interface that communicates with the `/conversation` API
endpoint. Partners can embed it in their own sites by including the supplied
JS and CSS files. The widget supports light and dark themes, optional
borders and preset widths for mobile, tablet or desktop displays. See
[`widget/README.md`](widget/README.md) for usage details and an example page.
