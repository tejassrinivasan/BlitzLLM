# BlitzLLM Conversation Widget

This simple JavaScript widget provides a chat interface that communicates with
the `/conversation` endpoint exposed by the BlitzLLM API. Partners can embed the
widget in their website or application to allow end users to interact with the
LLM without building a custom front end.

## Usage

1. Copy `conversation_widget.js` and `conversation_widget.css` into your
   project.
2. Include the files on the page where the widget should appear:

```html
<link rel="stylesheet" href="conversation_widget.css" />
<div id="blitz-widget"></div>
<script src="conversation_widget.js"></script>
<script>
  BlitzWidget.createWidget({
    targetId: 'blitz-widget',          // Element that will host the widget
    apiBase: 'https://your-api-host',  // Base URL of the BlitzLLM API
    apiKey: 'YOUR_API_KEY',            // Partner API key
    device: 'desktop',                 // 'mobile', 'tablet' or 'desktop'
    border: true,                      // show widget border
    theme: 'light',                    // 'light' or 'dark'
    userId: 'user@example.com'         // optional user identifier
  });
</script>
```

For a working example see [`example.html`](example.html).

The widget maintains the conversation ID and message IDs internally and polls
the API until a response is ready. The appearance can be customized by modifying
the accompanying CSS file.

### Options

| Option | Description |
|--------|-------------|
| `device` | `'mobile'`, `'tablet'`, or `'desktop'` width presets |
| `border` | `true` to show a border, `false` for none |
| `theme` | `'light'` or `'dark'` color scheme |
| `userId` | String identifying the end user. Used to persist conversation state |

## Streaming Version

A variant named `streaming_conversation_widget.js` is also provided. It uses the
`/api/conversations/{conversation_id}/messages/stream` endpoint and polls the
`/api/tasks/{task_id}` endpoint for progress. Include this file instead of
`conversation_widget.js` to enable streaming responses.
